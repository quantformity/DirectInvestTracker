import Foundation

enum NumberFormatters {
    static func currency(_ value: Double, currency: String = "CAD") -> String {
        value.currencyFormatted(currency: currency)
    }

    static func percent(_ value: Double) -> String {
        value.percentFormatted()
    }

    static func compact(_ value: Double, currency: String = "CAD") -> String {
        let absValue = abs(value)
        let sign = value < 0 ? "-" : ""
        let symbol = Locale.current.currencySymbol ?? "$"
        switch absValue {
        case 1_000_000_000...:
            return "\(sign)\(symbol)\(String(format: "%.1f", absValue / 1_000_000_000))B"
        case 1_000_000...:
            return "\(sign)\(symbol)\(String(format: "%.1f", absValue / 1_000_000))M"
        case 1_000...:
            return "\(sign)\(symbol)\(String(format: "%.1f", absValue / 1_000))K"
        default:
            return value.currencyFormatted(currency: currency)
        }
    }
}
