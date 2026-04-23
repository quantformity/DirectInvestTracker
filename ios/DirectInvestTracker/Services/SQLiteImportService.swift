import Foundation
import SQLite3
import SwiftData

// MARK: - Errors

enum ImportError: LocalizedError {
    case cannotOpenFile(String)
    case queryFailed(String)

    var errorDescription: String? {
        switch self {
        case .cannotOpenFile(let msg): return "Cannot open file: \(msg)"
        case .queryFailed(let msg):    return "Query failed: \(msg)"
        }
    }
}

// MARK: - Result

struct ImportSummary {
    let accounts:       Int
    let positions:      Int
    let marketData:     Int
    let fxRates:        Int
    let sectorMappings: Int

    var description: String {
        "Imported \(accounts) accounts, \(positions) positions, " +
        "\(marketData) market quotes, \(fxRates) FX rates, \(sectorMappings) sector mappings."
    }
}

// MARK: - Service

@MainActor
enum SQLiteImportService {

    /// Read `investments.db` at `url` and replace all SwiftData records.
    static func importFile(url: URL, context: ModelContext) throws -> ImportSummary {
        let accessed = url.startAccessingSecurityScopedResource()
        defer { if accessed { url.stopAccessingSecurityScopedResource() } }

        var db: OpaquePointer?
        let rc = sqlite3_open_v2(url.path, &db, SQLITE_OPEN_READONLY, nil)
        guard rc == SQLITE_OK, let db else {
            let msg = String(cString: sqlite3_errmsg(db))
            throw ImportError.cannotOpenFile(msg)
        }
        defer { sqlite3_close(db) }

        // ── 1. Read all data from SQLite ─────────────────────────────────────

        let rawAccounts      = try readAccounts(db)
        let rawPositions     = try readPositions(db)
        let rawMarketData    = try readMarketData(db)
        let rawFxRates       = try readFxRates(db)
        let rawSectorMap     = try readSectorMappings(db)

        // ── 2. Clear existing SwiftData records ──────────────────────────────

        for p in try context.fetch(FetchDescriptor<Position>())     { context.delete(p) }
        for a in try context.fetch(FetchDescriptor<Account>())      { context.delete(a) }
        for m in try context.fetch(FetchDescriptor<MarketData>())   { context.delete(m) }
        for f in try context.fetch(FetchDescriptor<FxRate>())       { context.delete(f) }
        for s in try context.fetch(FetchDescriptor<SectorMapping>()){ context.delete(s) }

        // ── 3. Insert accounts, build id → Account map ───────────────────────

        var accountMap: [Int: Account] = [:]
        for row in rawAccounts {
            let account = Account(name: row.name, baseCurrency: row.baseCurrency)
            context.insert(account)
            accountMap[row.pythonId] = account
        }

        // ── 4. Insert positions ───────────────────────────────────────────────

        for row in rawPositions {
            guard let account = accountMap[row.accountId] else { continue }
            let position = Position(
                symbol:       row.symbol,
                category:     row.category,
                quantity:     row.quantity,
                costPerShare: row.costPerShare,
                dateAdded:    row.dateAdded,
                yieldRate:    row.yieldRate,
                currency:     row.currency,
                account:      account
            )
            context.insert(position)
        }

        // ── 5. Insert market data ─────────────────────────────────────────────

        for row in rawMarketData {
            let md = MarketData(
                symbol:      row.symbol,
                companyName: row.companyName,
                lastPrice:   row.lastPrice,
                previousClose: nil,
                peRatio:     row.peRatio,
                changePercent: row.changePercent,
                changePercentSource: row.changePercent != nil ? "api" : nil,
                beta:        row.beta,
                timestamp:   row.timestamp
            )
            context.insert(md)
        }

        // ── 6. Insert FX rates ────────────────────────────────────────────────

        for row in rawFxRates {
            let fx = FxRate(pair: row.pair, rate: row.rate, timestamp: row.timestamp)
            context.insert(fx)
        }

        // ── 7. Insert sector mappings ─────────────────────────────────────────

        for row in rawSectorMap {
            context.insert(SectorMapping(symbol: row.symbol, sector: row.sector))
        }

        try context.save()

        return ImportSummary(
            accounts:       rawAccounts.count,
            positions:      rawPositions.count,
            marketData:     rawMarketData.count,
            fxRates:        rawFxRates.count,
            sectorMappings: rawSectorMap.count
        )
    }

    // MARK: - Raw row types

    private struct RawAccount  { let pythonId: Int; let name, baseCurrency: String }
    private struct RawPosition {
        let accountId: Int; let symbol, category, currency: String
        let quantity, costPerShare: Double; let dateAdded: Date; let yieldRate: Double?
    }
    private struct RawMarketData {
        let symbol: String; let lastPrice, changePercent, peRatio, beta: Double?
        let companyName: String?; let timestamp: Date
    }
    private struct RawFxRate    { let pair: String; let rate: Double; let timestamp: Date }
    private struct RawSectorMap { let symbol, sector: String }

