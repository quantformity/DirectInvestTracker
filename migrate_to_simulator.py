#!/usr/bin/env python3
"""
Migrates data from the backend SQLite DB into the iOS Simulator's SwiftData store.

Source:  investments.db  (SQLAlchemy / FastAPI schema)
Target:  DirectInvestTracker.store  (SwiftData / CoreData schema)

Run after terminating the app in the simulator.
"""
import sqlite3
import uuid
import sys
from datetime import datetime, date, timezone

# ── Paths ─────────────────────────────────────────────────────────────────────

SOURCE_DB = (
    "/Users/chupcheng/Library/Mobile Documents/"
    "com~apple~CloudDocs/Documents/Personal/financial/investments.db"
)

SWIFTDATA_DB = (
    "/Users/chupcheng/Library/Developer/CoreSimulator/Devices/"
    "22DABA2C-EC2C-4D47-B0D7-0B35F1FF7F65/data/Containers/Data/Application/"
    "D7F3296B-11B9-455F-864E-18D6D188A242/Library/Application Support/"
    "DirectInvestTracker.store"
)

# ── SwiftData entity numbers (from Z_PRIMARYKEY) ──────────────────────────────
Z_ENT = {
    "Account":       1,
    "AppSettings":   2,
    "FxRate":        3,
    "MarketData":    4,
    "Position":      5,
    "PriceCache":    6,
    "SectorMapping": 7,
}

# ── Date helpers ──────────────────────────────────────────────────────────────
# CoreData epoch = 2001-01-01 00:00:00 UTC
COREDATA_EPOCH_OFFSET = 978307200.0  # seconds from Unix epoch to CoreData epoch

def to_cd_timestamp(dt) -> float:
    """Convert a datetime/date/string to a CoreData timestamp (float)."""
    if dt is None:
        return None
    if isinstance(dt, str):
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(dt, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime(dt.year, dt.month, dt.day)
    unix_ts = dt.replace(tzinfo=timezone.utc).timestamp()
    return unix_ts - COREDATA_EPOCH_OFFSET

def uuid_blob(u: uuid.UUID) -> bytes:
    """Return UUID as 16-byte big-endian blob (CoreData format)."""
    return u.bytes

# ── Connect ───────────────────────────────────────────────────────────────────

src = sqlite3.connect(SOURCE_DB)
src.row_factory = sqlite3.Row
dst = sqlite3.connect(SWIFTDATA_DB)

# ── Clear existing data ───────────────────────────────────────────────────────

print("Clearing existing SwiftData rows …")
dst.execute("DELETE FROM ZPOSITION")
dst.execute("DELETE FROM ZACCOUNT")
dst.execute("DELETE FROM ZFXRATE")
dst.execute("DELETE FROM ZMARKETDATA")
dst.execute("DELETE FROM ZSECTORMAPPING")
dst.execute("UPDATE Z_PRIMARYKEY SET Z_MAX = 0")
dst.commit()

# ── Accounts ──────────────────────────────────────────────────────────────────

print("Migrating accounts …")
accounts = src.execute("SELECT id, name, base_currency FROM accounts").fetchall()

# Map old integer id → (new Z_PK, new UUID blob)
account_map: dict[int, tuple[int, bytes]] = {}
z_pk = 0
for row in accounts:
    z_pk += 1
    new_uuid = uuid.uuid4()
    account_map[row["id"]] = (z_pk, uuid_blob(new_uuid))
    dst.execute(
        "INSERT INTO ZACCOUNT (Z_PK, Z_ENT, Z_OPT, ZID, ZNAME, ZBASECURRENCY) VALUES (?,?,?,?,?,?)",
        (z_pk, Z_ENT["Account"], 1, uuid_blob(new_uuid), row["name"], row["base_currency"])
    )

dst.execute("UPDATE Z_PRIMARYKEY SET Z_MAX=? WHERE Z_NAME='Account'", (z_pk,))
print(f"  → {len(accounts)} accounts inserted")

# ── Positions ─────────────────────────────────────────────────────────────────

print("Migrating positions …")
positions = src.execute(
    "SELECT id, account_id, symbol, category, quantity, cost_per_share, "
    "date_added, yield_rate, currency FROM positions"
).fetchall()

z_pk = 0
for row in positions:
    if row["account_id"] not in account_map:
        print(f"  ⚠ Skipping position {row['id']}: unknown account_id {row['account_id']}")
        continue
    z_pk += 1
    acct_zpk, acct_uuid = account_map[row["account_id"]]
    date_ts = to_cd_timestamp(row["date_added"])
    new_uuid = uuid.uuid4()

    # Normalise category string to match our Category enum raw values
    cat = str(row["category"]).strip()
    cat_map = {"equity": "Equity", "gic": "GIC", "cash": "Cash", "dividend": "Dividend"}
    cat = cat_map.get(cat.lower(), cat)

    dst.execute(
        "INSERT INTO ZPOSITION "
        "(Z_PK, Z_ENT, Z_OPT, ZID, ZACCOUNT, ZSYMBOL, ZCATEGORY, ZQUANTITY, "
        " ZCOSTPERSHARE, ZDATEADDED, ZYIELDRATE, ZCURRENCY) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (z_pk, Z_ENT["Position"], 1, uuid_blob(new_uuid), acct_zpk,
         row["symbol"], cat, row["quantity"], row["cost_per_share"],
         date_ts, row["yield_rate"], row["currency"])
    )

