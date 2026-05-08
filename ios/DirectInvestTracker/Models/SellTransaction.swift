import Foundation
import SwiftData

@Model
final class SellTransaction {
    var id: UUID
    var accountId: Int          // mirrors pythonId of the account
    var accountName: String
    var symbol: String
    var category: String
    var quantity: Double
    var sellPrice: Double
    var costPerShare: Double
    var fee: Double
    var date: Date
    var stockCurrency: String
    var accountCurrency: String
    var realizedPnlStock: Double
    var realizedPnlAccount: Double
    var realizedPnlReporting: Double
    var fxStockToAccount: Double
    var fxAccountToReporting: Double
    var pythonId: Int?

    init(
        accountId: Int,
        accountName: String,
        symbol: String,
        category: String,
        quantity: Double,
        sellPrice: Double,
        costPerShare: Double,
        fee: Double,
        date: Date,
        stockCurrency: String,
        accountCurrency: String,
        realizedPnlStock: Double,
        realizedPnlAccount: Double,
        realizedPnlReporting: Double,
        fxStockToAccount: Double,
        fxAccountToReporting: Double
    ) {
        self.id = UUID()
        self.accountId = accountId
        self.accountName = accountName
        self.symbol = symbol
        self.category = category
        self.quantity = quantity
        self.sellPrice = sellPrice
        self.costPerShare = costPerShare
        self.fee = fee
        self.date = date
        self.stockCurrency = stockCurrency
        self.accountCurrency = accountCurrency
        self.realizedPnlStock = realizedPnlStock
        self.realizedPnlAccount = realizedPnlAccount
        self.realizedPnlReporting = realizedPnlReporting
        self.fxStockToAccount = fxStockToAccount
        self.fxAccountToReporting = fxAccountToReporting
    }
}
