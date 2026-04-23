import Foundation

protocol YahooFinanceServiceProtocol {
    func fetchPrices(symbols: [String]) async throws -> [String: MarketQuote]
    func fetchFxRates(pairs: [(String, String)]) async throws -> [String: Double]
    func fetchHistory(symbol: String, from startDate: Date) async throws -> [Date: Double]
}

struct MarketQuote {
    let lastPrice: Double?
    let previousClose: Double?
    let changePercent: Double?
    let changePercentSource: String?   // "api", "chart", or "derived"
    let peRatio: Double?
    let beta: Double?
    let companyName: String?
}
