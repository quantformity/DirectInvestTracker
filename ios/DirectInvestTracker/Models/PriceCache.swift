import Foundation
import SwiftData

/// Stores daily historical close prices for equities and FX pairs.
@Model
final class PriceCache {
    var id: UUID
    var cacheKey: String   // symbol or "USDCAD=X"
    var date: Date         // trading date (midnight UTC)
    var closePrice: Double

    init(cacheKey: String, date: Date, closePrice: Double) {
        self.id = UUID()
        self.cacheKey = cacheKey
        self.date = date
        self.closePrice = closePrice
    }
}
