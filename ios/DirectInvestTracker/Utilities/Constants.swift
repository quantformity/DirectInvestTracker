import Foundation

enum Constants {
    static let defaultReportingCurrency = "CAD"

    static let supportedCurrencies = [
        "CAD", "USD", "EUR", "GBP", "AUD", "CHF",
        "JPY", "CNY", "HKD", "SGD", "NZD", "SEK",
        "NOK", "DKK", "MXN", "BRL", "INR", "KRW"
    ]

    static let backgroundTaskIdentifier = "com.quantformity.directinvest.marketrefresh"
}
