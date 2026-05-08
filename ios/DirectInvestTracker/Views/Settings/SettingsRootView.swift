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

    // iCloud sync — link picker
    @State private var showLinkPicker = false
    @State private var pendingLinkURL: URL? = nil
    @State private var showLinkConfirm = false

    // iCloud sync — export
    @State private var isExporting = false
    @State private var showExportShare = false
    @State private var exportTempURL: URL? = nil

    var body: some View {
        let iCloudService = appContainer.iCloudService
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

                Section("iCloud Database Sync") {
                    // Linked file row
                    HStack {
                        Label(
                            iCloudService.linkedURL?.lastPathComponent ?? "Not linked",
                            systemImage: iCloudService.linkedURL != nil ? "link" : "link.badge.plus"
                        )
                        Spacer()
                        if iCloudService.linkedURL != nil {
                            Button("Unlink") { iCloudService.unlink() }
                                .foregroundStyle(.red)
                                .buttonStyle(.borderless)
                        }
                    }

                    // Link / Sync buttons
                    if iCloudService.linkedURL == nil {
                        Button {
                            showLinkPicker = true
                        } label: {
                            Label("Link Database File…", systemImage: "square.and.arrow.down")
                        }
                    } else {
                        Button {
                            Task { await iCloudService.checkAndSyncIfNeeded(context: modelContext) }
                        } label: {
                            HStack {
                                if iCloudService.isSyncing {
                                    ProgressView().padding(.trailing, 4)
                                }
                                Text(iCloudService.isSyncing ? "Syncing…" : "Sync Now")
                            }
                        }
                        .disabled(iCloudService.isSyncing)
                    }

                    // Export to new file
                    Button {
                        Task { await exportToTemp() }
                    } label: {
                        HStack {
                            if isExporting { ProgressView().padding(.trailing, 4) }
                            Label(isExporting ? "Preparing…" : "Export to New File…",
                                  systemImage: "square.and.arrow.up")
                        }
                    }
                    .disabled(isExporting)

                    // Status messages
                    if let d = iCloudService.lastSyncDate {
                        Text("Last sync: \(d.formatted(date: .abbreviated, time: .shortened))")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    if let err = iCloudService.syncError {
                        Text(err)
                            .font(.caption)
                            .foregroundStyle(.red)
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
        // Link file picker
        .fileImporter(
            isPresented: $showLinkPicker,
            allowedContentTypes: [UTType.data, UTType.item],
            allowsMultipleSelection: false
        ) { result in
            guard case .success(let urls) = result, let url = urls.first else { return }
            pendingLinkURL = url
            showLinkConfirm = true
        }
        .confirmationDialog(
            "Link \(pendingLinkURL?.lastPathComponent ?? "this file") as the shared database?\nChanges on iOS will be written back to this file.",
            isPresented: $showLinkConfirm,
            titleVisibility: .visible
        ) {
            Button("Link & Sync Now") {
                if let url = pendingLinkURL {
                    appContainer.iCloudService.link(url: url)
                    Task {
                        await appContainer.iCloudService.checkAndSyncIfNeeded(context: modelContext)
                    }
                }
                pendingLinkURL = nil
            }
            Button("Cancel", role: .cancel) { pendingLinkURL = nil }
        }
        // Export share sheet
        .sheet(isPresented: $showExportShare) {
            if let url = exportTempURL {
                ShareSheet(url: url)
            }
        }
    }

    // MARK: - Actions

    private func exportToTemp() async {
        isExporting = true
        defer { isExporting = false }
        let ts = Int(Date().timeIntervalSince1970)
        let tempURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("investments_\(ts).db")
        do {
            try await appContainer.iCloudService.exportTo(url: tempURL, context: modelContext)
            exportTempURL = tempURL
            showExportShare = true
        } catch {
            errorMessage = "Export failed: \(error.localizedDescription)"
        }
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

// MARK: - Share sheet

private struct ShareSheet: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: [url], applicationActivities: nil)
    }

    func updateUIViewController(_ uvc: UIActivityViewController, context: Context) {}
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
