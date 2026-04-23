import Foundation
import SwiftData

@Model
final class MarketData {
    var id: UUID
    var symbol: String
    var companyName: String?
    var lastPrice: Double?
    var previousClose: Double?
    var peRatio: Double?
    var changePercent: Double?
    /// "api" = regularMarketChangePercent, "chart" = chart fallback, "derived" = computed from prices
    var changePercentSource: String?
    var beta: Double?
    var timestamp: Date

    init(
        symbol: String,
        companyName: String? = nil,
        lastPrice: Double? = nil,
        previousClose: Double? = nil,
        peRatio: Double? = nil,
        changePercent: Double? = nil,
        changePercentSource: String? = nil,
        beta: Double? = nil,
        timestamp: Date = Date()
    ) {
        self.id = UUID()
        self.symbol = symbol
        self.companyName = companyName
        self.lastPrice = lastPrice
        self.previousClose = previousClose
        self.peRatio = peRatio
        self.changePercent = changePercent
        self.changePercentSource = changePercentSource
        self.beta = beta
        self.timestamp = timestamp
    }
}
