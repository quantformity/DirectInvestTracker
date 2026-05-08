import Foundation
import SQLite3

// MARK: - Export Error

enum ExportError: LocalizedError {
    case cannotOpenFile(String)
    case executionFailed(String)

    var errorDescription: String? {
        switch self {
        case .cannotOpenFile(let msg):  return "Cannot open file: \(msg)"
        case .executionFailed(let msg): return "SQL execution failed: \(msg)"
        }
    }
}

// MARK: - SQLite Export Service

/// Writes all SwiftData records to a SQLite file matching the Python schema.
/// Full-overwrite strategy: DELETE all rows then re-insert within a single transaction.
enum SQLiteExportService {

    static func export(
        accounts: [Account],
        positions: [Position],
        marketData: [MarketData],
        fxRates: [FxRate],
        sectorMappings: [SectorMapping],
        sellTransactions: [SellTransaction] = [],
        to url: URL
    ) throws {
        var db: OpaquePointer?
        let rc = sqlite3_open_v2(
            url.path, &db,
            SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE,
            nil
        )
        guard rc == SQLITE_OK, let db else {
            let msg = db.map { String(cString: sqlite3_errmsg($0)) } ?? "open failed"
            throw ExportError.cannotOpenFile(msg)
        }
        defer { sqlite3_close(db) }

        // Prevent WAL files that confuse iCloud Drive
        try exec(db, "PRAGMA journal_mode=DELETE")

        try exec(db, "PRAGMA foreign_keys=OFF")

        // Create tables if they don't exist (mirrors Python SQLAlchemy schema)
        try createTables(db)

        // Single transaction for atomicity
        try exec(db, "BEGIN TRANSACTION")

        do {
            try exec(db, "DELETE FROM sell_transactions")
            try exec(db, "DELETE FROM sector_mappings")
            try exec(db, "DELETE FROM market_data")
            try exec(db, "DELETE FROM fx_rates")
            try exec(db, "DELETE FROM positions")
            try exec(db, "DELETE FROM accounts")

            // Build account UUID → SQL id map
            var accountSQLId: [UUID: Int] = [:]
            for account in accounts {
                let sqlId = try insertAccount(db, account: account)
                accountSQLId[account.id] = sqlId
            }

            for position in positions {
                guard let accountId = position.account.flatMap({ accountSQLId[$0.id] }) else { continue }
                try insertPosition(db, position: position, accountSQLId: accountId)
            }

            for md in marketData {
                try insertMarketData(db, md: md)
            }

            for fx in fxRates {
                try insertFxRate(db, fx: fx)
            }

            for sm in sectorMappings {
                try insertSectorMapping(db, sm: sm)
            }

            for tx in sellTransactions {
                try insertSellTransaction(db, tx: tx)
            }

            try exec(db, "COMMIT")
        } catch {
            try? exec(db, "ROLLBACK")
            throw error
        }
    }

    // MARK: - Table creation

    private static func createTables(_ db: OpaquePointer) throws {
        try exec(db, """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                base_currency TEXT NOT NULL DEFAULT 'CAD'
            )
            """)

        try exec(db, """
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER REFERENCES accounts(id),
                symbol TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity REAL NOT NULL,
                cost_per_share REAL NOT NULL,
                date_added TEXT NOT NULL,
                yield_rate REAL,
                currency TEXT NOT NULL DEFAULT 'CAD'
            )
            """)

        try exec(db, """
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                last_price REAL,
                change_percent REAL,
                pe_ratio REAL,
                beta REAL,
                company_name TEXT,
                timestamp TEXT NOT NULL
            )
            """)

        try exec(db, """
            CREATE TABLE IF NOT EXISTS fx_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair TEXT NOT NULL,
                rate REAL NOT NULL,
                timestamp TEXT NOT NULL
            )
            """)

        try exec(db, """
            CREATE TABLE IF NOT EXISTS sector_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                sector TEXT NOT NULL
            )
            """)

        try exec(db, """
            CREATE TABLE IF NOT EXISTS sell_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                account_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity REAL NOT NULL,
                sell_price REAL NOT NULL,
                cost_per_share REAL NOT NULL,
                fee REAL NOT NULL DEFAULT 0,
                date TEXT NOT NULL,
                stock_currency TEXT NOT NULL,
                account_currency TEXT NOT NULL,
                realized_pnl_stock REAL NOT NULL,
                realized_pnl_account REAL NOT NULL,
                realized_pnl_reporting REAL NOT NULL,
                fx_stock_to_account REAL NOT NULL DEFAULT 1,
                fx_account_to_reporting REAL NOT NULL DEFAULT 1
            )
            """)
    }

