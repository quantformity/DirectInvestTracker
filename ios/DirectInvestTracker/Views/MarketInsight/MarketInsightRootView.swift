import SwiftUI
import SwiftData

// MARK: - Per-account market insight data

private struct AccountInsight: Identifiable {
    let id: String      // account name
    let name: String
    var mtmReporting: Double
    var oneDayPnL: Double
    var overallPnL: Double
}

// MARK: - Per-symbol market insight data

private struct SymbolInsight: Identifiable {
    let id: String      // symbol
    var symbol: String
    var companyName: String
    var sector: String
    var lastPrice: Double?
    var changePercent: Double?
    var changePercentSource: String?   // "api", "chart", "derived", or nil
    var peRatio: Double?
    var beta: Double?
    var totalShares: Double
    var mtmReporting: Double
    var oneDayPnL: Double
    var overallPnL: Double
}

// MARK: - Root view

struct MarketInsightRootView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(AppContainer.self)  private var appContainer

    @Query private var positions: [Position]
    @Query private var accounts: [Account]
    @Query(sort: \MarketData.timestamp, order: .reverse) private var marketData: [MarketData]
    @Query(sort: \FxRate.timestamp, order: .reverse)    private var fxRates:    [FxRate]
    @Query private var sectorMappings: [SectorMapping]

    @State private var insights: [SymbolInsight] = []
    @State private var accountInsights: [AccountInsight] = []
    @State private var totalMTM:   Double = 0
    @State private var totalPnL:   Double = 0
    @State private var todayPnL:   Double = 0
    @State private var totalCash:  Double = 0
    @State private var totalGIC:   Double = 0
    @State private var isRefreshing = false
    @State private var errorMessage: String? = nil

    private let currency: String = AppSettingsStore.reportingCurrency

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    statCardsSection
                    if !insights.isEmpty {
                        barChartSection(
                            title: "MTM by Symbol",
                            data: insights.sorted { $0.mtmReporting > $1.mtmReporting },
                            valueKey: \.mtmReporting
                        )
                        barChartSection(
                            title: "1-Day PnL by Symbol",
                            data: insights.sorted { $0.oneDayPnL > $1.oneDayPnL },
                            valueKey: \.oneDayPnL
                        )
                        barChartSection(
                            title: "Overall PnL by Symbol",
                            data: insights.sorted { $0.overallPnL > $1.overallPnL },
                            valueKey: \.overallPnL
                        )
                        if accountInsights.count > 1 {
                            accountBarChartSection(
                                title: "MTM by Account",
                                data: accountInsights.sorted { $0.mtmReporting > $1.mtmReporting },
                                valueKey: \.mtmReporting
                            )
                            accountBarChartSection(
                                title: "1-Day PnL by Account",
                                data: accountInsights.sorted { $0.oneDayPnL > $1.oneDayPnL },
                                valueKey: \.oneDayPnL
                            )
                            accountBarChartSection(
                                title: "Overall PnL by Account",
                                data: accountInsights.sorted { $0.overallPnL > $1.overallPnL },
                                valueKey: \.overallPnL
                            )
                        }
                        marketCardsSection
                    }
                }
                .padding(.vertical)
            }
            .navigationTitle("Market Insight")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { Task { await refresh() } }) {
                        if isRefreshing {
                            ProgressView()
                        } else {
                            Image(systemName: "arrow.clockwise")
                        }
                    }
                    .disabled(isRefreshing)
                }
            }
            .onChange(of: positions.count)    { _, _ in recompute() }
            .onChange(of: marketData.count)   { _, _ in recompute() }
            .onChange(of: fxRates.count)      { _, _ in recompute() }
            .onAppear { recompute() }

            if let error = errorMessage {
                ErrorBannerView(message: error) { errorMessage = nil }
            }
        }
    }

    // MARK: - Stat cards

    private var statCardsSection: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            StatCard(title: "Total MTM",   value: totalMTM.currencyFormatted(currency: currency), isHighlight: false)
            StatCard(title: "Total PnL",   value: totalPnL.currencyFormatted(currency: currency), isPositive: totalPnL >= 0)
            StatCard(title: "Today's PnL", value: todayPnL.currencyFormatted(currency: currency), isPositive: todayPnL >= 0)
            StatCard(title: "Cash + GIC",  value: (totalCash + totalGIC).currencyFormatted(currency: currency), isHighlight: false)
        }
        .padding(.horizontal)
    }

    // MARK: - Ranked list

    private func barChartSection(
        title: String,
        data: [SymbolInsight],
        valueKey: KeyPath<SymbolInsight, Double>
    ) -> some View {
        let maxAbs = data.map { Swift.abs($0[keyPath: valueKey]) }.max() ?? 1

        return VStack(alignment: .leading, spacing: 0) {
            Text(title)
                .font(.headline)
                .padding(.horizontal)
                .padding(.bottom, 8)

            ForEach(Array(data.enumerated()), id: \.element.id) { index, item in
                rankedRow(rank: index + 1, item: item,
                          value: item[keyPath: valueKey], maxAbs: maxAbs)
                if index < data.count - 1 {
                    Divider().padding(.leading, 56)
                }
            }
        }
        .padding(.vertical, 12)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal)
    }

    private func rankedRow(rank: Int, item: SymbolInsight, value: Double, maxAbs: Double) -> some View {
        let positive  = value >= 0
        let barColor  = positive ? Color.green : Color.red
        let fraction  = maxAbs > 0 ? Swift.abs(value) / maxAbs : 0

        return VStack(alignment: .leading, spacing: 5) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text("#\(rank)")
                    .font(.caption2.bold())
                    .foregroundStyle(.tertiary)
                    .frame(width: 28, alignment: .trailing)

                Text(item.symbol)
                    .font(.subheadline.bold())

                Spacer()

                Text(compactValue(value))
                    .font(.subheadline.bold())
                    .foregroundStyle(positive ? .green : .red)
                    .monospacedDigit()
            }

            // Bar with company name inside
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(barColor.opacity(0.12))
                        .frame(maxWidth: .infinity)
                    RoundedRectangle(cornerRadius: 4)
                        .fill(LinearGradient(
                            colors: positive
                                ? [Color.green.opacity(0.5), Color.green.opacity(0.75)]
                                : [Color.red.opacity(0.5), Color.red.opacity(0.75)],
                            startPoint: .leading, endPoint: .trailing
                        ))
                        .frame(width: max(geo.size.width * fraction, 4))

                    Text(item.companyName)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .padding(.horizontal, 6)
                }
            }
            .frame(height: 16)
            .padding(.leading, 36)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
    }

    // MARK: - Account ranked list

    private func accountBarChartSection(
        title: String,
        data: [AccountInsight],
        valueKey: KeyPath<AccountInsight, Double>
    ) -> some View {
        let maxAbs = data.map { Swift.abs($0[keyPath: valueKey]) }.max() ?? 1

        return VStack(alignment: .leading, spacing: 0) {
            Text(title)
                .font(.headline)
                .padding(.horizontal)
                .padding(.bottom, 8)

            ForEach(Array(data.enumerated()), id: \.element.id) { index, item in
                accountRankedRow(rank: index + 1, name: item.name,
                                 value: item[keyPath: valueKey], maxAbs: maxAbs)
                if index < data.count - 1 {
                    Divider().padding(.leading, 56)
                }
            }
        }
        .padding(.vertical, 12)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal)
    }

    private func accountRankedRow(rank: Int, name: String, value: Double, maxAbs: Double) -> some View {
        let positive = value >= 0
        let barColor = positive ? Color.purple : Color.red
        let fraction = maxAbs > 0 ? Swift.abs(value) / maxAbs : 0

        return VStack(alignment: .leading, spacing: 5) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text("#\(rank)")
                    .font(.caption2.bold())
                    .foregroundStyle(.tertiary)
                    .frame(width: 28, alignment: .trailing)
                Text(name)
                    .font(.subheadline.bold())
                Spacer()
                Text(compactValue(value))
                    .font(.subheadline.bold())
                    .foregroundStyle(positive ? .purple : .red)
                    .monospacedDigit()
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(barColor.opacity(0.12))
                        .frame(maxWidth: .infinity)
                    RoundedRectangle(cornerRadius: 4)
                        .fill(LinearGradient(
                            colors: positive
                                ? [Color.purple.opacity(0.45), Color.purple.opacity(0.7)]
                                : [Color.red.opacity(0.5), Color.red.opacity(0.75)],
                            startPoint: .leading, endPoint: .trailing
                        ))
                        .frame(width: max(geo.size.width * fraction, 4))
                    Text(name)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .padding(.horizontal, 6)
                }
            }
            .frame(height: 16)
            .padding(.leading, 36)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
    }

    private func compactValue(_ v: Double) -> String {
        let abs = Swift.abs(v)
        let sign = v < 0 ? "-" : (v > 0 ? "+" : "")
        if abs >= 1_000_000 { return "\(sign)$\(String(format: "%.1f", abs/1_000_000))M" }
        if abs >= 1_000     { return "\(sign)$\(String(format: "%.1f", abs/1_000))K" }
        return "\(sign)$\(String(format: "%.0f", abs))"
    }

    // MARK: - Market cards grid

    private var marketCardsSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Market Cards")
                .font(.headline)
                .padding(.horizontal)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(insights.sorted { $0.symbol < $1.symbol }) { insight in
                    MarketCardView(insight: insight, currency: currency)
                }
            }
            .padding(.horizontal)
        }
    }

    // MARK: - Computation

    private func recompute() {
        let accountsMap = Dictionary(uniqueKeysWithValues: accounts.map { ($0.id, $0) })
        let prices      = latestPrices()
        let fx          = latestFxRates()
        let sm          = Dictionary(uniqueKeysWithValues: sectorMappings.map { ($0.symbol, $0.sector) })
        let mdMap       = latestMarketData()
        // Pick the first non-nil company name per symbol across all history (chart fallback has no name)
        var companyNames: [String: String] = [:]
        for md in marketData {
            if companyNames[md.symbol] == nil, let name = md.companyName, !name.isEmpty {
                companyNames[md.symbol] = name
            }
        }
        let today       = Calendar.current.startOfDay(for: Date())

        let enriched = PnLCalculator.enrichAll(
            positions: positions,
            accounts: accountsMap,
            prices: prices,
            fxRates: fx,
            reportingCurrency: currency
        )

        totalMTM  = enriched.reduce(0) { $0 + $1.mtmReporting }
        totalPnL  = enriched.reduce(0) { $0 + $1.pnlReporting }
        totalCash = enriched.filter { $0.category == .cash    }.reduce(0) { $0 + $1.mtmReporting }
        totalGIC  = enriched.filter { $0.category == .gic     }.reduce(0) { $0 + $1.mtmReporting }

        // Group equity positions by symbol
        var symGroups: [String: [EnrichedPosition]] = [:]
        for e in enriched where e.category == .equity {
            symGroups[e.symbol, default: []].append(e)
        }

        // Build per-symbol insights
        var result: [SymbolInsight] = []
        var todayTotal: Double = 0

        for (symbol, eps) in symGroups {
            let mtm     = eps.reduce(0) { $0 + $1.mtmReporting }
            let pnl     = eps.reduce(0) { $0 + $1.pnlReporting }
            let shares  = eps.reduce(0) { $0 + $1.quantity }
            let md      = mdMap[symbol]

            // 1-Day PnL = (changePercent / 100) × eligibleMTM
            // where eligibleMTM = sum of mtmReporting for positions not added today.
            // This matches the Python/Electron formula exactly.
            let eligibleMTM = eps
                .filter { Calendar.current.startOfDay(for: $0.dateAdded) < today }
                .reduce(0) { $0 + $1.mtmReporting }

            let oneDayPnL: Double
            if let pct = md?.changePercent {
                oneDayPnL = (pct / 100.0) * eligibleMTM
            } else {
                oneDayPnL = 0
            }

            todayTotal += oneDayPnL

            result.append(SymbolInsight(
                id: symbol,
                symbol: symbol,
                companyName: companyNames[symbol] ?? symbol,
                sector: sm[symbol] ?? "—",
                lastPrice: md?.lastPrice,
                changePercent: md?.changePercent,
                changePercentSource: md?.changePercentSource,
                peRatio: md?.peRatio,
                beta: md?.beta,
                totalShares: shares,
                mtmReporting: mtm,
                oneDayPnL: oneDayPnL,
                overallPnL: pnl
            ))
        }

        todayPnL = todayTotal
        insights = result

        // ── Account-level insights ────────────────────────────────────────────
        var accGroups: [String: [EnrichedPosition]] = [:]
        for e in enriched { accGroups[e.accountName, default: []].append(e) }

        accountInsights = accGroups.map { (accountName, eps) in
            let mtm = eps.reduce(0) { $0 + $1.mtmReporting }
            let pnl = eps.reduce(0) { $0 + $1.pnlReporting }

            // 1-Day PnL: sum equity symbols in this account
            let equityEps = eps.filter { $0.category == .equity }
            let equitySymbols = Set(equityEps.map { $0.symbol })
            let oneDayPnL = equitySymbols.reduce(0.0) { sum, symbol in
                guard let pct = mdMap[symbol]?.changePercent else { return sum }
                let eligible = equityEps
                    .filter { $0.symbol == symbol && Calendar.current.startOfDay(for: $0.dateAdded) < today }
                    .reduce(0) { $0 + $1.mtmReporting }
                return sum + (pct / 100.0) * eligible
            }

            return AccountInsight(id: accountName, name: accountName,
                                  mtmReporting: mtm, oneDayPnL: oneDayPnL, overallPnL: pnl)
        }
    }

    private func latestPrices() -> [String: Double] {
        var r: [String: Double] = [:]
        for md in marketData where r[md.symbol] == nil {
            if let p = md.lastPrice { r[md.symbol] = p }
        }
        return r
    }

    private func latestFxRates() -> [String: Double] {
        var r: [String: Double] = [:]
        for fx in fxRates where r[fx.pair] == nil { r[fx.pair] = fx.rate }
        return r
    }

    private func latestMarketData() -> [String: MarketData] {
        var r: [String: MarketData] = [:]
        for md in marketData where r[md.symbol] == nil { r[md.symbol] = md }
        return r
    }

    private func refresh() async {
        isRefreshing = true
        defer { isRefreshing = false }
        let pos  = (try? modelContext.fetch(FetchDescriptor<Position>())) ?? []
        let accs = (try? modelContext.fetch(FetchDescriptor<Account>()))  ?? []
        await appContainer.refreshService.refresh(positions: pos, accounts: accs)
        recompute()
        if let err = appContainer.refreshService.lastError { errorMessage = err }
    }
}

