import SwiftUI

struct SellPositionView: View {
    @Environment(\.dismiss) private var dismiss

    let position: Position
    var onSell: (Double, Double, Double, Date) throws -> Void

    @State private var quantityText: String = ""
    @State private var priceText: String = ""
    @State private var feeText: String = "0"
    @State private var saleDate: Date = Date()
    @State private var errorMessage: String? = nil

    var body: some View {
        NavigationStack {
            Form {
                Section("Sell \(position.symbol)") {
                    HStack {
                        Text("Holding")
                        Spacer()
                        Text("\(position.quantity.formatted(.number.precision(.fractionLength(4)))) units")
                            .foregroundStyle(.secondary)
                    }

                    TextField("Quantity to Sell", text: $quantityText)
                        .keyboardType(.decimalPad)

                    TextField("Sale Price per Unit", text: $priceText)
                        .keyboardType(.decimalPad)

                    TextField("Fee (optional)", text: $feeText)
                        .keyboardType(.decimalPad)

                    DatePicker("Sale Date", selection: $saleDate, displayedComponents: .date)
                }

                if let proceeds = netProceeds {
                    Section {
                        HStack {
                            Text("Net Proceeds")
                            Spacer()
                            Text(proceeds.currencyFormatted(currency: position.account?.baseCurrency ?? "CAD"))
                                .fontWeight(.semibold)
                        }
                    }
                }

                if let err = errorMessage {
                    Section {
                        Text(err)
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("Sell Position")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Sell") {
                        guard let qty   = Double(quantityText),
                              let price = Double(priceText),
                              let fee   = Double(feeText) else { return }
                        do {
                            try onSell(qty, price, fee, saleDate)
                            dismiss()
                        } catch {
                            errorMessage = error.localizedDescription
                        }
                    }
                    .disabled(!isValid)
                }
            }
        }
    }

    private var netProceeds: Double? {
        guard let qty   = Double(quantityText),
              let price = Double(priceText),
              let fee   = Double(feeText) else { return nil }
        return qty * price - fee
    }

    private var isValid: Bool {
        guard let qty = Double(quantityText), qty > 0, qty <= position.quantity else { return false }
        guard Double(priceText) != nil else { return false }
        guard Double(feeText) != nil else { return false }
        return true
    }
}
