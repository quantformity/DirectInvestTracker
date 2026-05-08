import SwiftUI
import SwiftData

struct PositionListView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(AppContainer.self) private var appContainer
    let account: Account

    @Query private var positions: [Position]
    @State private var showAddPosition = false
    @State private var showAddTransaction = false
    @State private var positionToEdit: Position? = nil
    @State private var positionToSell: Position? = nil
    @State private var expandedPositionId: UUID? = nil
    @State private var errorMessage: String? = nil

    init(account: Account) {
        self.account = account
        let accountId = account.id
        _positions = Query(
            filter: #Predicate<Position> { $0.account?.id == accountId },
            sort: \Position.dateAdded,
            order: .reverse
        )
    }

    var body: some View {
        Group {
            if positions.isEmpty {
                ContentUnavailableView(
                    "No Positions",
                    systemImage: "chart.bar",
                    description: Text("Tap + to add a position.")
                )
            } else {
                List {
                    ForEach(positions) { position in
                        VStack(spacing: 0) {
                            PositionRowView(position: position)
                                .contentShape(Rectangle())
                                .onTapGesture {
                                    withAnimation(.easeInOut(duration: 0.2)) {
                                        expandedPositionId = expandedPositionId == position.id ? nil : position.id
                                    }
                                }

                            if expandedPositionId == position.id {
                                Divider()
                                HStack(spacing: 0) {
                                    if position.category == Category.equity.rawValue || position.category == Category.gic.rawValue {
                                        actionButton(label: "Sell", icon: "arrow.down.circle", color: .orange) {
                                            expandedPositionId = nil
                                            positionToSell = position
                                        }
                                        Divider().frame(height: 36)
                                    }
                                    actionButton(label: "Edit", icon: "pencil", color: .blue) {
                                        expandedPositionId = nil
                                        positionToEdit = position
                                    }
                                    Divider().frame(height: 36)
                                    actionButton(label: "Delete", icon: "trash", color: .red) {
                                        expandedPositionId = nil
                                        delete(position)
                                    }
                                }
                                .transition(.opacity.combined(with: .move(edge: .top)))
                            }
                        }
                        .swipeActions(edge: .trailing) {
                            Button(role: .destructive) {
                                delete(position)
                            } label: {
                                Label("Delete", systemImage: "trash")
                            }
                            Button {
                                positionToEdit = position
                            } label: {
                                Label("Edit", systemImage: "pencil")
                            }
                            .tint(.blue)
                        }
                        .swipeActions(edge: .leading) {
                            if position.category == Category.equity.rawValue || position.category == Category.gic.rawValue {
                                Button {
                                    positionToSell = position
                                } label: {
                                    Label("Sell", systemImage: "arrow.down.circle")
                                }
                                .tint(.orange)
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle(account.name)
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Menu {
                    Button {
                        showAddPosition = true
                    } label: {
                        Label("Add Position", systemImage: "chart.bar")
                    }
                    Button {
                        showAddTransaction = true
                    } label: {
                        Label("Cash Transaction", systemImage: "dollarsign.circle")
                    }
                } label: {
                    Image(systemName: "plus")
                }
            }
        }
        .sheet(isPresented: $showAddPosition) {
            PositionFormView(account: account) { symbol, cat, qty, cost, date, yieldRate, currency in
                addPosition(symbol: symbol, category: cat, quantity: qty,
                            costPerShare: cost, dateAdded: date, yieldRate: yieldRate, currency: currency)
            }
        }
        .sheet(item: $positionToEdit) { position in
            PositionFormView(account: account, existingPosition: position) { symbol, cat, qty, cost, date, yieldRate, currency in
                position.symbol       = symbol.uppercased()
                position.category     = cat.rawValue
                position.quantity     = qty
                position.costPerShare = cost
                position.dateAdded    = date
                position.yieldRate    = yieldRate
                position.currency     = currency
                try? modelContext.save()
            }
        }
        .sheet(item: $positionToSell) { position in
            SellPositionView(position: position) { qty, price, fee, date in
                try sellPosition(position, quantity: qty, price: price, fee: fee, date: date)
            }
        }
        .sheet(isPresented: $showAddTransaction) {
            TransactionFormView(account: account) { amount, _, date in
                let cashPosition = Position(
                    symbol: "CASH",
                    category: Category.cash.rawValue,
                    quantity: amount,
                    costPerShare: 1.0,
                    dateAdded: date,
                    currency: account.baseCurrency,
                    account: account
                )
                modelContext.insert(cashPosition)
                try? modelContext.save()
                appContainer.iCloudService.scheduleExport(context: modelContext)
            }
        }
        if let error = errorMessage {
            ErrorBannerView(message: error) { errorMessage = nil }
        }
    }

    // MARK: - Action button

    private func actionButton(label: String, icon: String, color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 16))
                Text(label)
                    .font(.caption2)
            }
            .foregroundStyle(color)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
        }
        .buttonStyle(.plain)
    }

    // MARK: - Mutations

    private func addPosition(symbol: String, category: Category, quantity: Double,
                             costPerShare: Double, dateAdded: Date, yieldRate: Double?, currency: String) {
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

        if (category == .equity || category == .gic) && quantity > 0 {
            let totalCostInStockCcy = quantity * costPerShare
            let acctCurrency = account.baseCurrency
            Task { @MainActor in
                let fx = await appContainer.fxService.ensuredRate(from: currency, to: acctCurrency, context: modelContext)
                let withdrawal = Position(
                    symbol: "CASH",
                    category: Category.cash.rawValue,
                    quantity: -(totalCostInStockCcy * fx),
                    costPerShare: 1.0,
                    dateAdded: dateAdded,
                    currency: acctCurrency,
                    account: account
                )
                modelContext.insert(withdrawal)
                try? modelContext.save()
                appContainer.iCloudService.scheduleExport(context: modelContext)
            }
        } else {
            try? modelContext.save()
        }
    }

    private func sellPosition(_ position: Position, quantity: Double, price: Double, fee: Double, date: Date) throws {
        guard quantity <= position.quantity else {
            throw PositionError.insufficientQuantity(held: position.quantity, requested: quantity)
        }
        let netCashInStockCcy = quantity * price - fee
        let stockCurrency = position.currency
        let acctCurrency = account.baseCurrency

        if position.quantity - quantity <= 0 {
            modelContext.delete(position)
        } else {
            position.quantity -= quantity
        }

        Task { @MainActor in
            let fx = await appContainer.fxService.ensuredRate(from: stockCurrency, to: acctCurrency, context: modelContext)
            let deposit = Position(
                symbol: "CASH",
                category: Category.cash.rawValue,
                quantity: netCashInStockCcy * fx,
                costPerShare: 1.0,
                dateAdded: date,
                currency: acctCurrency,
                account: account
            )
            modelContext.insert(deposit)
            try? modelContext.save()
            appContainer.iCloudService.scheduleExport(context: modelContext)
        }
    }

    private func delete(_ position: Position) {
        modelContext.delete(position)
        try? modelContext.save()
    }
}
