import Foundation
import SwiftData
import Observation

/// Holds all service singletons — injected as an environment value.
@Observable
class AppContainer {
    let yahoo: YahooFinanceService
    let fxService: FxService
    let historyService: HistoryService
    let refreshService: MarketDataRefreshService

    private let modelContext: ModelContext
    private var autoRefreshTask: Task<Void, Never>? = nil

    static let autoRefreshInterval: TimeInterval = 5 * 60   // 5 minutes

    @MainActor
    init(modelContainer: ModelContainer) {
        let yahoo = YahooFinanceService()
        let fx    = FxService(yahoo: yahoo)
        let ctx   = ModelContext(modelContainer)

        self.yahoo          = yahoo
        self.fxService      = fx
        self.modelContext   = ctx
        self.historyService = HistoryService(yahoo: yahoo, modelContext: ctx)
        self.refreshService = MarketDataRefreshService(yahoo: yahoo, fxService: fx, modelContext: ctx)

        if AppSettingsStore.autoRefreshEnabled {
            startAutoRefresh()
        }
    }

    // MARK: - Auto-refresh

    @MainActor
    func setAutoRefresh(enabled: Bool) {
        AppSettingsStore.autoRefreshEnabled = enabled
        if enabled {
            startAutoRefresh()
        } else {
            stopAutoRefresh()
        }
    }

    @MainActor
    private func startAutoRefresh() {
        stopAutoRefresh()
        autoRefreshTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: UInt64(AppContainer.autoRefreshInterval * 1_000_000_000))
                guard !Task.isCancelled, let self else { break }
                await self.runAutoRefresh()
            }
        }
    }

    private func stopAutoRefresh() {
        autoRefreshTask?.cancel()
        autoRefreshTask = nil
    }

    @MainActor
    private func runAutoRefresh() async {
        let positions = (try? modelContext.fetch(FetchDescriptor<Position>())) ?? []
        let accounts  = (try? modelContext.fetch(FetchDescriptor<Account>()))  ?? []
        await refreshService.refresh(positions: positions, accounts: accounts)
    }
}
