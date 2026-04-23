import Foundation

struct FxService: FxServiceProtocol {

    private let yahoo: YahooFinanceService

    init(yahoo: YahooFinanceService) {
        self.yahoo = yahoo
    }

    func lookupFx(from: String, to: String, fxRates: [String: Double]) -> Double {
        PnLCalculator.lookupFx(fxRates, from: from, to: to)
    }

    /// Collect all unique FX pairs needed by positions/accounts, then fetch them.
    func refreshAllRates(positions: [Position], accounts: [Account]) async throws -> [String: Double] {
        let reportingCurrency = AppSettingsStore.reportingCurrency
        var pairs: Set<String> = []

        for position in positions {
            let stockCcy = position.currency.uppercased()
            let acctCcy  = (position.account?.baseCurrency ?? reportingCurrency).uppercased()
            let repCcy   = reportingCurrency.uppercased()

            if stockCcy != acctCcy {
                pairs.insert("\(stockCcy)/\(acctCcy)")
            }
            if acctCcy != repCcy {
                pairs.insert("\(acctCcy)/\(repCcy)")
            }
        }

        let pairsArray = pairs.map { pair -> (String, String) in
            let parts = pair.split(separator: "/").map(String.init)
            return (parts[0], parts[1])
        }

        return try await yahoo.fetchFxRates(pairs: pairsArray)
    }
}

/// Simple UserDefaults-backed settings store (no SwiftData needed for settings).
enum AppSettingsStore {
    static var reportingCurrency: String {
        get { UserDefaults.standard.string(forKey: "reportingCurrency") ?? "CAD" }
        set { UserDefaults.standard.set(newValue, forKey: "reportingCurrency") }
    }

    static var lastRefreshDate: Date? {
        get { UserDefaults.standard.object(forKey: "lastRefreshDate") as? Date }
        set { UserDefaults.standard.set(newValue, forKey: "lastRefreshDate") }
    }

    static var autoRefreshEnabled: Bool {
        get { UserDefaults.standard.bool(forKey: "autoRefreshEnabled") }
        set { UserDefaults.standard.set(newValue, forKey: "autoRefreshEnabled") }
    }
}
