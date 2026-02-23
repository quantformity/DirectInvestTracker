"""
Yahoo Finance data fetcher.

Uses curl_cffi with Chrome impersonation so the TLS/JA3 fingerprint matches
a real browser — bypasses Yahoo Finance's bot detection inside Docker.

- quoteSummary endpoint: price, change%, PE ratio, beta (requires crumb)
- v8/chart endpoint: fallback for price + change% if crumb fails
"""
import logging
import threading
import time
from datetime import date, datetime
from typing import Optional

from curl_cffi import requests as cffi_requests
import pandas as pd

logger = logging.getLogger(__name__)

# Shared Chrome-impersonating session
_SESSION = cffi_requests.Session(impersonate="chrome120")

_SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
_CRUMB_URL   = "https://query2.finance.yahoo.com/v1/test/getcrumb"
_CHART_URL   = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

_crumb: str | None = None
_crumb_lock = threading.Lock()


def _get_crumb() -> str | None:
    """Fetch and cache a Yahoo Finance crumb (required for quoteSummary)."""
    global _crumb
    with _crumb_lock:
        if _crumb:
            return _crumb
        try:
            r = _SESSION.get(_CRUMB_URL, timeout=10)
            if r.status_code == 200 and r.text.strip():
                _crumb = r.text.strip()
                logger.info("Yahoo Finance crumb obtained")
                return _crumb
        except Exception as exc:
            logger.warning("Failed to get crumb: %s", exc)
        return None


def _fetch_one(symbol: str) -> tuple[str, dict]:
    """
    Fetch price, change%, PE ratio, and beta for one symbol.
    Uses quoteSummary (full data) with v8/chart as fallback.
    """
    global _crumb
    empty = {"last_price": None, "pe_ratio": None, "change_percent": None, "beta": None}

    crumb = _get_crumb()
    if crumb:
        try:
            r = _SESSION.get(
                _SUMMARY_URL.format(symbol=symbol),
                params={
                    "modules": "price,summaryDetail,defaultKeyStatistics",
                    "crumb": crumb,
                },
                timeout=15,
            )
            # Crumb expired — clear so next call re-fetches
            if r.status_code in (401, 403):
                with _crumb_lock:
                    _crumb = None
                raise ValueError("Crumb expired")
            r.raise_for_status()
            result = r.json().get("quoteSummary", {}).get("result") or []
            if result:
                price_d = result[0].get("price", {})
                summary = result[0].get("summaryDetail", {})
                stats   = result[0].get("defaultKeyStatistics", {})
                price   = (price_d.get("regularMarketPrice") or {}).get("raw")
                chg_raw = (price_d.get("regularMarketChangePercent") or {}).get("raw")
                pe      = ((summary.get("trailingPE") or {}).get("raw")
                           or (summary.get("forwardPE") or {}).get("raw"))
                beta    = (stats.get("beta") or {}).get("raw")
                return symbol, {
                    "last_price":     price,
                    "pe_ratio":       pe,
                    "change_percent": round(chg_raw * 100, 4) if chg_raw else None,
                    "beta":           beta,
                }
        except Exception as exc:
            logger.warning("quoteSummary failed for %s: %s — falling back to chart", symbol, exc)

    # Fallback: v8/chart (price + change% only, no PE/beta)
    try:
        r = _SESSION.get(
            _CHART_URL.format(symbol=symbol),
            params={"interval": "1d", "range": "2d"},
            timeout=15,
        )
        r.raise_for_status()
        result = r.json()["chart"]["result"]
        if result:
            meta  = result[0]["meta"]
            price = meta.get("regularMarketPrice")
            prev  = meta.get("chartPreviousClose")
            chg   = round((price - prev) / prev * 100, 4) if price and prev else None
            return symbol, {"last_price": price, "pe_ratio": None, "change_percent": chg, "beta": None}
    except Exception as exc:
        logger.warning("Failed to fetch price for %s: %s", symbol, exc)

    return symbol, empty


