import Foundation
import SwiftData
import SwiftUI

@MainActor
@Observable
class AccountsViewModel {

    var accounts: [Account] = []
    var errorMessage: String? = nil

    private let modelContext: ModelContext

    init(modelContext: ModelContext) {
        self.modelContext = modelContext
        fetchAccounts()
    }

    func fetchAccounts() {
        let descriptor = FetchDescriptor<Account>(sortBy: [SortDescriptor(\.name)])
        accounts = (try? modelContext.fetch(descriptor)) ?? []
    }

    func addAccount(name: String, baseCurrency: String) {
        let account = Account(name: name, baseCurrency: baseCurrency)
        modelContext.insert(account)
        save()
    }

    func updateAccount(_ account: Account, name: String, baseCurrency: String) {
        account.name = name
        account.baseCurrency = baseCurrency
        save()
    }

    func deleteAccount(_ account: Account) {
        modelContext.delete(account)
        save()
    }

    func positionCount(for account: Account) -> Int {
        account.positions.count
    }

    private func save() {
        do {
            try modelContext.save()
            fetchAccounts()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
