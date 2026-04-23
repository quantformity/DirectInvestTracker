import Foundation
import SwiftData
import SwiftUI

@MainActor
@Observable
class SummaryViewModel {

    var enrichedPositions: [EnrichedPosition] = []
    var groups: [SummaryGroup] = []
    var totalMTM: Double = 0
    var totalPnL: Double = 0
    var selectedGroupBy: GroupBy = .category
    var isLoading = false
    var errorMessage: String? = nil

    private let modelContext: ModelContext

    init(modelContext: ModelContext) {
        self.modelContext = modelContext
    }

    func load() {
        isLoading = true
        defer { isLoading = false }

        let positions = (try? modelContext.fetch(FetchDescriptor<Position>())) ?? []
        let accounts  = Dictionary(
            uniqueKeysWithValues: ((try? modelContext.fetch(FetchDescriptor<Account>())) ?? []).map { ($0.id, $0) }
        )
        let prices    = latestPrices()
        let fxRates   = latestFxRates()
        let reporting = AppSettingsStore.reportingCurrency

        enrichedPositions = PnLCalculator.enrichAll(
            positions: positions,
            accounts: accounts,
            prices: prices,
            fxRates: fxRates,
            reportingCurrency: reporting
        )

        totalMTM = enrichedPositions.reduce(0) { $0 + $1.mtmReporting }
        totalPnL = enrichedPositions.reduce(0) { $0 + $1.pnlReporting }

        rebuildGroups()
    }

    func rebuildGroups() {
        let sectorMappings = loadSectorMappings()
        groups = PnLCalculator.buildGroups(
            enriched: enrichedPositions,
            groupBy: selectedGroupBy,
            sectorMappings: sectorMappings
        )
    }

    // MARK: - Helpers

    private func latestPrices() -> [String: Double] {
        let descriptor = FetchDescriptor<MarketData>(sortBy: [SortDescriptor(\.timestamp, order: .reverse)])
        let all = (try? modelContext.fetch(descriptor)) ?? []
        var result: [String: Double] = [:]
        for md in all {
            if result[md.symbol] == nil, let price = md.lastPrice {
                result[md.symbol] = price
            }
        }
        return result
    }

    private func latestFxRates() -> [String: Double] {
        let descriptor = FetchDescriptor<FxRate>(sortBy: [SortDescriptor(\.timestamp, order: .reverse)])
        let all = (try? modelContext.fetch(descriptor)) ?? []
        var result: [String: Double] = [:]
        for fx in all {
            if result[fx.pair] == nil {
                result[fx.pair] = fx.rate
            }
        }
        return result
    }

    private func loadSectorMappings() -> [String: String] {
        let all = (try? modelContext.fetch(FetchDescriptor<SectorMapping>())) ?? []
        return Dictionary(uniqueKeysWithValues: all.map { ($0.symbol, $0.sector) })
    }
}
