import Foundation
import SwiftData
import SwiftUI

enum HistoryMode: String, CaseIterable, Identifiable {
    case portfolio = "Portfolio"
    case account   = "Account"
    case symbol    = "Symbol"
    case sector    = "Sector"

    var id: String { rawValue }
}

@MainActor
@Observable
class HistoryViewModel {

    var points: [HistoryPoint] = []
    var mode: HistoryMode = .portfolio
    var selectedAccountId: UUID? = nil
    var selectedSymbol: String? = nil
    var selectedSector: String? = nil
    var isLoading = false
    var errorMessage: String? = nil

    private let modelContext: ModelContext
    private var historyService: HistoryService? = nil

    init(modelContext: ModelContext) {
        self.modelContext = modelContext
    }

    func setup(historyService: HistoryService) {
        self.historyService = historyService
    }

    var peakPoint: HistoryPoint? { points.max(by: { $0.mtm < $1.mtm }) }
    var troughPoint: HistoryPoint? { points.min(by: { $0.mtm < $1.mtm }) }

    func load(useCache: Bool = true) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        guard let service = historyService else { return }

        let allPositions = (try? modelContext.fetch(FetchDescriptor<Position>())) ?? []
        let allAccounts  = (try? modelContext.fetch(FetchDescriptor<Account>())) ?? []
        let accountsMap  = Dictionary(uniqueKeysWithValues: allAccounts.map { ($0.id, $0) })
        let latestFx     = latestFxRates()
        let reporting    = AppSettingsStore.reportingCurrency

        do {
            switch mode {
            case .portfolio:
                points = try await service.aggregateHistory(
                    positions: allPositions,
                    accounts: accountsMap,
                    latestFx: latestFx,
                    reportingCurrency: reporting,
                    useCache: useCache
                )

            case .account:
                guard let accountId = selectedAccountId else { return }
                let filtered = allPositions.filter { $0.account?.id == accountId }
                points = try await service.aggregateHistory(
                    positions: filtered,
                    accounts: accountsMap,
                    latestFx: latestFx,
                    reportingCurrency: reporting,
                    useCache: useCache
                )

            case .symbol:
                guard let symbol = selectedSymbol else { return }
                let filtered = allPositions.filter {
                    $0.symbol == symbol && $0.category == Category.equity.rawValue
                }
                let priceHistory = try await service.symbolHistory(symbol: symbol, positions: filtered, useCache: useCache)
                let totalQty  = filtered.reduce(0) { $0 + $1.quantity }
                let avgCost   = totalQty > 0 ? filtered.reduce(0) { $0 + $1.quantity * $1.costPerShare } / totalQty : 0
                points = priceHistory.sorted { $0.key < $1.key }.map { dt, close in
                    HistoryPoint(date: dt, pnl: (close - avgCost) * totalQty, mtm: close * totalQty)
                }

            case .sector:
                guard let sector = selectedSector else { return }
                let sectorMappings = loadSectorMappings()
                let filtered = allPositions.filter {
                    $0.category == Category.equity.rawValue &&
                    (sectorMappings[$0.symbol] ?? "Unspecified") == sector
                }
                points = try await service.aggregateHistory(
                    positions: filtered,
                    accounts: accountsMap,
                    latestFx: latestFx,
                    reportingCurrency: reporting,
                    useCache: useCache
                )
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    // MARK: - Helpers

    private func latestFxRates() -> [String: Double] {
        let descriptor = FetchDescriptor<FxRate>(sortBy: [SortDescriptor(\.timestamp, order: .reverse)])
        let all = (try? modelContext.fetch(descriptor)) ?? []
        var result: [String: Double] = [:]
        for fx in all where result[fx.pair] == nil { result[fx.pair] = fx.rate }
        return result
    }

    private func loadSectorMappings() -> [String: String] {
        let all = (try? modelContext.fetch(FetchDescriptor<SectorMapping>())) ?? []
        return Dictionary(uniqueKeysWithValues: all.map { ($0.symbol, $0.sector) })
    }
}
