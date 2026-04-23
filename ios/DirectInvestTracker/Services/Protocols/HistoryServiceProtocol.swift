import Foundation

protocol HistoryServiceProtocol {
    func aggregateHistory(
        positions: [Position],
        accounts: [UUID: Account],
        latestFx: [String: Double],
        reportingCurrency: String,
        useCache: Bool
    ) async throws -> [HistoryPoint]

    func symbolHistory(
        symbol: String,
        positions: [Position],
        useCache: Bool
    ) async throws -> [Date: Double]
}
