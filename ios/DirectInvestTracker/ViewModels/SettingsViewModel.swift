import Foundation
import SwiftData
import SwiftUI

@MainActor
@Observable
class SettingsViewModel {

    var reportingCurrency: String = AppSettingsStore.reportingCurrency
    var sectorMappings: [SectorMapping] = []
    var lastRefreshDate: Date? = AppSettingsStore.lastRefreshDate
    var errorMessage: String? = nil

    private let modelContext: ModelContext
    private let refreshService: MarketDataRefreshService

    init(modelContext: ModelContext, refreshService: MarketDataRefreshService) {
        self.modelContext = modelContext
        self.refreshService = refreshService
        fetchSectorMappings()
    }

    func saveReportingCurrency() {
        AppSettingsStore.reportingCurrency = reportingCurrency
    }

    func fetchSectorMappings() {
        sectorMappings = (try? modelContext.fetch(FetchDescriptor<SectorMapping>(sortBy: [SortDescriptor(\.symbol)]))) ?? []
    }

    func addSectorMapping(symbol: String, sector: String) {
        let mapping = SectorMapping(symbol: symbol.uppercased(), sector: sector)
        modelContext.insert(mapping)
        save()
    }

    func updateSectorMapping(_ mapping: SectorMapping, sector: String) {
        mapping.sector = sector
        save()
    }

    func deleteSectorMapping(_ mapping: SectorMapping) {
        modelContext.delete(mapping)
        save()
    }

    func triggerManualRefresh() async {
        let positions = (try? modelContext.fetch(FetchDescriptor<Position>())) ?? []
        let accounts  = (try? modelContext.fetch(FetchDescriptor<Account>())) ?? []
        await refreshService.refresh(positions: positions, accounts: accounts)
        lastRefreshDate = AppSettingsStore.lastRefreshDate
    }

    var isRefreshing: Bool { refreshService.isRefreshing }

    private func save() {
        do {
            try modelContext.save()
            fetchSectorMappings()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
