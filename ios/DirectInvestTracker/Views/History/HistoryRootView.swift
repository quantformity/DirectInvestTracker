import SwiftUI
import SwiftData

// MARK: - UserDefaults keys for last sub-selections
private enum HistoryPref {
    static let accountId = "history.lastAccountId"
    static let symbol    = "history.lastSymbol"
    static let sector    = "history.lastSector"
}

struct HistoryRootView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(AppContainer.self) private var appContainer

    @Query(sort: \Account.name) private var accounts: [Account]
    @Query private var sectorMappings: [SectorMapping]

    @State private var mode: HistoryMode = .portfolio
    @State private var selectedAccountId: UUID? = nil
    @State private var selectedSymbol: String? = nil
    @State private var selectedSector: String? = nil
    @State private var points: [HistoryPoint] = []
    @State private var isLoading = false
    @State private var errorMessage: String? = nil

    var peakPoint:   HistoryPoint? { points.max(by: { $0.mtm < $1.mtm }) }
    var troughPoint: HistoryPoint? { points.min(by: { $0.mtm < $1.mtm }) }

    @State private var availableSymbols: [String] = []
    @State private var availableSectors: [String] = []

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                HistoryModePickerView(selectedMode: $mode)
                    .padding(.horizontal)
                    .padding(.top, 8)
                    .padding(.bottom, 4)

                subPicker
                    .padding(.horizontal)
                    .padding(.bottom, 8)

                Divider()

                if isLoading {
                    LoadingView()
                } else if points.isEmpty {
                    ContentUnavailableView(
                        "No History",
                        systemImage: "chart.line.uptrend.xyaxis",
                        description: Text("Tap ↺ to load historical data from Yahoo Finance.")
                    )
                } else {
                    ScrollView {
                        VStack(spacing: 16) {
                            HistoryChartView(points: points)
                                .frame(height: 260)
                                .padding(.horizontal)

                            HistoryExtremesView(
                                peak: peakPoint,
                                trough: troughPoint,
                                currency: AppSettingsStore.reportingCurrency
                            )
                            .padding(.horizontal)
                        }
                        .padding(.vertical)
                    }
                }

                if let error = errorMessage {
                    ErrorBannerView(message: error) { errorMessage = nil }
                }
            }
            .navigationTitle("History")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { Task { await load(useCache: false) } }) {
                        Image(systemName: "arrow.clockwise")
                    }
                    .disabled(isLoading)
                }
            }
            .onAppear {
                buildPickerOptions()
                Task { await load(useCache: true) }
            }
            .onChange(of: mode) { _, _ in
                points = []
                applyDefaultSelection()
                Task { await load(useCache: true) }
            }
            .onChange(of: selectedAccountId) { _, newVal in
                if let id = newVal {
                    UserDefaults.standard.set(id.uuidString, forKey: HistoryPref.accountId)
                }
                Task { await load(useCache: true) }
            }
            .onChange(of: selectedSymbol) { _, newVal in
                if let s = newVal {
                    UserDefaults.standard.set(s, forKey: HistoryPref.symbol)
                }
                Task { await load(useCache: true) }
            }
            .onChange(of: selectedSector) { _, newVal in
                if let s = newVal {
                    UserDefaults.standard.set(s, forKey: HistoryPref.sector)
                }
                Task { await load(useCache: true) }
            }
        }
    }

    // MARK: - Sub-pickers (no nil/placeholder row)

    @ViewBuilder
    private var subPicker: some View {
        switch mode {
        case .portfolio:
            EmptyView()

        case .account:
            if accounts.isEmpty {
                Text("No accounts available").font(.caption).foregroundStyle(.secondary)
            } else {
                Picker("Account", selection: Binding(
                    get: { selectedAccountId ?? accounts.first?.id },
                    set: { selectedAccountId = $0 }
                )) {
                    ForEach(accounts) { acct in
                        Text(acct.name).tag(Optional(acct.id))
                    }
                }
                .pickerStyle(.menu)
                .frame(maxWidth: .infinity, alignment: .leading)
            }

        case .symbol:
            if availableSymbols.isEmpty {
                Text("No equity symbols").font(.caption).foregroundStyle(.secondary)
            } else {
                Picker("Symbol", selection: Binding(
                    get: { selectedSymbol ?? availableSymbols.first },
                    set: { selectedSymbol = $0 }
                )) {
                    ForEach(availableSymbols, id: \.self) { sym in
                        Text(sym).tag(Optional(sym))
                    }
                }
                .pickerStyle(.menu)
                .frame(maxWidth: .infinity, alignment: .leading)
            }

        case .sector:
            if availableSectors.isEmpty {
                Text("No sectors mapped").font(.caption).foregroundStyle(.secondary)
            } else {
                Picker("Sector", selection: Binding(
                    get: { selectedSector ?? availableSectors.first },
                    set: { selectedSector = $0 }
                )) {
                    ForEach(availableSectors, id: \.self) { sec in
                        Text(sec).tag(Optional(sec))
                    }
                }
                .pickerStyle(.menu)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    // MARK: - Build picker options + restore/default selections

    private func buildPickerOptions() {
        let allPositions = (try? modelContext.fetch(FetchDescriptor<Position>())) ?? []
        availableSymbols = Array(Set(
            allPositions
                .filter { $0.category == Category.equity.rawValue }
                .map { $0.symbol }
        )).sorted()
        availableSectors = Array(Set(sectorMappings.map { $0.sector })).sorted()

        applyDefaultSelection()
    }

    /// Restore the last saved selection for the current mode, falling back to the first item.
    private func applyDefaultSelection() {
        switch mode {
        case .portfolio:
            break

        case .account:
            let saved = UserDefaults.standard.string(forKey: HistoryPref.accountId)
                .flatMap { UUID(uuidString: $0) }
            // Use saved if it still exists, otherwise first account
            if let id = saved, accounts.contains(where: { $0.id == id }) {
                selectedAccountId = id
            } else {
                selectedAccountId = accounts.first?.id
            }

        case .symbol:
            let saved = UserDefaults.standard.string(forKey: HistoryPref.symbol)
            if let s = saved, availableSymbols.contains(s) {
                selectedSymbol = s
            } else {
                selectedSymbol = availableSymbols.first
            }

        case .sector:
            let saved = UserDefaults.standard.string(forKey: HistoryPref.sector)
            if let s = saved, availableSectors.contains(s) {
                selectedSector = s
            } else {
                selectedSector = availableSectors.first
            }
        }
    }

    // MARK: - Load

    private func load(useCache: Bool) async {
        let allPositions = (try? modelContext.fetch(FetchDescriptor<Position>())) ?? []
        let allAccounts  = (try? modelContext.fetch(FetchDescriptor<Account>()))  ?? []
        let accountsMap  = Dictionary(uniqueKeysWithValues: allAccounts.map { ($0.id, $0) })
        let latestFx     = latestFxRates()
        let reporting    = AppSettingsStore.reportingCurrency

        switch mode {
        case .portfolio:
            await fetchAggregate(positions: allPositions, accounts: accountsMap, fx: latestFx, reporting: reporting, useCache: useCache)

        case .account:
            guard let accountId = selectedAccountId else { return }
            let filtered = allPositions.filter { $0.account?.id == accountId }
            await fetchAggregate(positions: filtered, accounts: accountsMap, fx: latestFx, reporting: reporting, useCache: useCache)

        case .symbol:
            guard let symbol = selectedSymbol else { return }
            let filtered = allPositions.filter {
                $0.symbol == symbol && $0.category == Category.equity.rawValue
            }
            guard !filtered.isEmpty else { points = []; return }
            isLoading = true; errorMessage = nil
            defer { isLoading = false }
            do {
                let priceHistory = try await appContainer.historyService.symbolHistory(
                    symbol: symbol, positions: filtered, useCache: useCache
                )
                let totalQty = filtered.reduce(0) { $0 + $1.quantity }
                let avgCost  = totalQty > 0 ? filtered.reduce(0) { $0 + $1.quantity * $1.costPerShare } / totalQty : 0
                let fxRate   = fxForSymbol(filtered[0], latestFx: latestFx, reporting: reporting)
                points = priceHistory.sorted { $0.key < $1.key }.map { dt, close in
                    HistoryPoint(
                        date: dt,
                        pnl: (close - avgCost) * totalQty * fxRate,
                        mtm: close * totalQty * fxRate
                    )
                }
            } catch {
                errorMessage = error.localizedDescription
            }

        case .sector:
            guard let sector = selectedSector else { return }
            let sm = Dictionary(uniqueKeysWithValues: sectorMappings.map { ($0.symbol, $0.sector) })
            let filtered = allPositions.filter {
                $0.category == Category.equity.rawValue && (sm[$0.symbol] ?? "Unspecified") == sector
            }
            await fetchAggregate(positions: filtered, accounts: accountsMap, fx: latestFx, reporting: reporting, useCache: useCache)
        }
    }

    private func fetchAggregate(
        positions: [Position],
        accounts: [UUID: Account],
        fx: [String: Double],
        reporting: String,
        useCache: Bool
    ) async {
        isLoading = true; errorMessage = nil
        defer { isLoading = false }
        do {
            points = try await appContainer.historyService.aggregateHistory(
                positions: positions,
                accounts: accounts,
                latestFx: fx,
                reportingCurrency: reporting,
                useCache: useCache
            )
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    // MARK: - Helpers

    private func latestFxRates() -> [String: Double] {
        let descriptor = FetchDescriptor<FxRate>(sortBy: [SortDescriptor(\.timestamp, order: .reverse)])
        let all = (try? modelContext.fetch(descriptor)) ?? []
        var result: [String: Double] = [:]
        for fx in all where result[fx.pair] == nil { result[fx.pair] = fx.rate }
        return result
    }

    private func fxForSymbol(_ pos: Position, latestFx: [String: Double], reporting: String) -> Double {
        let stockCcy = pos.currency.uppercased()
        let acctCcy  = (pos.account?.baseCurrency ?? reporting).uppercased()
        return PnLCalculator.lookupFx(latestFx, from: stockCcy, to: acctCcy)
             * PnLCalculator.lookupFx(latestFx, from: acctCcy, to: reporting)
    }
}
