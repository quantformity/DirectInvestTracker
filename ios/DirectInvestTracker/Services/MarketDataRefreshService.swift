import Foundation
import SwiftData

@MainActor
class MarketDataRefreshService: ObservableObject {

    @Published var isRefreshing = false
    @Published var lastError: String? = nil

    private let yahoo: YahooFinanceService
    private let fxService: FxService
    private let modelContext: ModelContext

    init(yahoo: YahooFinanceService, fxService: FxService, modelContext: ModelContext) {
        self.yahoo = yahoo
        self.fxService = fxService
        self.modelContext = modelContext
    }

    func refresh(positions: [Position], accounts: [Account]) async {
        guard !isRefreshing else { return }
        isRefreshing = true
        lastError = nil
        defer { isRefreshing = false }

        do {
            // Fetch equity prices
            let equitySymbols = positions
                .filter { $0.category == Category.equity.rawValue }
                .map { $0.symbol }
                .uniqued()

            if !equitySymbols.isEmpty {
                let quotes = try await yahoo.fetchPrices(symbols: equitySymbols)
                for (symbol, quote) in quotes {
                    let md = MarketData(
                        symbol: symbol,
                        companyName: quote.companyName,
                        lastPrice: quote.lastPrice,
                        previousClose: quote.previousClose,
                        peRatio: quote.peRatio,
                        changePercent: quote.changePercent,
                        changePercentSource: quote.changePercentSource,
                        beta: quote.beta
                    )
                    modelContext.insert(md)
                }
            }

            // Fetch FX rates
            let fxRates = try await fxService.refreshAllRates(positions: positions, accounts: accounts)
            for (pair, rate) in fxRates {
                let fx = FxRate(pair: pair, rate: rate)
                modelContext.insert(fx)
            }

            try modelContext.save()
            AppSettingsStore.lastRefreshDate = Date()

        } catch {
            lastError = error.localizedDescription
        }
    }
}

// MARK: - Array uniqued helper
private extension Array where Element: Hashable {
    func uniqued() -> [Element] {
        var seen = Set<Element>()
        return filter { seen.insert($0).inserted }
    }
}
