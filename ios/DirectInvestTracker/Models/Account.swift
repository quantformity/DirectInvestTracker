import Foundation
import SwiftData

@Model
final class Account {
    var id: UUID
    var name: String
    var baseCurrency: String

    @Relationship(deleteRule: .cascade, inverse: \Position.account)
    var positions: [Position]

    init(name: String, baseCurrency: String = "CAD") {
        self.id = UUID()
        self.name = name
        self.baseCurrency = baseCurrency
        self.positions = []
    }
}
