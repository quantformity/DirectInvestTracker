import Foundation
import SwiftData

@Model
final class Position {
    var id: UUID
    var symbol: String
    var category: String  // CategoryEnum raw value
    var quantity: Double
    var costPerShare: Double
    var dateAdded: Date
    var yieldRate: Double?
    var currency: String

    var account: Account?

    init(
        symbol: String,
        category: String,
        quantity: Double,
        costPerShare: Double,
        dateAdded: Date = Date(),
        yieldRate: Double? = nil,
        currency: String = "CAD",
        account: Account? = nil
    ) {
        self.id = UUID()
        self.symbol = symbol
        self.category = category
        self.quantity = quantity
        self.costPerShare = costPerShare
        self.dateAdded = dateAdded
        self.yieldRate = yieldRate
        self.currency = currency
        self.account = account
    }
}
