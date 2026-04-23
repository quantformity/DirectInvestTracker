import SwiftUI
import SwiftData
import UniformTypeIdentifiers

struct SettingsRootView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(AppContainer.self) private var appContainer

    @Query(sort: \SectorMapping.symbol) private var sectorMappings: [SectorMapping]

    @State private var reportingCurrency: String = AppSettingsStore.reportingCurrency
    @State private var lastRefreshDate: Date? = AppSettingsStore.lastRefreshDate
    @State private var autoRefreshEnabled: Bool = AppSettingsStore.autoRefreshEnabled
    @State private var isRefreshing = false
    @State private var errorMessage: String? = nil

    // Import
    @State private var showImportPicker = false
    @State private var isImporting = false
    @State private var importResultMessage: String? = nil
    @State private var showImportConfirm = false
    @State private var pendingImportURL: URL? = nil

    var body: some View {
        NavigationStack {
            Form {
                Section("Reporting Currency") {
                    Picker("Currency", selection: $reportingCurrency) {
                        ForEach(Constants.supportedCurrencies, id: \.self) { c in
                            Text(c).tag(c)
                        }
                    }
                    .onChange(of: reportingCurrency) { _, newValue in
                        AppSettingsStore.reportingCurrency = newValue
                    }
                }

                Section("Sector Mappings") {
                    NavigationLink("Manage Sector Mappings") {
                        SectorMappingListView()
                    }
                }

                Section("Import Data") {
                    Button {
                        showImportPicker = true
                    } label: {
                        HStack {
                            if isImporting { ProgressView().padding(.trailing, 4) }
                            Label(isImporting ? "Importing…" : "Import from investments.db",
                                  systemImage: "square.and.arrow.down")
                        }
                    }
                    .disabled(isImporting)

                    if let msg = importResultMessage {
                        Text(msg)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("Market Data") {
                    Toggle("Auto-Refresh (every 5 min)", isOn: $autoRefreshEnabled)
                        .onChange(of: autoRefreshEnabled) { _, newValue in
                            appContainer.setAutoRefresh(enabled: newValue)
                        }
                    HStack {
                        Text("Last Refresh")
                        Spacer()
                        Text(lastRefreshDate.map { $0.formatted(style: .medium) } ?? "Never")
                            .foregroundStyle(.secondary)
                    }
                    Button(action: { Task { await refresh() } }) {
                        HStack {
                            if isRefreshing { ProgressView().padding(.trailing, 4) }
                            Text(isRefreshing ? "Refreshing…" : "Refresh Now")
                        }
                    }
                    .disabled(isRefreshing)
                }
            }
            .navigationTitle("Settings")

            if let error = errorMessage {
                ErrorBannerView(message: error) { errorMessage = nil }
            }
        }
        .fileImporter(
            isPresented: $showImportPicker,
            allowedContentTypes: [UTType.data, UTType.item],
            allowsMultipleSelection: false
        ) { result in
            guard case .success(let urls) = result, let url = urls.first else { return }
            pendingImportURL = url
            showImportConfirm = true
        }
        .confirmationDialog(
            "Replace all existing data with the contents of \(pendingImportURL?.lastPathComponent ?? "the file")?",
            isPresented: $showImportConfirm,
            titleVisibility: .visible
        ) {
            Button("Import & Replace", role: .destructive) {
                if let url = pendingImportURL { Task { await runImport(url: url) } }
            }
            Button("Cancel", role: .cancel) { pendingImportURL = nil }
        }
    }

    private func runImport(url: URL) async {
        isImporting = true
        importResultMessage = nil
        defer { isImporting = false }
        do {
            let summary = try SQLiteImportService.importFile(url: url, context: modelContext)
            importResultMessage = summary.description
        } catch {
            importResultMessage = "Import failed: \(error.localizedDescription)"
        }
        pendingImportURL = nil
    }

    private func refresh() async {
        isRefreshing = true
        defer { isRefreshing = false }
        let positions = (try? modelContext.fetch(FetchDescriptor<Position>())) ?? []
        let accounts  = (try? modelContext.fetch(FetchDescriptor<Account>())) ?? []
        await appContainer.refreshService.refresh(positions: positions, accounts: accounts)
        lastRefreshDate = AppSettingsStore.lastRefreshDate
        if let err = appContainer.refreshService.lastError { errorMessage = err }
    }
}

// MARK: - Sector Mapping list (inline, avoids the Bindable ViewModel dependency)

struct SectorMappingListView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \SectorMapping.symbol) private var sectorMappings: [SectorMapping]
    @State private var showAdd = false
    @State private var newSymbol = ""
    @State private var newSector = ""

    var body: some View {
        List {
            ForEach(sectorMappings, id: \.symbol) { mapping in
                HStack {
                    Text(mapping.symbol).font(.headline)
                    Spacer()
                    Text(mapping.sector).foregroundStyle(.secondary)
                }
            }
            .onDelete { indexSet in
                indexSet.forEach { modelContext.delete(sectorMappings[$0]) }
                try? modelContext.save()
            }
        }
        .navigationTitle("Sector Mappings")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button(action: { showAdd = true }) { Image(systemName: "plus") }
            }
        }
        .sheet(isPresented: $showAdd) {
            NavigationStack {
                Form {
                    TextField("Symbol (e.g. AAPL)", text: $newSymbol)
                        .textInputAutocapitalization(.characters)
                    TextField("Sector (e.g. Technology)", text: $newSector)
                }
                .navigationTitle("Add Mapping")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { showAdd = false }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Add") {
                            let m = SectorMapping(symbol: newSymbol.uppercased(), sector: newSector)
                            modelContext.insert(m)
                            try? modelContext.save()
                            newSymbol = ""; newSector = ""
                            showAdd = false
                        }
                        .disabled(newSymbol.isEmpty || newSector.isEmpty)
                    }
                }
            }
        }
    }
}
