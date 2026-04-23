import Foundation
import SwiftData

@Model
final class FxRate {
    var id: UUID
    var pair: String   // e.g. "USD/CAD"
    var rate: Double
    var timestamp: Date

    init(pair: String, rate: Double, timestamp: Date = Date()) {
        self.id = UUID()
        self.pair = pair
        self.rate = rate
        self.timestamp = timestamp
    }
}
