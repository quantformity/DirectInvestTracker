import Foundation
import SwiftData
import SwiftUI

@MainActor
@Observable
class PositionsViewModel {

    var positions: [Position] = []
    var errorMessage: String? = nil

    private let modelContext: ModelContext
    var iCloudService: iCloudDatabaseService?
    var yahoo: YahooFinanceService?

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
        Task { @MainActor in
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

            // Auto-create cash withdrawal in account currency, FX-converted from stock currency.
            if (category == .equity || category == .gic) && quantity > 0 {
                let totalCostInStockCcy = quantity * costPerShare
                let fx = await fxRateEnsured(from: currency, to: account.baseCurrency)
                let cashWithdrawal = Position(
                    symbol: "CASH",
                    category: Category.cash.rawValue,
                    quantity: -(totalCostInStockCcy * fx),
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

        // Capture values before the async Task (position may be deleted).
        let stockCurrency      = position.currency
        let acctCurrency       = account.baseCurrency
        let positionSymbol     = position.symbol
        let positionCategory   = position.category
        let positionCostBasis  = position.costPerShare
        let netCashInStockCcy  = quantity * price - fee
        let remaining          = position.quantity - quantity

        if remaining <= 0 {
            modelContext.delete(position)
        } else {
            position.quantity = remaining
        }

        Task { @MainActor in
            let fx = await fxRateEnsured(from: stockCurrency, to: acctCurrency)

            // Deposit cash proceeds in account currency, FX-converted from stock currency.
            let cashDeposit = Position(
                symbol: "CASH",
                category: Category.cash.rawValue,
                quantity: netCashInStockCcy * fx,
                costPerShare: 1.0,
                dateAdded: date,
                currency: acctCurrency,
                account: account
            )
            modelContext.insert(cashDeposit)

            // Record realized PnL.
            let reportingCurrency    = AppSettingsStore.reportingCurrency
            let fxAcctToReporting    = await fxRateEnsured(from: acctCurrency, to: reportingCurrency)
            let realizedPnlStock     = quantity * price - fee - quantity * positionCostBasis
            let realizedPnlAccount   = realizedPnlStock * fx
            let tx = SellTransaction(
                accountId: account.pythonId ?? -1,
                accountName: account.name,
                symbol: positionSymbol,
                category: positionCategory,
                quantity: quantity,
                sellPrice: price,
                costPerShare: positionCostBasis,
                fee: fee,
                date: date,
                stockCurrency: stockCurrency,
                accountCurrency: acctCurrency,
                realizedPnlStock: realizedPnlStock,
                realizedPnlAccount: realizedPnlAccount,
                realizedPnlReporting: realizedPnlAccount * fxAcctToReporting,
                fxStockToAccount: fx,
                fxAccountToReporting: fxAcctToReporting
            )
            modelContext.insert(tx)

            save()
            fetchPositions(for: account)
        }
    }

    /// Returns FX rate from SwiftData, fetching from Yahoo Finance if not cached.
    private func fxRateEnsured(from: String, to: String) async -> Double {
        let f = from.uppercased(), t = to.uppercased()
        if f == t { return 1.0 }

        // Check DB first
        let rates = (try? modelContext.fetch(FetchDescriptor<FxRate>())) ?? []
        if let r = rates.filter({ $0.pair == "\(f)/\(t)" }).max(by: { $0.timestamp < $1.timestamp }) {
            return r.rate
        }
        if let r = rates.filter({ $0.pair == "\(t)/\(f)" }).max(by: { $0.timestamp < $1.timestamp }), r.rate != 0 {
            return 1.0 / r.rate
        }

        // Not in DB — fetch live from Yahoo Finance
        guard let yahoo else { return 1.0 }
        let fetched = try? await yahoo.fetchFxRates(pairs: [(f, t)])
        if let rate = fetched?["\(f)/\(t)"] {
            let fxRecord = FxRate(pair: "\(f)/\(t)", rate: rate)
            modelContext.insert(fxRecord)
            return rate
        }
        return 1.0
    }

    private func save() {
        do {
            try modelContext.save()
            iCloudService?.scheduleExport(context: modelContext)
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
