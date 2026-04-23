import Foundation

struct EnrichedPosition: Identifiable {
    let id: UUID
    let symbol: String
    let category: Category
    let accountId: UUID
    let accountName: String
    let accountCurrency: String
    let quantity: Double
    let costPerShare: Double
    let dateAdded: Date
    let yieldRate: Double?
    let stockCurrency: String
    let spotPrice: Double
    let fxStockToAccount: Double
    let fxAccountToReporting: Double
    let mtmAccount: Double
    let pnlAccount: Double
    let mtmReporting: Double
    let pnlReporting: Double
    var proportion: Double  // percentage of total MTM
}
