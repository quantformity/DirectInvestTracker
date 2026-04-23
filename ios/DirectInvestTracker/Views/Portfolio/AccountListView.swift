import SwiftUI
import SwiftData

struct AccountListView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \Account.name) private var accounts: [Account]

    @State private var showAddAccount = false
    @State private var accountToEdit: Account? = nil
    @State private var errorMessage: String? = nil

    var body: some View {
        NavigationStack {
            Group {
                if accounts.isEmpty {
                    ContentUnavailableView(
                        "No Accounts",
                        systemImage: "building.columns",
                        description: Text("Tap + to add your first account.")
                    )
                } else {
                    List {
                        ForEach(accounts) { account in
                            NavigationLink(destination: PositionListView(account: account)) {
                                AccountRowView(account: account, positionCount: account.positions.count)
                            }
                            .swipeActions(edge: .trailing) {
                                Button(role: .destructive) {
                                    delete(account)
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                                Button {
                                    accountToEdit = account
                                } label: {
                                    Label("Edit", systemImage: "pencil")
                                }
                                .tint(.blue)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Accounts")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { showAddAccount = true }) {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showAddAccount) {
                AccountFormView { name, currency in
                    let account = Account(name: name, baseCurrency: currency)
                    modelContext.insert(account)
                    try? modelContext.save()
                }
            }
            .sheet(item: $accountToEdit) { account in
                AccountFormView(existingAccount: account) { name, currency in
                    account.name = name
                    account.baseCurrency = currency
                    try? modelContext.save()
                }
            }

            if let error = errorMessage {
                ErrorBannerView(message: error) { errorMessage = nil }
            }
        }
    }

    private func delete(_ account: Account) {
        modelContext.delete(account)
        try? modelContext.save()
    }
}
