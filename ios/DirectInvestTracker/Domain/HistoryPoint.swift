import Foundation

struct HistoryPoint: Identifiable {
    let id: UUID
    let date: Date
    let pnl: Double
    let mtm: Double
    let cashGIC: Double

    init(date: Date, pnl: Double, mtm: Double, cashGIC: Double = 0) {
        self.id = UUID()
        self.date = date
        self.pnl = pnl
        self.mtm = mtm
        self.cashGIC = cashGIC
    }
}
