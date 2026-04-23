import SwiftUI

struct CurrencyPickerView: View {
    @Binding var selectedCurrency: String

    var body: some View {
        Picker("Currency", selection: $selectedCurrency) {
            ForEach(Constants.supportedCurrencies, id: \.self) { c in
                Text(c).tag(c)
            }
        }
    }
}
