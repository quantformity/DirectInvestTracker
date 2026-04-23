import BackgroundTasks
import SwiftData

enum MarketDataBackgroundTask {

    static let identifier = "com.quantformity.directinvest.marketrefresh"

    /// Call from App.init / onAppear to register the handler.
    static func register(container: ModelContainer) {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: identifier, using: nil) { task in
            guard let refreshTask = task as? BGAppRefreshTask else { return }
            handle(refreshTask: refreshTask, container: container)
        }
    }

    /// Schedule the next background refresh (call when app goes to background).
    static func schedule() {
        let request = BGAppRefreshTaskRequest(identifier: identifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 60 * 60) // 1 hour
        try? BGTaskScheduler.shared.submit(request)
    }

    private static func handle(refreshTask: BGAppRefreshTask, container: ModelContainer) {
        // Schedule the next one immediately
        schedule()

        let task = Task {
            let context = ModelContext(container)
            let yahoo   = YahooFinanceService()
            let fx      = FxService(yahoo: yahoo)

            let positions = (try? context.fetch(FetchDescriptor<Position>())) ?? []
            let accounts  = (try? context.fetch(FetchDescriptor<Account>())) ?? []

            // Fetch prices
            let symbols = positions
                .filter { $0.category == Category.equity.rawValue }
                .map { $0.symbol }
                .uniqued()

            if !symbols.isEmpty {
                if let quotes = try? await yahoo.fetchPrices(symbols: symbols) {
                    for (symbol, quote) in quotes {
                        let md = MarketData(
                            symbol: symbol,
                            companyName: quote.companyName,
                            lastPrice: quote.lastPrice,
                            peRatio: quote.peRatio,
                            changePercent: quote.changePercent,
                            beta: quote.beta
                        )
                        context.insert(md)
                    }
                }
            }

            // Fetch FX rates
            if let fxRates = try? await fx.refreshAllRates(positions: positions, accounts: accounts) {
                for (pair, rate) in fxRates {
                    context.insert(FxRate(pair: pair, rate: rate))
                }
            }

            try? context.save()
            AppSettingsStore.lastRefreshDate = Date()
            refreshTask.setTaskCompleted(success: true)
        }

        refreshTask.expirationHandler = {
            task.cancel()
        }
    }
}

private extension Array where Element: Hashable {
    func uniqued() -> [Element] {
        var seen = Set<Element>()
        return filter { seen.insert($0).inserted }
    }
}
