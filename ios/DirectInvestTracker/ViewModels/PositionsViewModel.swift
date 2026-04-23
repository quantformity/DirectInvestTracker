import Foundation
import SwiftData
import SwiftUI

@MainActor
@Observable
class PositionsViewModel {

    var positions: [Position] = []
    var errorMessage: String? = nil

    private let modelContext: ModelContext

    init(modelContext: ModelContext) {
        self.modelContext = modelContext
    }

    func fetchPositions(for account: Account) {
        let accountId = account.id
        let descriptor = FetchDescriptor<Position>(
            predicate: #Predicate { $0.account?.id == accountId },
            sortBy: [SortDescriptor(\.dateAdded, order: .reverse)]
        )
        positions = (try? modelContext.fetch(descriptor)) ?? []
    }

    func addPosition(
        to account: Account,
        symbol: String,
        category: Category,
        quantity: Double,
        costPerShare: Double,
        dateAdded: Date,
        yieldRate: Double?,
        currency: String
    ) {
        let position = Position(
            symbol: symbol.uppercased(),
            category: category.rawValue,
            quantity: quantity,
            costPerShare: costPerShare,
            dateAdded: dateAdded,
            yieldRate: yieldRate,
            currency: currency,
            account: account
        )
        modelContext.insert(position)

        // Auto-create cash withdrawal for Equity/GIC purchases
        if (category == .equity || category == .gic) && quantity > 0 {
            let totalCost = quantity * costPerShare
            let cashWithdrawal = Position(
                symbol: "CASH",
                category: Category.cash.rawValue,
                quantity: -totalCost,
                costPerShare: 1.0,
                dateAdded: dateAdded,
                currency: account.baseCurrency,
                account: account
            )
            modelContext.insert(cashWithdrawal)
        }

        save()
        fetchPositions(for: account)
    }

    func updatePosition(_ position: Position, symbol: String, category: Category, quantity: Double,
                        costPerShare: Double, dateAdded: Date, yieldRate: Double?, currency: String) {
        position.symbol = symbol.uppercased()
        position.category = category.rawValue
        position.quantity = quantity
        position.costPerShare = costPerShare
        position.dateAdded = dateAdded
        position.yieldRate = yieldRate
        position.currency = currency
        guard let account = position.account else { return }
        save()
        fetchPositions(for: account)
    }

    func deletePosition(_ position: Position) {
        let account = position.account
        modelContext.delete(position)
        save()
        if let account { fetchPositions(for: account) }
    }

    func sellPosition(_ position: Position, quantity: Double, price: Double, fee: Double, date: Date) throws {
        guard let account = position.account else {
            throw PositionError.noAccount
        }
        guard quantity <= position.quantity else {
            throw PositionError.insufficientQuantity(held: position.quantity, requested: quantity)
        }

        let netCash = quantity * price - fee

        // Deposit cash proceeds
        let cashDeposit = Position(
            symbol: "CASH",
            category: Category.cash.rawValue,
            quantity: netCash,
            costPerShare: 1.0,
            dateAdded: date,
            currency: account.baseCurrency,
            account: account
        )
        modelContext.insert(cashDeposit)

        let remaining = position.quantity - quantity
        if remaining <= 0 {
            modelContext.delete(position)
        } else {
            position.quantity = remaining
        }
        save()
        fetchPositions(for: account)
    }

    private func save() {
        do {
            try modelContext.save()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

enum PositionError: LocalizedError {
    case noAccount
    case insufficientQuantity(held: Double, requested: Double)

    var errorDescription: String? {
        switch self {
        case .noAccount:
            return "Position has no associated account."
        case let .insufficientQuantity(held, requested):
            return "Cannot sell \(requested); only \(held) held."
        }
    }
}
