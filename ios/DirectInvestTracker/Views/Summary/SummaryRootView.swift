import SwiftUI
import SwiftData

struct SummaryRootView: View {
    @Environment(\.modelContext) private var modelContext

    @Query private var positions: [Position]
    @Query private var accounts: [Account]
    @Query(sort: \MarketData.timestamp, order: .reverse) private var marketData: [MarketData]
    @Query(sort: \FxRate.timestamp, order: .reverse) private var fxRates: [FxRate]
    @Query private var sectorMappings: [SectorMapping]

    @State private var selectedGroupBy: GroupBy = .category
    @State private var enrichedPositions: [EnrichedPosition] = []
    @State private var groups: [SummaryGroup] = []
    @State private var totalMTM: Double = 0
    @State private var totalPnL: Double = 0

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    headerCard

                    Picker("Group by", selection: $selectedGroupBy) {
                        ForEach(GroupBy.allCases) { g in
                            Text(g.displayName).tag(g)
                        }
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal)

                    ForEach(groups) { group in
                        SummaryCardView(
                            group: group,
                            reportingCurrency: AppSettingsStore.reportingCurrency,
                            positions: enrichedPositions.filter { matchesGroup($0, group: group) }
                        )
                    }
                }
                .padding(.vertical)
            }
            .navigationTitle("Summary")
            .onChange(of: selectedGroupBy) { _, _ in rebuildGroups() }
            .onChange(of: positions.count) { _, _ in recompute() }
            .onChange(of: marketData.count) { _, _ in recompute() }
            .onChange(of: fxRates.count) { _, _ in recompute() }
            .onAppear { recompute() }
        }
    }

    private var headerCard: some View {
        let currency = AppSettingsStore.reportingCurrency
        return VStack(spacing: 8) {
            Text("Total Portfolio")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Text(totalMTM.currencyFormatted(currency: currency))
                .font(.title.bold())
            PnLText(value: totalPnL, currency: currency)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal)
    }

    private func recompute() {
        let accountsMap = Dictionary(uniqueKeysWithValues: accounts.map { ($0.id, $0) })
        let prices      = latestPrices()
        let fx          = latestFxRates()

        let enriched = PnLCalculator.enrichAll(
            positions: positions,
            accounts: accountsMap,
            prices: prices,
            fxRates: fx,
            reportingCurrency: AppSettingsStore.reportingCurrency
        )
        totalMTM = enriched.reduce(0) { $0 + $1.mtmReporting }
        totalPnL = enriched.reduce(0) { $0 + $1.pnlReporting }
        enrichedPositions = enriched
        rebuildGroups()
    }

    private func rebuildGroups() {
        let sm = Dictionary(uniqueKeysWithValues: sectorMappings.map { ($0.symbol, $0.sector) })
        groups = PnLCalculator.buildGroups(enriched: enrichedPositions, groupBy: selectedGroupBy, sectorMappings: sm)
    }

    private func latestPrices() -> [String: Double] {
        var result: [String: Double] = [:]
        for md in marketData where result[md.symbol] == nil {
            if let p = md.lastPrice { result[md.symbol] = p }
        }
        return result
    }

    private func latestFxRates() -> [String: Double] {
        var result: [String: Double] = [:]
        for fx in fxRates where result[fx.pair] == nil { result[fx.pair] = fx.rate }
        return result
    }

    private func matchesGroup(_ pos: EnrichedPosition, group: SummaryGroup) -> Bool {
        switch selectedGroupBy {
        case .category:
            if group.groupKey == "Cash + GIC" {
                return pos.category == .cash || pos.category == .gic
            }
            return pos.category.rawValue == group.groupKey
        case .account:  return pos.accountName == group.groupKey
        case .sector:
            let sm = Dictionary(uniqueKeysWithValues: sectorMappings.map { ($0.symbol, $0.sector) })
            return (sm[pos.symbol] ?? "Unspecified") == group.groupKey
        }
    }
}