    // MARK: - Row inserts

    @discardableResult
    private static func insertAccount(_ db: OpaquePointer, account: Account) throws -> Int {
        if let pid = account.pythonId {
            try exec(db, """
                INSERT OR REPLACE INTO accounts(id, name, base_currency) VALUES (\(pid), ?, ?)
                """, params: [account.name, account.baseCurrency])
            return pid
        } else {
            try exec(db, "INSERT INTO accounts(name, base_currency) VALUES (?, ?)",
                     params: [account.name, account.baseCurrency])
            return Int(sqlite3_last_insert_rowid(db))
        }
    }

    private static func insertPosition(_ db: OpaquePointer, position: Position, accountSQLId: Int) throws {
        let dateStr = dateFormatter.string(from: position.dateAdded)

        if let pid = position.pythonId {
            if let yr = position.yieldRate {
                try exec(db, """
                    INSERT OR REPLACE INTO positions(id, account_id, symbol, category, quantity,
                        cost_per_share, date_added, yield_rate, currency)
                    VALUES (\(pid), \(accountSQLId), ?, ?, ?, ?, ?, ?, ?)
                    """, params: [position.symbol, position.category,
                                  position.quantity, position.costPerShare,
                                  dateStr, yr, position.currency])
            } else {
                try exec(db, """
                    INSERT OR REPLACE INTO positions(id, account_id, symbol, category, quantity,
                        cost_per_share, date_added, currency)
                    VALUES (\(pid), \(accountSQLId), ?, ?, ?, ?, ?, ?)
                    """, params: [position.symbol, position.category,
                                  position.quantity, position.costPerShare,
                                  dateStr, position.currency])
            }
        } else {
            if let yr = position.yieldRate {
                try exec(db, """
                    INSERT INTO positions(account_id, symbol, category, quantity,
                        cost_per_share, date_added, yield_rate, currency)
                    VALUES (\(accountSQLId), ?, ?, ?, ?, ?, ?, ?)
                    """, params: [position.symbol, position.category,
                                  position.quantity, position.costPerShare,
                                  dateStr, yr, position.currency])
            } else {
                try exec(db, """
                    INSERT INTO positions(account_id, symbol, category, quantity,
                        cost_per_share, date_added, currency)
                    VALUES (\(accountSQLId), ?, ?, ?, ?, ?, ?)
                    """, params: [position.symbol, position.category,
                                  position.quantity, position.costPerShare,
                                  dateStr, position.currency])
            }
        }
    }

