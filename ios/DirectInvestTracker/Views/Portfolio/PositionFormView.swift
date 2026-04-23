import SwiftUI

struct PositionFormView: View {
    @Environment(\.dismiss) private var dismiss

    let account: Account
    var existingPosition: Position? = nil
    var onSave: (String, Category, Double, Double, Date, Double?, String) -> Void

    @State private var symbol: String = ""
    @State private var category: Category = .equity
    @State private var quantity: String = ""
    @State private var costPerShare: String = ""
    @State private var dateAdded: Date = Date()
    @State private var yieldRateText: String = ""
    @State private var currency: String = "CAD"

    private var yieldRate: Double? {
        guard category == .gic, let v = Double(yieldRateText), v > 0 else { return nil }
        return v
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Position Details") {
                    Picker("Category", selection: $category) {
                        ForEach(Category.allCases) { c in
                            Text(c.rawValue).tag(c)
                        }
                    }

                    if category == .equity {
                        TextField("Symbol (e.g. AAPL)", text: $symbol)
                            .textInputAutocapitalization(.characters)
                    } else {
                        TextField("Label (e.g. TD GIC 2025)", text: $symbol)
                    }

                    TextField("Quantity", text: $quantity)
                        .keyboardType(.decimalPad)

                    TextField("Cost Per Share / Unit", text: $costPerShare)
                        .keyboardType(.decimalPad)

                    DatePicker("Date Added", selection: $dateAdded, displayedComponents: .date)

                    Picker("Currency", selection: $currency) {
                        ForEach(Constants.supportedCurrencies, id: \.self) { c in
                            Text(c).tag(c)
                        }
                    }
                }

                if category == .gic {
                    Section("GIC Details") {
                        HStack {
                            TextField("Annual Yield Rate", text: $yieldRateText)
                                .keyboardType(.decimalPad)
                            Text("%")
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .navigationTitle(existingPosition == nil ? "New Position" : "Edit Position")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        guard let qty  = Double(quantity),
                              let cost = Double(costPerShare) else { return }
                        let yr = yieldRateText.isEmpty ? nil : Double(yieldRateText).map { $0 / 100.0 }
                        onSave(symbol, category, qty, cost, dateAdded, yr, currency)
                        dismiss()
                    }
                    .disabled(!isValid)
                }
            }
            .onAppear { populate() }
        }
    }

    private var isValid: Bool {
        !symbol.trimmingCharacters(in: .whitespaces).isEmpty &&
        Double(quantity) != nil &&
        Double(costPerShare) != nil &&
        (category != .gic || Double(yieldRateText) != nil)
    }

    private func populate() {
        guard let p = existingPosition else {
            currency = account.baseCurrency
            return
        }
        symbol      = p.symbol
        category    = Category(rawValue: p.category) ?? .equity
        quantity    = "\(p.quantity)"
        costPerShare = "\(p.costPerShare)"
        dateAdded   = p.dateAdded
        currency    = p.currency
        if let yr = p.yieldRate { yieldRateText = "\(yr * 100)" }
    }
}
