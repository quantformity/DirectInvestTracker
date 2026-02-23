import logging
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.models import Position, MarketData, FxRate, CategoryEnum
from app.services import yahoo_finance
from app.services.yahoo_finance import fetch_fx_rates_batch

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()
_sync_lock = threading.Lock()  # prevents concurrent scheduler + manual refresh runs

REPORTING_CURRENCY = "CAD"  # Default; overridden by env var at startup


def sync_market_data():
    """
    Fetch latest prices and FX rates, then upsert into the database.
    Runs every 5 minutes via APScheduler.
    """
    if not _sync_lock.acquire(blocking=False):
        logger.info("Sync already in progress — skipping")
        return
    import os
    reporting_currency = os.getenv("REPORTING_CURRENCY", "CAD")

    db = SessionLocal()
    try:
        # Collect distinct equity symbols
        positions = db.query(Position).all()
        equity_symbols = list({
            p.symbol for p in positions
            if p.category == CategoryEnum.Equity
        })

        # Collect distinct account currencies (for FX)
        from app.models import Account
        accounts = db.query(Account).all()
        account_map = {a.id: a for a in accounts}
        currencies = list({a.base_currency for a in accounts})

        # Collect position_currency → account_currency pairs needing FX
        fx_pairs: set[tuple[str, str]] = set()
        for pos in positions:
            acct = account_map.get(pos.account_id)
            if acct and pos.currency.upper() != acct.base_currency.upper():
                fx_pairs.add((pos.currency.upper(), acct.base_currency.upper()))

        # ── Prices ──────────────────────────────────────────────────────────
        if equity_symbols:
            price_data = yahoo_finance.fetch_prices(equity_symbols)
            for symbol, data in price_data.items():
                # Always insert a new row (latest per symbol is queried by MAX timestamp)
                row = MarketData(
                    symbol=symbol,
                    last_price=data["last_price"],
                    pe_ratio=data["pe_ratio"],
                    change_percent=data["change_percent"],
                    beta=data["beta"],
                    timestamp=datetime.utcnow(),
                )
                db.add(row)
            logger.info("Market data synced for %d symbols", len(equity_symbols))

        # ── FX Rates: batch all pairs in one download call ───────────────────
        all_fx_pairs: list[tuple[str, str]] = []
        for currency in currencies:
            if currency.upper() != reporting_currency.upper():
                all_fx_pairs.append((currency, reporting_currency))
        for pair in fx_pairs:
            all_fx_pairs.append(pair)

        if all_fx_pairs:
            fx_results = fetch_fx_rates_batch(all_fx_pairs)
            for pair_key, rate in fx_results.items():
                row = FxRate(
                    pair=pair_key,
                    rate=rate,
                    timestamp=datetime.utcnow(),
                )
                db.add(row)
            logger.info("FX synced for %d pairs", len(fx_results))

        db.commit()
        logger.info("Scheduler sync complete at %s", datetime.utcnow().isoformat())
    except Exception as exc:
        logger.error("Scheduler sync failed: %s", exc)
        db.rollback()
    finally:
        db.close()
        _sync_lock.release()


def start_scheduler():
    _scheduler.add_job(sync_market_data, "interval", minutes=5, id="market_sync", replace_existing=True)
    _scheduler.start()
    logger.info("APScheduler started — market sync every 5 minutes")


def shutdown_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
