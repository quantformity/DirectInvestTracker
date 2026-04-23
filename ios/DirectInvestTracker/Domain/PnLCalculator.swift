import Foundation

/// Pure static functions — no I/O, no SwiftData access.
enum PnLCalculator {

    // MARK: - FX

    static func lookupFx(_ fxRates: [String: Double], from: String, to: String) -> Double {
        guard from != to else { return 1.0 }
        let pair = "\(from)/\(to)"
        let inv  = "\(to)/\(from)"
        if let rate = fxRates[pair] { return rate }
        if let rate = fxRates[inv], rate != 0 { return 1.0 / rate }
        return 1.0
    }

    // MARK: - Spot Price

    /// Returns the effective spot price for a position given its category.
    /// GIC accrues interest; Cash/Dividend fixed at cost; Equity uses market price.
    static func spotPrice(
        category: Category,
        costPerShare: Double,
        yieldRate: Double?,
        dateAdded: Date,
        asOf: Date,
        marketPrice: Double?
    ) -> Double {
        switch category {
        case .cash, .dividend:
            return costPerShare
        case .gic:
            let days = Calendar.current.dateComponents([.day], from: dateAdded, to: asOf).day ?? 0
            return costPerShare * (1 + (yieldRate ?? 0) * Double(days) / 365.0)
        case .equity:
            return marketPrice ?? costPerShare
        }
    }

    // MARK: - Enrich single position

    static func enrich(
        position: Position,
        account: Account,
        marketPrice: Double?,
        fxRates: [String: Double],
        reportingCurrency: String,
        asOf: Date = Date()
    ) -> EnrichedPosition {
        guard let cat = Category(rawValue: position.category) else {
            fatalError("Unknown category: \(position.category)")
        }

        let acctCurrency  = account.baseCurrency.uppercased()
        let stockCurrency = position.currency.uppercased()
        let repCurrency   = reportingCurrency.uppercased()

        let spot = spotPrice(
            category: cat,
            costPerShare: position.costPerShare,
            yieldRate: position.yieldRate,
            dateAdded: position.dateAdded,
            asOf: asOf,
            marketPrice: marketPrice
        )

        let fxStockToAccount    = lookupFx(fxRates, from: stockCurrency, to: acctCurrency)
        let fxAccountToReporting = lookupFx(fxRates, from: acctCurrency, to: repCurrency)

        let mtmAccount  = spot * position.quantity * fxStockToAccount
        let pnlAccount  = (spot - position.costPerShare) * position.quantity * fxStockToAccount
        let mtmReporting = mtmAccount * fxAccountToReporting
        let pnlReporting = pnlAccount * fxAccountToReporting

        return EnrichedPosition(
            id: position.id,
            symbol: position.symbol,
            category: cat,
            accountId: account.id,
            accountName: account.name,
            accountCurrency: acctCurrency,
            quantity: position.quantity,
            costPerShare: position.costPerShare,
            dateAdded: position.dateAdded,
            yieldRate: position.yieldRate,
            stockCurrency: stockCurrency,
            spotPrice: spot,
            fxStockToAccount: fxStockToAccount,
            fxAccountToReporting: fxAccountToReporting,
            mtmAccount: mtmAccount,
            pnlAccount: pnlAccount,
            mtmReporting: mtmReporting,
            pnlReporting: pnlReporting,
            proportion: 0
        )
    }

    // MARK: - Enrich all positions

    static func enrichAll(
        positions: [Position],
        accounts: [UUID: Account],
        prices: [String: Double],
        fxRates: [String: Double],
        reportingCurrency: String,
        asOf: Date = Date()
    ) -> [EnrichedPosition] {
        var enriched = positions.compactMap { position -> EnrichedPosition? in
            guard let account = position.account else { return nil }
            return enrich(
                position: position,
                account: account,
                marketPrice: prices[position.symbol],
                fxRates: fxRates,
                reportingCurrency: reportingCurrency,
                asOf: asOf
            )
        }

        let totalMTM = enriched.reduce(0) { $0 + $1.mtmReporting }
        if totalMTM > 0 {
            for i in enriched.indices {
                enriched[i].proportion = (enriched[i].mtmReporting / totalMTM) * 100.0
            }
        }
        return enriched
    }

