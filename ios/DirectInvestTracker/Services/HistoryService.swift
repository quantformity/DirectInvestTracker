import Foundation
import SwiftData

actor HistoryService: @preconcurrency HistoryServiceProtocol {

    private let yahoo: YahooFinanceService
    private let modelContext: ModelContext

    init(yahoo: YahooFinanceService, modelContext: ModelContext) {
        self.yahoo = yahoo
        self.modelContext = modelContext
    }

    // MARK: - Cache helpers

    private func readCache(cacheKey: String, from startDate: Date) -> [Date: Double] {
        let descriptor = FetchDescriptor<PriceCache>(
            predicate: #Predicate { $0.cacheKey == cacheKey && $0.date >= startDate }
        )
        let rows = (try? modelContext.fetch(descriptor)) ?? []
        return Dictionary(uniqueKeysWithValues: rows.map { ($0.date, $0.closePrice) })
    }

    private func writeCache(cacheKey: String, prices: [Date: Double]) {
        // Remove existing rows for this key to avoid duplicates
        let descriptor = FetchDescriptor<PriceCache>(
            predicate: #Predicate { $0.cacheKey == cacheKey }
        )
        let existing = (try? modelContext.fetch(descriptor)) ?? []
        existing.forEach { modelContext.delete($0) }

        for (date, price) in prices {
            let row = PriceCache(cacheKey: cacheKey, date: date, closePrice: price)
            modelContext.insert(row)
        }
        try? modelContext.save()
    }

    // MARK: - Symbol history (cache-first)

    func symbolHistory(symbol: String, positions: [Position], useCache: Bool) async throws -> [Date: Double] {
        let earliest = positions.map { $0.dateAdded }.min() ?? Date()
        return try await symbolHistoryInternal(symbol: symbol, from: earliest, useCache: useCache)
    }

    private func symbolHistoryInternal(symbol: String, from startDate: Date, useCache: Bool) async throws -> [Date: Double] {
        if useCache {
            return readCache(cacheKey: symbol, from: startDate)
        }
        let prices = try await yahoo.fetchHistory(symbol: symbol, from: startDate)
        if !prices.isEmpty {
            writeCache(cacheKey: symbol, prices: prices)
        }
        return prices
    }

    // MARK: - Aggregate history

    func aggregateHistory(
        positions: [Position],
        accounts: [UUID: Account],
        latestFx: [String: Double],
        reportingCurrency: String,
        useCache: Bool
    ) async throws -> [HistoryPoint] {
        let equityPositions = positions.filter { $0.category == Category.equity.rawValue }
        guard !equityPositions.isEmpty else { return [] }

        let overall = equityPositions.map { $0.dateAdded }.min() ?? Date()

        // Determine needed FX pairs
        var fxPairsNeeded: Set<String> = []
        for p in equityPositions {
            let stockCcy = p.currency.uppercased()
            let acctCcy  = (p.account?.baseCurrency ?? reportingCurrency).uppercased()
            if stockCcy != acctCcy { fxPairsNeeded.insert("\(stockCcy)/\(acctCcy)") }
            if acctCcy != reportingCurrency { fxPairsNeeded.insert("\(acctCcy)/\(reportingCurrency)") }
        }

        // Fetch FX history
        var fxHistory: [String: [Date: Double]] = [:]
        for pair in fxPairsNeeded {
            let parts = pair.split(separator: "/").map(String.init)
            guard parts.count == 2 else { continue }
            let fxSymbol = "\(parts[0])\(parts[1])=X"
            try await Task.sleep(nanoseconds: 300_000_000)
            let prices = try await symbolHistoryInternal(symbol: fxSymbol, from: overall, useCache: useCache)
            fxHistory[pair] = prices
        }

        // Group by symbol and fetch price history
        var symGroups: [String: [Position]] = [:]
        for p in equityPositions { symGroups[p.symbol, default: []].append(p) }

        var priceHistory: [String: [Date: Double]] = [:]
        for (i, (symbol, symPositions)) in symGroups.enumerated() {
            if i > 0 { try await Task.sleep(nanoseconds: 300_000_000) }
            let earliest = symPositions.map { $0.dateAdded }.min() ?? Date()
            let prices = try await symbolHistoryInternal(symbol: symbol, from: earliest, useCache: useCache)
            priceHistory[symbol] = prices
        }

        // Add Cash/GIC positions on top
        var points = PnLCalculator.computeHistoricalPnL(
            equityPositions: equityPositions,
            accounts: accounts,
            priceHistory: priceHistory,
            fxHistory: fxHistory,
            latestFx: latestFx,
            reportingCurrency: reportingCurrency
        )

        // Attach cash/GIC
        let nonEquity = positions.filter {
            $0.category == Category.cash.rawValue || $0.category == Category.gic.rawValue
        }
        let allDates = points.map { $0.date }
        var cashGICByDate: [Date: Double] = [:]
        for pos in nonEquity {
            let acctCcy = (pos.account?.baseCurrency ?? reportingCurrency).uppercased()
            let posCcy  = pos.currency.uppercased()
            let cat     = Category(rawValue: pos.category) ?? .cash
            for dt in allDates {
                guard dt >= pos.dateAdded else { continue }
                let spot: Double
                if cat == .cash {
                    spot = pos.costPerShare
                } else {
                    let days = Calendar.current.dateComponents([.day], from: pos.dateAdded, to: dt).day ?? 0
                    spot = pos.costPerShare * (1 + (pos.yieldRate ?? 0) * Double(days) / 365.0)
                }
                let fx = PnLCalculator.lookupFx(latestFx, from: posCcy, to: acctCcy)
                      * PnLCalculator.lookupFx(latestFx, from: acctCcy, to: reportingCurrency)
                cashGICByDate[dt, default: 0] += spot * pos.quantity * fx
            }
        }

        points = points.map { p in
            HistoryPoint(date: p.date, pnl: p.pnl, mtm: p.mtm + (cashGICByDate[p.date] ?? 0), cashGIC: cashGICByDate[p.date] ?? 0)
        }
        return points
    }
}
