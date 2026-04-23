import Foundation

protocol FxServiceProtocol {
    func lookupFx(from: String, to: String, fxRates: [String: Double]) -> Double
    func refreshAllRates(positions: [Position], accounts: [Account]) async throws -> [String: Double]
}
