import Foundation
import SwiftData

@Model
final class SectorMapping {
    var symbol: String
    var sector: String

    init(symbol: String, sector: String = "Unspecified") {
        self.symbol = symbol
        self.sector = sector
    }
}
