import SwiftUI

struct AccountFormView: View {
    @Environment(\.dismiss) private var dismiss

    @State private var name: String = ""
    @State private var currency: String = "CAD"

    var existingAccount: Account? = nil
    var onSave: (String, String) -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section("Account Details") {
                    TextField("Account Name", text: $name)
                    Picker("Base Currency", selection: $currency) {
                        ForEach(Constants.supportedCurrencies, id: \.self) { c in
                            Text(c).tag(c)
                        }
                    }
                }
            }
            .navigationTitle(existingAccount == nil ? "New Account" : "Edit Account")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave(name, currency)
                        dismiss()
                    }
                    .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
            .onAppear {
                if let account = existingAccount {
                    name     = account.name
                    currency = account.baseCurrency
                }
            }
        }
    }
}
