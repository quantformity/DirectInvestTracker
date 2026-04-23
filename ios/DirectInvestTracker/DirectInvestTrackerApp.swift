import SwiftUI
import SwiftData
import BackgroundTasks

@main
struct DirectInvestTrackerApp: App {

    let modelContainer: ModelContainer
    let appContainer: AppContainer

    init() {
        let schema = Schema([
            Account.self,
            Position.self,
            MarketData.self,
            FxRate.self,
            SectorMapping.self,
            PriceCache.self,
            AppSettings.self,
        ])
        let config = ModelConfiguration("DirectInvestTracker", schema: schema)
        do {
            let container = try ModelContainer(for: schema, configurations: config)
            self.modelContainer = container
            // AppContainer must be created on the main actor — defer to the body
            self.appContainer = AppContainer(modelContainer: container)
        } catch {
            fatalError("Failed to create ModelContainer: \(error)")
        }

        // Register background refresh task
        MarketDataBackgroundTask.register(container: modelContainer)
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .modelContainer(modelContainer)
                .environment(appContainer)
                .onReceive(NotificationCenter.default.publisher(for: UIApplication.didEnterBackgroundNotification)) { _ in
                    MarketDataBackgroundTask.schedule()
                }
        }
    }
}