    // MARK: - Readers

    private static func readAccounts(_ db: OpaquePointer) throws -> [RawAccount] {
        var rows: [RawAccount] = []
        try query(db, sql: "SELECT id, name, base_currency FROM accounts") { stmt in
            rows.append(RawAccount(
                pythonId:     Int(sqlite3_column_int(stmt, 0)),
                name:         string(stmt, 1),
                baseCurrency: string(stmt, 2)
            ))
        }
        return rows
    }

    private static func readPositions(_ db: OpaquePointer) throws -> [RawPosition] {
        var rows: [RawPosition] = []
        let sql = """
            SELECT account_id, symbol, category, quantity,
                   cost_per_share, date_added, yield_rate, currency
            FROM positions
            """
        try query(db, sql: sql) { stmt in
            rows.append(RawPosition(
                accountId:    Int(sqlite3_column_int(stmt, 0)),
                symbol:       string(stmt, 1),
                category:     string(stmt, 2),
                currency:     string(stmt, 7),
                quantity:     sqlite3_column_double(stmt, 3),
                costPerShare: sqlite3_column_double(stmt, 4),
                dateAdded:    parseDate(string(stmt, 5)) ?? Date(),
                yieldRate:    sqlite3_column_type(stmt, 6) == SQLITE_NULL ? nil : sqlite3_column_double(stmt, 6)
            ))
        }
        return rows
    }

    private static func readMarketData(_ db: OpaquePointer) throws -> [RawMarketData] {
        // Take only the latest row per symbol
        var rows: [RawMarketData] = []
        let sql = """
            SELECT symbol, last_price, change_percent, pe_ratio, beta, company_name, timestamp
            FROM market_data
            WHERE id IN (
                SELECT MAX(id) FROM market_data GROUP BY symbol
            )
            """
        try query(db, sql: sql) { stmt in
            rows.append(RawMarketData(
                symbol:        string(stmt, 0),
                lastPrice:     optDouble(stmt, 1),
                changePercent: optDouble(stmt, 2),
                peRatio:       optDouble(stmt, 3),
                beta:          optDouble(stmt, 4),
                companyName:   sqlite3_column_type(stmt, 5) == SQLITE_NULL ? nil : string(stmt, 5),
                timestamp:     parseTimestamp(string(stmt, 6)) ?? Date()
            ))
        }
        return rows
    }

    private static func readFxRates(_ db: OpaquePointer) throws -> [RawFxRate] {
        // Take only the latest row per pair
        var rows: [RawFxRate] = []
        let sql = """
            SELECT pair, rate, timestamp FROM fx_rates
            WHERE id IN (
                SELECT MAX(id) FROM fx_rates GROUP BY pair
            )
            """
        try query(db, sql: sql) { stmt in
            rows.append(RawFxRate(
                pair:      string(stmt, 0),
                rate:      sqlite3_column_double(stmt, 1),
                timestamp: parseTimestamp(string(stmt, 2)) ?? Date()
            ))
        }
        return rows
    }

    private static func readSectorMappings(_ db: OpaquePointer) throws -> [RawSectorMap] {
        var rows: [RawSectorMap] = []
        try query(db, sql: "SELECT symbol, sector FROM sector_mappings") { stmt in
            rows.append(RawSectorMap(symbol: string(stmt, 0), sector: string(stmt, 1)))
        }
        return rows
    }

    // MARK: - SQLite helpers

    private static func query(_ db: OpaquePointer, sql: String,
                               row: (OpaquePointer) -> Void) throws {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw ImportError.queryFailed(sql)
        }
        defer { sqlite3_finalize(stmt) }
        while sqlite3_step(stmt) == SQLITE_ROW { row(stmt!) }
    }

    private static func string(_ stmt: OpaquePointer, _ col: Int32) -> String {
        guard let ptr = sqlite3_column_text(stmt, col) else { return "" }
        return String(cString: ptr)
    }

    private static func optDouble(_ stmt: OpaquePointer, _ col: Int32) -> Double? {
        sqlite3_column_type(stmt, col) == SQLITE_NULL ? nil : sqlite3_column_double(stmt, col)
    }

    // MARK: - Date parsers

    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(secondsFromGMT: 0)
        return f
    }()

    private static let timestampFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(secondsFromGMT: 0)
        f.dateFormat = "yyyy-MM-dd HH:mm:ss.SSSSSS"
        return f
    }()

    private static let timestampFormatterShort: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(secondsFromGMT: 0)
        f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return f
    }()

    private static func parseDate(_ s: String) -> Date? {
        dateFormatter.date(from: s)
    }

    private static func parseTimestamp(_ s: String) -> Date? {
        timestampFormatter.date(from: s) ?? timestampFormatterShort.date(from: s)
    }
}
