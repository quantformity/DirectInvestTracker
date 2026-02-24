"""
Lightweight SQLite cache for Yahoo Finance historical price data.

Stored separately from the main DB so it can be wiped or relocated without
affecting positions/accounts.  Cache key = Yahoo Finance ticker (e.g. "AAPL",
"USDCAD=X").
"""

import os
import sqlite3
from datetime import date

import pandas as pd

from app.database import DATABASE_URL


def get_cache_path() -> str:
    """Return the absolute path to the history cache SQLite DB.

    Priority:
    1. ``history_cache_path`` row in the settings table (user-configured)
    2. Default: same directory as the main investments DB, named
       ``history_cache.db``
    """
    try:
        from app.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT value FROM settings WHERE key = 'history_cache_path'")
            ).fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass

    # Derive default from DATABASE_URL
    db_path = DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(os.path.abspath(db_path))
    return os.path.join(db_dir, "history_cache.db")


def _get_conn() -> sqlite3.Connection:
    path = get_cache_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS price_cache (
            cache_key  TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            close      REAL NOT NULL,
            PRIMARY KEY (cache_key, trade_date)
        )
        """
    )
    conn.commit()
    return conn


def read_cache(cache_key: str, start_date: date) -> pd.DataFrame:
    """Return cached close prices for *cache_key* from *start_date* onwards.

    Returns an empty DataFrame if no cache entry exists.
    The returned DataFrame has a ``date`` index and a ``Close`` column,
    matching the format returned by ``fetch_history``.
    """
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT trade_date, close FROM price_cache "
            "WHERE cache_key = ? AND trade_date >= ? ORDER BY trade_date",
            (cache_key, start_date.isoformat()),
        ).fetchall()
        conn.close()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=["Date", "Close"])
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
        df = df.set_index("Date")
        return df
    except Exception:
        return pd.DataFrame()


def write_cache(cache_key: str, df: pd.DataFrame) -> None:
    """Upsert price rows from *df* into the cache.

    *df* must have a date index and at least a ``Close`` column (same format
    as ``fetch_history`` output).  Silently ignores errors so a cache write
    failure never breaks a live request.
    """
    if df is None or df.empty:
        return
    try:
        conn = _get_conn()
        rows = [
            (
                cache_key,
                dt.isoformat() if hasattr(dt, "isoformat") else str(dt),
                float(row["Close"]),
            )
            for dt, row in df.iterrows()
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO price_cache (cache_key, trade_date, close) "
            "VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