// MARK: - Stat card

private struct StatCard: View {
    let title: String
    let value: String
    var isHighlight: Bool = false
    var isPositive: Bool? = nil   // nil = neutral

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.subheadline.bold())
                .foregroundStyle(foreground)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private var foreground: Color {
        if let pos = isPositive { return pos ? .green : .red }
        return .primary
    }
}

// MARK: - Market card

private struct MarketCardView: View {
    let insight: SymbolInsight
    let currency: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            // Header: symbol + sector badge
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(insight.symbol)
                        .font(.subheadline.bold())
                    Text(insight.companyName)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                Spacer()
                Text(insight.sector)
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.accentColor.opacity(0.15))
                    .clipShape(Capsule())
            }

            Divider()

            // Price + change
            HStack(alignment: .firstTextBaseline) {
                if let price = insight.lastPrice {
                    Text(price.currencyFormatted(currency: "USD", maximumFractionDigits: 2))
                        .font(.title3.bold())
                } else {
                    Text("—").font(.title3).foregroundStyle(.secondary)
                }
                Spacer()
                if let chg = insight.changePercent {
                    HStack(spacing: 2) {
                        Text(String(format: "%+.2f%%", chg))
                            .font(.caption.bold())
                            .foregroundStyle(chg >= 0 ? .green : .red)
                        if let src = insight.changePercentSource, src != "api" {
                            Image(systemName: src == "chart" ? "chart.bar" : "function")
                                .font(.system(size: 8))
                                .foregroundStyle(.secondary)
                                .help(src == "chart" ? "From chart endpoint" : "Derived from prices")
                        }
                    }
                }
            }

            // Metrics grid
            Group {
                metricRow(label: "Shares", value: insight.totalShares > 0
                    ? insight.totalShares.formatted(.number.precision(.fractionLength(0...4)))
                    : "—")
                metricRow(label: "MTM",  value: insight.mtmReporting.currencyFormatted(currency: currency, maximumFractionDigits: 0))
                metricRow(label: "P/E",  value: insight.peRatio.map { String(format: "%.1f", $0) } ?? "—")
                metricRow(label: "Beta", value: insight.beta.map { String(format: "%.2f", $0) } ?? "—")
                metricRow(label: "Day",  value: dayPnLString, highlight: insight.oneDayPnL >= 0 ? .green : .red)
                metricRow(label: "PnL",  value: totalPnLString, highlight: insight.overallPnL >= 0 ? .green : .red)
            }
        }
        .padding(12)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var dayPnLString: String {
        let prefix = insight.oneDayPnL >= 0 ? "+" : ""
        return prefix + insight.oneDayPnL.currencyFormatted(currency: currency, maximumFractionDigits: 0)
    }

    private var totalPnLString: String {
        let prefix = insight.overallPnL >= 0 ? "+" : ""
        return prefix + insight.overallPnL.currencyFormatted(currency: currency, maximumFractionDigits: 0)
    }

    private func metricRow(label: String, value: String, highlight: Color? = nil) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 9))
                .foregroundStyle(.secondary)
                .frame(width: 36, alignment: .leading)
            Text(value)
                .font(.system(size: 9, weight: .semibold))
                .foregroundStyle(highlight ?? .primary)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
    }
}
