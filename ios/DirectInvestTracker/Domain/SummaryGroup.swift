import Foundation

struct SummaryGroup: Identifiable {
    var id: String { groupKey }
    let groupKey: String
    let totalMTM: Double
    let totalPnL: Double
    let proportion: Double  // percentage of total MTM
}