    private static func insertMarketData(_ db: OpaquePointer, md: MarketData) throws {
        let tsStr = timestampFormatter.string(from: md.timestamp)
        // Use .map { $0 as Any } to ensure nil optionals become Optional<Any>.none, not Any(Optional.none)
        try exec(db, """
            INSERT INTO market_data(symbol, last_price, change_percent, pe_ratio, beta, company_name, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, params: [md.symbol,
                          md.lastPrice.map { $0 as Any },
                          md.changePercent.map { $0 as Any },
                          md.peRatio.map { $0 as Any },
                          md.beta.map { $0 as Any },
                          md.companyName.map { $0 as Any },
                          tsStr])
    }

    private static func insertFxRate(_ db: OpaquePointer, fx: FxRate) throws {
        let tsStr = timestampFormatter.string(from: fx.timestamp)
        try exec(db, "INSERT INTO fx_rates(pair, rate, timestamp) VALUES (?, ?, ?)",
                 params: [fx.pair, fx.rate, tsStr])
    }

    private static func insertSectorMapping(_ db: OpaquePointer, sm: SectorMapping) throws {
        try exec(db, "INSERT INTO sector_mappings(symbol, sector) VALUES (?, ?)",
                 params: [sm.symbol, sm.sector])
    }

    private static func insertSellTransaction(_ db: OpaquePointer, tx: SellTransaction) throws {
        let dateStr = dateFormatter.string(from: tx.date)
        if let pid = tx.pythonId {
            try exec(db, """
                INSERT OR REPLACE INTO sell_transactions(
                    id, account_id, account_name, symbol, category, quantity, sell_price,
                    cost_per_share, fee, date, stock_currency, account_currency,
                    realized_pnl_stock, realized_pnl_account, realized_pnl_reporting,
                    fx_stock_to_account, fx_account_to_reporting)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, params: [pid, tx.accountId, tx.accountName, tx.symbol, tx.category,
                              tx.quantity, tx.sellPrice, tx.costPerShare, tx.fee, dateStr,
                              tx.stockCurrency, tx.accountCurrency, tx.realizedPnlStock,
                              tx.realizedPnlAccount, tx.realizedPnlReporting,
                              tx.fxStockToAccount, tx.fxAccountToReporting])
        } else {
            try exec(db, """
                INSERT INTO sell_transactions(
                    account_id, account_name, symbol, category, quantity, sell_price,
                    cost_per_share, fee, date, stock_currency, account_currency,
                    realized_pnl_stock, realized_pnl_account, realized_pnl_reporting,
                    fx_stock_to_account, fx_account_to_reporting)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, params: [tx.accountId, tx.accountName, tx.symbol, tx.category,
                              tx.quantity, tx.sellPrice, tx.costPerShare, tx.fee, dateStr,
                              tx.stockCurrency, tx.accountCurrency, tx.realizedPnlStock,
                              tx.realizedPnlAccount, tx.realizedPnlReporting,
                              tx.fxStockToAccount, tx.fxAccountToReporting])
        }
    }

    // MARK: - SQLite helpers

    /// Execute a statement with no bound parameters.
    @discardableResult
    private static func exec(_ db: OpaquePointer, _ sql: String) throws -> Int {
        var errMsg: UnsafeMutablePointer<CChar>?
        guard sqlite3_exec(db, sql, nil, nil, &errMsg) == SQLITE_OK else {
            let msg = errMsg.map { String(cString: $0) } ?? sql
            sqlite3_free(errMsg)
            throw ExportError.executionFailed(msg)
        }
        return Int(sqlite3_last_insert_rowid(db))
    }

    /// Prepare, bind, and step a statement with mixed-type parameters.
    @discardableResult
    private static func exec(_ db: OpaquePointer, _ sql: String, params: [Any?]) throws -> Int {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw ExportError.executionFailed("prepare failed: \(sql)")
        }
        defer { sqlite3_finalize(stmt) }

        for (i, param) in params.enumerated() {
            let col = Int32(i + 1)
            switch param {
            case nil:
                sqlite3_bind_null(stmt, col)
            case let v as String:
                sqlite3_bind_text(stmt, col, v, -1, SQLITE_TRANSIENT)
            case let v as Double:
                sqlite3_bind_double(stmt, col, v)
            case let v as Int:
                sqlite3_bind_int64(stmt, col, Int64(v))
            default:
                // Fallback: try to bind as text
                let str = "\(param!)"
                sqlite3_bind_text(stmt, col, str, -1, SQLITE_TRANSIENT)
            }
        }

        guard sqlite3_step(stmt) == SQLITE_DONE else {
            throw ExportError.executionFailed("step failed: \(sql)")
        }
        return Int(sqlite3_last_insert_rowid(db))
    }

    // MARK: - Date formatters

    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(secondsFromGMT: 0)
        return f
    }()

    private static let timestampFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(secondsFromGMT: 0)
        return f
    }()
}

// SQLite transient helper
private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