_FETCH_DELAY = 0.4  # seconds between requests


def fetch_prices(symbols: list[str]) -> dict[str, dict]:
    """
    Fetch price, change%, PE ratio, and beta for all symbols sequentially.
    Returns {symbol: {last_price, pe_ratio, change_percent, beta}}.
    """
    if not symbols:
        return {}

    results: dict[str, dict] = {}
    for i, sym in enumerate(symbols):
        if i > 0:
            time.sleep(_FETCH_DELAY)
        _, data = _fetch_one(sym)
        results[sym] = data
        if data["last_price"] is not None:
            logger.info(
                "Price %s → %.4f  chg=%.2f%%  PE=%s  beta=%s",
                sym, data["last_price"],
                data["change_percent"] or 0,
                f"{data['pe_ratio']:.1f}" if data["pe_ratio"] else "—",
                f"{data['beta']:.2f}" if data["beta"] else "—",
            )
    return results


def fetch_fx_rates_batch(pairs: list[tuple[str, str]]) -> dict[str, float]:
    """
    Fetch multiple FX rates sequentially via Yahoo Finance v8/chart.
    Returns {"FROM/TO": rate}.
    """
    result: dict[str, float] = {}
    to_fetch: list[tuple[str, str]] = []

    for from_ccy, to_ccy in pairs:
        f, t = from_ccy.upper(), to_ccy.upper()
        if f == t:
            result[f"{f}/{t}"] = 1.0
        else:
            to_fetch.append((f, t))

    for i, (f, t) in enumerate(to_fetch):
        if i > 0:
            time.sleep(_FETCH_DELAY)
        key = f"{f}/{t}"
        try:
            r = _SESSION.get(
                _CHART_URL.format(symbol=f"{f}{t}=X"),
                params={"interval": "1d", "range": "1d"},
                timeout=15,
            )
            r.raise_for_status()
            res = r.json()["chart"]["result"]
            if res:
                rate = res[0]["meta"].get("regularMarketPrice")
                if rate:
                    result[key] = float(rate)
                    logger.info("FX %s → %.6f", key, rate)
        except Exception as exc:
            logger.warning("Failed to fetch FX %s: %s", key, exc)

    return result


def fetch_fx_rate(from_currency: str, to_currency: str) -> Optional[float]:
    """Single FX rate lookup."""
    rates = fetch_fx_rates_batch([(from_currency, to_currency)])
    return rates.get(f"{from_currency.upper()}/{to_currency.upper()}")


def fetch_history(
    symbol: str,
    start_date: date,
    end_date: Optional[date] = None,
) -> pd.DataFrame:
    """Fetch daily OHLCV history for a symbol via curl_cffi (Chrome impersonation)."""
    if end_date is None:
        end_date = date.today()
    period1 = int(datetime.combine(start_date, datetime.min.time()).timestamp())
    period2 = int(datetime.combine(end_date,   datetime.max.time()).timestamp())
    try:
        r = _SESSION.get(
            _CHART_URL.format(symbol=symbol),
            params={"interval": "1d", "period1": period1, "period2": period2},
            timeout=30,
        )
        r.raise_for_status()
        result = r.json()["chart"]["result"]
        if not result:
            return pd.DataFrame()
        timestamps = result[0].get("timestamp", [])
        closes     = result[0]["indicators"]["quote"][0].get("close", [])
        dates  = [datetime.fromtimestamp(ts).date() for ts in timestamps]
        df = pd.DataFrame({"Close": closes}, index=dates)
        df.index.name = "Date"
        df["Close"] = df["Close"].ffill()   # fill gaps (halts, data holes) with previous price
        return df.dropna(subset=["Close"])  # still drops leading NaN (before first trade)
    except Exception as exc:
        logger.warning("Failed to fetch history for %s: %s", symbol, exc)
        return pd.DataFrame()
