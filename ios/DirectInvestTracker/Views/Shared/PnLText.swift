import SwiftUI

struct PnLText: View {
    let value: Double
    let currency: String
    var showSign: Bool = true

    var body: some View {
        Text(formatted)
            .foregroundStyle(Color.pnl(value))
            .fontWeight(.semibold)
    }

    private var formatted: String {
        let f = value.currencyFormatted(currency: currency)
        return showSign && value > 0 ? "+\(f)" : f
    }
}
