#!/usr/bin/env python3
"""
sync_prices.py — Run on the Mac host (NOT inside Docker).

Fetches live stock prices and FX rates via Yahoo Finance and writes them
directly into the investments SQLite database.

Usage:
    python3 scripts/sync_prices.py          # run once
    python3 scripts/sync_prices.py --watch  # run every 5 minutes

Cron (every 5 min):
    */5 * * * * /usr/bin/python3 /Users/chup/workspace-local/investments/scripts/sync_prices.py
"""

import argparse
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent.parent / "backend" / "data" / "investments.db"
REPORTING_CURRENCY = "CAD"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
DELAY = 0.5  # seconds between requests

_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
})


# ── Fetch helpers ─────────────────────────────────────────────────────────────

def fetch_price(symbol: str) -> dict:
    """Fetch latest price for one symbol via Yahoo Finance v8/chart."""
    try:
        r = _session.get(
            CHART_URL.format(symbol=symbol),
            params={"interval": "1d", "range": "2d"},
            timeout=15,
        )
        r.raise_for_status()
        result = r.json()["chart"]["result"]
        if not result:
            print(f"  ✗ {symbol}: no data returned")
            return {}
        meta = result[0]["meta"]
        price = meta.get("regularMarketPrice")
        prev  = meta.get("chartPreviousClose")
        change_pct = round((price - prev) / prev * 100, 4) if price and prev else None
        print(f"  ✓ {symbol}: {price:.4f}  ({'+' if (change_pct or 0) >= 0 else ''}{change_pct:.2f}%)")
        return {
            "last_price":      price,
            "pe_ratio":        None,
            "change_percent":  change_pct,
            "beta":            None,
        }
    except Exception as e:
        print(f"  ✗ {symbol}: {e}")
        return {}


def fetch_fx(from_ccy: str, to_ccy: str) -> float | None:
    """Fetch FX rate for from_ccy → to_ccy."""
    if from_ccy == to_ccy:
        return 1.0
    ticker = f"{from_ccy}{to_ccy}=X"
    try:
        r = _session.get(
            CHART_URL.format(symbol=ticker),
            params={"interval": "1d", "range": "1d"},
            timeout=15,
        )
        r.raise_for_status()
        result = r.json()["chart"]["result"]
        if result:
            rate = result[0]["meta"].get("regularMarketPrice")
            if rate:
                print(f"  ✓ FX {from_ccy}/{to_ccy}: {rate:.6f}")
                return float(rate)
    except Exception as e:
        print(f"  ✗ FX {from_ccy}/{to_ccy}: {e}")
    return None


# ── Main sync ─────────────────────────────────────────────────────────────────

def sync():
    print(f"\n{'─'*50}")
    print(f"  Sync started at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'─'*50}")

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")  # allow concurrent reads from Docker
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        # ── Collect symbols ──────────────────────────────────────────────────
        equity_symbols = [
            row[0] for row in conn.execute(
                "SELECT DISTINCT symbol FROM positions WHERE category = 'Equity'"
            ).fetchall()
        ]

        # ── Collect FX pairs needed ──────────────────────────────────────────
        accounts = dict(conn.execute("SELECT id, base_currency FROM accounts").fetchall())
        positions = conn.execute("SELECT currency, account_id FROM positions").fetchall()

        fx_pairs: set[tuple[str, str]] = set()
        for pos_ccy, acct_id in positions:
            acct_ccy = accounts.get(acct_id, REPORTING_CURRENCY)
            if pos_ccy.upper() != acct_ccy.upper():
                fx_pairs.add((pos_ccy.upper(), acct_ccy.upper()))
            if acct_ccy.upper() != REPORTING_CURRENCY.upper():
                fx_pairs.add((acct_ccy.upper(), REPORTING_CURRENCY.upper()))

        # ── Fetch prices ─────────────────────────────────────────────────────
        print(f"\nPrices ({len(equity_symbols)} symbols):")
        for i, symbol in enumerate(equity_symbols):
            if i > 0:
                time.sleep(DELAY)
            data = fetch_price(symbol)
            if data:
                conn.execute(
                    """INSERT INTO market_data
                       (symbol, last_price, pe_ratio, change_percent, beta, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (symbol, data["last_price"], data["pe_ratio"],
                     data["change_percent"], data["beta"], now),
                )

        # ── Fetch FX rates ───────────────────────────────────────────────────
        print(f"\nFX rates ({len(fx_pairs)} pairs):")
        for i, (from_ccy, to_ccy) in enumerate(sorted(fx_pairs)):
            if i > 0:
                time.sleep(DELAY)
            rate = fetch_fx(from_ccy, to_ccy)
            if rate is not None:
                conn.execute(
                    "INSERT INTO fx_rates (pair, rate, timestamp) VALUES (?, ?, ?)",
                    (f"{from_ccy}/{to_ccy}", rate, now),
                )

        conn.commit()
        print(f"\n  ✅ Done at {datetime.now().strftime('%H:%M:%S')}\n")

    except Exception as e:
        print(f"\n  ✗ Sync failed: {e}")
        conn.rollback()
    finally:
        conn.close()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="Run every 5 minutes")
    parser.add_argument("--interval", type=int, default=300, help="Interval in seconds (default: 300)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    if args.watch:
        print(f"Watching — syncing every {args.interval}s. Press Ctrl+C to stop.")
        while True:
            sync()
            time.sleep(args.interval)
    else:
        sync()
