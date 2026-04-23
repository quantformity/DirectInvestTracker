import Foundation

extension Double {
    func currencyFormatted(currency: String = "CAD", maximumFractionDigits: Int = 2) -> String {
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.currencyCode = currency
        f.maximumFractionDigits = maximumFractionDigits
        return f.string(from: NSNumber(value: self)) ?? "\(self)"
    }

    func percentFormatted(maximumFractionDigits: Int = 2) -> String {
        let f = NumberFormatter()
        f.numberStyle = .percent
        f.maximumFractionDigits = maximumFractionDigits
        f.multiplier = 1
        return f.string(from: NSNumber(value: self)) ?? "\(self)%"
    }

    var signPrefix: String { self >= 0 ? "+" : "" }

    func signedFormatted(currency: String = "CAD") -> String {
        signPrefix + currencyFormatted(currency: currency)
    }
}
