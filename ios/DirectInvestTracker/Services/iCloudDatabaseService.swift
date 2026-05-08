import Foundation
import SwiftData

// MARK: - iCloud Database Service

@Observable
@MainActor
final class iCloudDatabaseService {

    private(set) var linkedURL: URL?

    var lastSyncDate: Date? {
        get { AppSettingsStore.lastSyncDate }
        set { AppSettingsStore.lastSyncDate = newValue }
    }

    var syncError: String?
    var isSyncing: Bool = false

    private var exportTask: Task<Void, Never>?
    private var lastKnownModDate: Date?

    init() {
        linkedURL = resolveBookmark()
    }

    // MARK: - Linking

    func link(url: URL) {
        let accessed = url.startAccessingSecurityScopedResource()
        defer { if accessed { url.stopAccessingSecurityScopedResource() } }
        do {
            let bookmark = try url.bookmarkData(
                options: .minimalBookmark,
                includingResourceValuesForKeys: nil,
                relativeTo: nil
            )
            AppSettingsStore.linkedDatabaseBookmark = bookmark
            linkedURL = url
            syncError = nil
        } catch {
            syncError = "Could not bookmark file: \(error.localizedDescription)"
        }
    }

    func unlink() {
        AppSettingsStore.linkedDatabaseBookmark = nil
        AppSettingsStore.lastSyncDate = nil
        linkedURL = nil
        lastKnownModDate = nil
        syncError = nil
        exportTask?.cancel()
    }

    // MARK: - Import (foreground check)

    func checkAndSyncIfNeeded(context: ModelContext) async {
        guard !isSyncing, let url = linkedURL else { return }

        // Trigger iCloud download if the item is ubiquitous
        let fm = FileManager.default
        if fm.isUbiquitousItem(at: url) {
            try? fm.startDownloadingUbiquitousItem(at: url)
            // Wait up to 3 seconds for the file to become current
            for _ in 0..<30 {
                let status = (try? url.resourceValues(forKeys: [.ubiquitousItemDownloadingStatusKey]))?
                    .ubiquitousItemDownloadingStatus
                if status == .current { break }
                try? await Task.sleep(nanoseconds: 100_000_000)
            }
        }

        // Check modification date
        guard let modDate = (try? url.resourceValues(forKeys: [.contentModificationDateKey]))?
            .contentModificationDate else { return }

        // Skip if file hasn't changed since last sync
        if let lastSync = lastSyncDate, modDate <= lastSync { return }
        if let lastKnown = lastKnownModDate, modDate <= lastKnown { return }

        isSyncing = true
        syncError = nil

        var coordinatorError: NSError?
        var importError: Error?

        NSFileCoordinator().coordinate(readingItemAt: url, options: [], error: &coordinatorError) { coordURL in
            do {
                _ = try SQLiteImportService.importFile(url: coordURL, context: context)
            } catch {
                importError = error
            }
        }

        isSyncing = false

        if let err = coordinatorError ?? importError {
            syncError = "Sync failed: \(err.localizedDescription)"
        } else {
            lastKnownModDate = modDate
            lastSyncDate = Date()
        }
    }

    // MARK: - Export (debounced after mutation)

    func scheduleExport(context: ModelContext) {
        exportTask?.cancel()
        exportTask = Task { [weak self] in
            guard let self else { return }
            try? await Task.sleep(nanoseconds: 1_500_000_000)
            guard !Task.isCancelled else { return }
            guard !self.isSyncing else { return }
            await self.performExport(context: context)
        }
    }

    // Export to an arbitrary URL (e.g. "Export to New File")
    func exportTo(url: URL, context: ModelContext) async throws {
        let accounts          = (try? context.fetch(FetchDescriptor<Account>()))          ?? []
        let positions         = (try? context.fetch(FetchDescriptor<Position>()))         ?? []
        let marketData        = (try? context.fetch(FetchDescriptor<MarketData>()))       ?? []
        let fxRates           = (try? context.fetch(FetchDescriptor<FxRate>()))           ?? []
        let sectorMappings    = (try? context.fetch(FetchDescriptor<SectorMapping>()))    ?? []
        let sellTransactions  = (try? context.fetch(FetchDescriptor<SellTransaction>())) ?? []

        var writeError: Error?
        var coordinatorError: NSError?

        NSFileCoordinator().coordinate(writingItemAt: url, options: .forReplacing,
                                       error: &coordinatorError) { coordURL in
            do {
                try SQLiteExportService.export(
                    accounts: accounts,
                    positions: positions,
                    marketData: marketData,
                    fxRates: fxRates,
                    sectorMappings: sectorMappings,
                    sellTransactions: sellTransactions,
                    to: coordURL
                )
            } catch {
                writeError = error
            }
        }

        if let err = coordinatorError ?? writeError { throw err }
    }

    // MARK: - Private

    private func performExport(context: ModelContext) async {
        guard let url = linkedURL else { return }
        isSyncing = true
        defer { isSyncing = false }
        do {
            try await exportTo(url: url, context: context)
            lastSyncDate = Date()
            // Record the new mod date so we don't re-import our own export
            lastKnownModDate = (try? url.resourceValues(forKeys: [.contentModificationDateKey]))?
                .contentModificationDate
        } catch {
            syncError = "Export failed: \(error.localizedDescription)"
        }
    }

    private func resolveBookmark() -> URL? {
        guard let data = AppSettingsStore.linkedDatabaseBookmark else { return nil }
        var isStale = false
        guard let url = try? URL(
            resolvingBookmarkData: data,
            options: .withoutUI,
            relativeTo: nil,
            bookmarkDataIsStale: &isStale
        ) else { return nil }

        if isStale {
            let accessed = url.startAccessingSecurityScopedResource()
            defer { if accessed { url.stopAccessingSecurityScopedResource() } }
            let newData = try? url.bookmarkData(
                options: .minimalBookmark,
                includingResourceValuesForKeys: nil,
                relativeTo: nil
            )
            AppSettingsStore.linkedDatabaseBookmark = newData
        }
        return url
    }
}
