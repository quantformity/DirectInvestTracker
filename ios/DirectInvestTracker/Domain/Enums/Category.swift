import Foundation

enum Category: String, CaseIterable, Identifiable, Codable {
    case equity   = "Equity"
    case gic      = "GIC"
    case cash     = "Cash"
    case dividend = "Dividend"

    var id: String { rawValue }

    /// Whether the spot price is fixed at cost (no market price needed)
    var isFixedPrice: Bool {
        switch self {
        case .gic, .cash, .dividend: return true
        case .equity: return false
        }
    }
}
