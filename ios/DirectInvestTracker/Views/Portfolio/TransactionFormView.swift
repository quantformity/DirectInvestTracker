import SwiftUI

/// Generic cash deposit / withdrawal entry (for recording dividends, transfers, etc.)
struct TransactionFormView: View {
    @Environment(\.dismiss) private var dismiss

    let account: Account
    var onSave: (Double, String, Date) -> Void  // amount, note, date

    @State private var amountText: String = ""
    @State private var note: String = ""
    @State private var date: Date = Date()
    @State private var isDeposit = true

    var body: some View {
        NavigationStack {
            Form {
                Section("Transaction") {
                    Picker("Type", selection: $isDeposit) {
                        Text("Deposit").tag(true)
                        Text("Withdrawal").tag(false)
                    }
                    .pickerStyle(.segmented)

                    TextField("Amount (\(account.baseCurrency))", text: $amountText)
                        .keyboardType(.decimalPad)

                    TextField("Note (optional)", text: $note)

                    DatePicker("Date", selection: $date, displayedComponents: .date)
                }
            }
            .navigationTitle("Record Transaction")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        guard let amount = Double(amountText) else { return }
                        onSave(isDeposit ? amount : -amount, note, date)
                        dismiss()
                    }
                    .disabled(Double(amountText) == nil)
                }
            }
        }
    }
}
