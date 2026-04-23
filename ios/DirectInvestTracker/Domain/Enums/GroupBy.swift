import Foundation

enum GroupBy: String, CaseIterable, Identifiable {
    case category = "category"
    case account  = "account"
    case sector   = "sector"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .category: return "Category"
        case .account:  return "Account"
        case .sector:   return "Sector"
        }
    }
}
