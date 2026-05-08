import Foundation
import SwiftData

struct FxService: FxServiceProtocol {

    private let yahoo: YahooFinanceService

    init(yahoo: YahooFinanceService) {
        self.yahoo = yahoo
    }

    func lookupFx(from: String, to: String, fxRates: [String: Double]) -> Double {
        PnLCalculator.lookupFx(fxRates, from: from, to: to)
    }

    /// Returns FX rate, checking SwiftData cache first. Fetches live from Yahoo Finance if not cached.
    @MainActor
    func ensuredRate(from: String, to: String, context: ModelContext) async -> Double {
        let f = from.uppercased(), t = to.uppercased()
        if f == t { return 1.0 }

        let rates = (try? context.fetch(FetchDescriptor<FxRate>())) ?? []
        if let r = rates.filter({ $0.pair == "\(f)/\(t)" }).max(by: { $0.timestamp < $1.timestamp }) {
            return r.rate
        }
        if let r = rates.filter({ $0.pair == "\(t)/\(f)" }).max(by: { $0.timestamp < $1.timestamp }), r.rate != 0 {
            return 1.0 / r.rate
        }

        let fetched = try? await yahoo.fetchFxRates(pairs: [(f, t)])
        if let rate = fetched?["\(f)/\(t)"] {
            let fxRecord = FxRate(pair: "\(f)/\(t)", rate: rate)
            context.insert(fxRecord)
            try? context.save()
            return rate
        }
        return 1.0
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

    static var linkedDatabaseBookmark: Data? {
        get { UserDefaults.standard.data(forKey: "linkedDatabaseBookmark") }
        set { UserDefaults.standard.set(newValue, forKey: "linkedDatabaseBookmark") }
    }

    static var lastSyncDate: Date? {
        get { UserDefaults.standard.object(forKey: "lastSyncDate") as? Date }
        set { UserDefaults.standard.set(newValue, forKey: "lastSyncDate") }
    }
}