    // MARK: - Build groups

    static func buildGroups(
        enriched: [EnrichedPosition],
        groupBy: GroupBy,
        sectorMappings: [String: String]
    ) -> [SummaryGroup] {
        var groupMap: [String: (mtm: Double, pnl: Double)] = [:]
        let totalMTM = enriched.reduce(0) { $0 + $1.mtmReporting }

        for e in enriched {
            let key: String
            switch groupBy {
            case .category:
                // Merge Cash and GIC into one group
                key = (e.category == .cash || e.category == .gic) ? "Cash + GIC" : e.category.rawValue
            case .account:
                key = e.accountName
            case .sector:
                key = sectorMappings[e.symbol] ?? "Unspecified"
            }
            let existing = groupMap[key] ?? (0, 0)
            groupMap[key] = (existing.mtm + e.mtmReporting, existing.pnl + e.pnlReporting)
        }

        return groupMap.map { key, value in
            SummaryGroup(
                groupKey: key,
                totalMTM: value.mtm,
                totalPnL: value.pnl,
                proportion: totalMTM > 0 ? (value.mtm / totalMTM) * 100.0 : 0
            )
        }.sorted { $0.totalMTM > $1.totalMTM }
    }

    // MARK: - Historical PnL

    /// Reconstruct historical PnL for a set of equity positions given daily price data.
    /// - Parameters:
    ///   - priceHistory: [cacheKey: [Date: closePrice]]
    ///   - fxHistory: [pair: [Date: rate]] — per-date FX, falls back to latestFx
    ///   - latestFx: spot FX rates for fallback
    static func computeHistoricalPnL(
        equityPositions: [Position],
        accounts: [UUID: Account],
        priceHistory: [String: [Date: Double]],
        fxHistory: [String: [Date: Double]],
        latestFx: [String: Double],
        reportingCurrency: String
    ) -> [HistoryPoint] {
        guard !equityPositions.isEmpty else { return [] }

        let repCurrency = reportingCurrency.uppercased()

        // Group by symbol
        var symGroups: [String: [Position]] = [:]
        for p in equityPositions {
            symGroups[p.symbol, default: []].append(p)
        }

        // All dates across all symbols
        let allDates = Set(priceHistory.values.flatMap { $0.keys }).sorted()
        guard !allDates.isEmpty else { return [] }

        func fxOnDate(_ from: String, _ to: String, _ dt: Date) -> Double {
            if from == to { return 1.0 }
            let key = "\(from)/\(to)"
            let inv = "\(to)/\(from)"
            if let rate = fxHistory[key]?[dt], rate > 0 { return rate }
            if let rate = fxHistory[inv]?[dt], rate > 0 { return 1.0 / rate }
            return lookupFx(latestFx, from: from, to: to)
        }

        var combined: [Date: (pnl: Double, mtm: Double)] = [:]

        for (symbol, positions) in symGroups {
            guard let prices = priceHistory[symbol], !prices.isEmpty else { continue }

            let totalQty  = positions.reduce(0) { $0 + $1.quantity }
            let avgCost   = positions.reduce(0) { $0 + $1.quantity * $1.costPerShare } / totalQty
            let stockCcy  = positions[0].currency.uppercased()
            let acctCcy   = (positions[0].account?.baseCurrency ?? repCurrency).uppercased()

            // Forward-fill prices across all dates
            var lastPrice: Double? = nil
            for dt in allDates {
                if let p = prices[dt] { lastPrice = p }
                guard let close = lastPrice else { continue }
                let fx = fxOnDate(stockCcy, acctCcy, dt) * fxOnDate(acctCcy, repCurrency, dt)
                combined[dt, default: (0, 0)].pnl += (close - avgCost) * totalQty * fx
                combined[dt, default: (0, 0)].mtm += close * totalQty * fx
            }
        }

        return combined
            .sorted { $0.key < $1.key }
            .map { dt, v in HistoryPoint(date: dt, pnl: v.pnl, mtm: v.mtm) }
    }
}
