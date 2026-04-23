import SwiftUI
import SwiftData

struct PositionListView: View {
    @Environment(\.modelContext) private var modelContext
    let account: Account

    @Query private var positions: [Position]
    @State private var showAddPosition = false
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
                Button(action: { showAddPosition = true }) {
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
            let withdrawal = Position(
                symbol: "CASH",
                category: Category.cash.rawValue,
                quantity: -(quantity * costPerShare),
                costPerShare: 1.0,
                dateAdded: dateAdded,
                currency: account.baseCurrency,
                account: account
            )
            modelContext.insert(withdrawal)
        }
        try? modelContext.save()
    }

    private func sellPosition(_ position: Position, quantity: Double, price: Double, fee: Double, date: Date) throws {
        guard quantity <= position.quantity else {
            throw PositionError.insufficientQuantity(held: position.quantity, requested: quantity)
        }
        let netCash = quantity * price - fee
        let deposit = Position(
            symbol: "CASH",
            category: Category.cash.rawValue,
            quantity: netCash,
            costPerShare: 1.0,
            dateAdded: date,
            currency: account.baseCurrency,
            account: account
        )
        modelContext.insert(deposit)

        if position.quantity - quantity <= 0 {
            modelContext.delete(position)
        } else {
            position.quantity -= quantity
        }
        try? modelContext.save()
    }

    private func delete(_ position: Position) {
        modelContext.delete(position)
        try? modelContext.save()
    }
}