dst.execute("UPDATE Z_PRIMARYKEY SET Z_MAX=? WHERE Z_NAME='Position'", (z_pk,))
print(f"  → {z_pk} positions inserted")

# ── FX Rates (latest per pair only) ──────────────────────────────────────────

print("Migrating FX rates (latest per pair) …")
fx_rows = src.execute(
    "SELECT pair, rate, timestamp FROM fx_rates "
    "WHERE (pair, timestamp) IN "
    "(SELECT pair, MAX(timestamp) FROM fx_rates GROUP BY pair)"
).fetchall()

z_pk = 0
for row in fx_rows:
    z_pk += 1
    ts = to_cd_timestamp(row["timestamp"])
    new_uuid = uuid.uuid4()
    dst.execute(
        "INSERT INTO ZFXRATE (Z_PK, Z_ENT, Z_OPT, ZID, ZPAIR, ZRATE, ZTIMESTAMP) VALUES (?,?,?,?,?,?,?)",
        (z_pk, Z_ENT["FxRate"], 1, uuid_blob(new_uuid), row["pair"], row["rate"], ts)
    )

dst.execute("UPDATE Z_PRIMARYKEY SET Z_MAX=? WHERE Z_NAME='FxRate'", (z_pk,))
print(f"  → {z_pk} FX rates inserted")

# ── Market Data (latest per symbol only) ─────────────────────────────────────

print("Migrating market data (latest per symbol) …")
md_rows = src.execute(
    "SELECT symbol, company_name, last_price, pe_ratio, change_percent, beta, timestamp "
    "FROM market_data "
    "WHERE (symbol, timestamp) IN "
    "(SELECT symbol, MAX(timestamp) FROM market_data GROUP BY symbol)"
).fetchall()

z_pk = 0
for row in md_rows:
    z_pk += 1
    ts = to_cd_timestamp(row["timestamp"])
    new_uuid = uuid.uuid4()
    dst.execute(
        "INSERT INTO ZMARKETDATA "
        "(Z_PK, Z_ENT, Z_OPT, ZID, ZSYMBOL, ZCOMPANYNAME, ZLASTPRICE, ZPERATIO, "
        " ZCHANGEPERCENT, ZBETA, ZTIMESTAMP) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (z_pk, Z_ENT["MarketData"], 1, uuid_blob(new_uuid),
         row["symbol"], row["company_name"], row["last_price"],
         row["pe_ratio"], row["change_percent"], row["beta"], ts)
    )

dst.execute("UPDATE Z_PRIMARYKEY SET Z_MAX=? WHERE Z_NAME='MarketData'", (z_pk,))
print(f"  → {z_pk} market data rows inserted")

# ── Sector Mappings ───────────────────────────────────────────────────────────

print("Migrating sector mappings …")
sm_rows = src.execute("SELECT symbol, sector FROM sector_mappings").fetchall()

z_pk = 0
for row in sm_rows:
    z_pk += 1
    dst.execute(
        "INSERT INTO ZSECTORMAPPING (Z_PK, Z_ENT, Z_OPT, ZSYMBOL, ZSECTOR) VALUES (?,?,?,?,?)",
        (z_pk, Z_ENT["SectorMapping"], 1, row["symbol"], row["sector"])
    )

dst.execute("UPDATE Z_PRIMARYKEY SET Z_MAX=? WHERE Z_NAME='SectorMapping'", (z_pk,))
print(f"  → {z_pk} sector mappings inserted")

# ── Commit & verify ───────────────────────────────────────────────────────────

dst.commit()
src.close()
dst.close()

print("\nVerifying …")
dst = sqlite3.connect(SWIFTDATA_DB)
for table, label in [("ZACCOUNT","accounts"), ("ZPOSITION","positions"),
                      ("ZFXRATE","fx_rates"), ("ZMARKETDATA","market_data"),
                      ("ZSECTORMAPPING","sector_mappings")]:
    count = dst.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  {table}: {count} rows")
dst.close()

print("\n✓ Migration complete — relaunch the app in the simulator.")
