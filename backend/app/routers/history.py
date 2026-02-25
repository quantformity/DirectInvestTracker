import os
import time
from collections import defaultdict
from datetime import date as date_type
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Position, Account, CategoryEnum, FxRate, IndustryMapping
from app.schemas import HistoryOut, HistoryPoint
from app.services.yahoo_finance import fetch_history
from app.services import history_cache

router = APIRouter()

_HISTORY_DELAY = 0.3  # seconds between Yahoo Finance fetches (rate-limit)


def _get_fx_rates(db: Session) -> dict[str, float]:
    subq = (
        db.query(FxRate.pair, func.max(FxRate.timestamp).label("max_ts"))
        .group_by(FxRate.pair)
        .subquery()
    )
    rows = (
        db.query(FxRate)
        .join(subq, (FxRate.pair == subq.c.pair) & (FxRate.timestamp == subq.c.max_ts))
        .all()
    )
    return {r.pair: r.rate for r in rows}


def _lookup_fx(fx_rates: dict, from_ccy: str, to_ccy: str) -> float:
    if from_ccy == to_ccy:
        return 1.0
    pair, inv = f"{from_ccy}/{to_ccy}", f"{to_ccy}/{from_ccy}"
    if pair in fx_rates:
        return fx_rates[pair]
    if inv in fx_rates and fx_rates[inv]:
        return 1.0 / fx_rates[inv]
    return 1.0


def _fetch_or_cache(cache_key: str, start_date: date_type, use_cache: bool) -> pd.DataFrame:
    """Return price history for *cache_key* from *start_date* onwards.

    When *use_cache* is True: read only from the local SQLite cache; never
    calls Yahoo Finance.  Returns an empty DataFrame on a cache miss.

    When *use_cache* is False: fetch live data from Yahoo Finance, write the
    result to the cache, then return it.
    """
    if use_cache:
        return history_cache.read_cache(cache_key, start_date)
    df = fetch_history(cache_key, start_date=start_date)
    if not df.empty:
        history_cache.write_cache(cache_key, df)
    return df


def _compute_equity_aggregate(
    equity_positions: list,
    accounts: dict,
    latest_fx: dict,
    reporting_currency: str,
    use_cache: bool,
) -> tuple[dict, list]:
    """
    Core equity aggregate computation.  Returns (combined, all_dates) where
    combined is a dict of date -> {"pnl": float, "mtm": float, "cash_gic": float}.
    """
    # Group positions by symbol
    sym_groups: dict[str, list] = defaultdict(list)
    for p in equity_positions:
        sym_groups[p.symbol].append(p)

    # ── Fetch historical FX rates for every currency pair we'll need ──────────
    overall_earliest = min(p.date_added for p in equity_positions)
    fx_pairs_needed: set[tuple[str, str]] = set()
    for sym_positions in sym_groups.values():
        stock_ccy = sym_positions[0].currency.upper()
        acct = accounts.get(sym_positions[0].account_id)
        acct_ccy = acct.base_currency.upper() if acct else reporting_currency
        if stock_ccy != acct_ccy:
            fx_pairs_needed.add((stock_ccy, acct_ccy))
        if acct_ccy != reporting_currency:
            fx_pairs_needed.add((acct_ccy, reporting_currency))

    hist_fx: dict[str, dict] = {}
    for from_ccy, to_ccy in fx_pairs_needed:
        if not use_cache:
            time.sleep(_HISTORY_DELAY)
        fx_df = _fetch_or_cache(f"{from_ccy}{to_ccy}=X", overall_earliest, use_cache)
        if not fx_df.empty:
            hist_fx[f"{from_ccy}/{to_ccy}"] = dict(zip(fx_df.index, fx_df["Close"]))

    def _fx_on_date(from_ccy: str, to_ccy: str, dt) -> float:
        if from_ccy == to_ccy:
            return 1.0
        key, inv = f"{from_ccy}/{to_ccy}", f"{to_ccy}/{from_ccy}"
        if key in hist_fx:
            rate = hist_fx[key].get(dt)
            if rate is not None and rate > 0:
                return float(rate)
        if inv in hist_fx:
            rate = hist_fx[inv].get(dt)
            if rate is not None and rate > 0:
                return 1.0 / float(rate)
        return _lookup_fx(latest_fx, from_ccy, to_ccy)

    # ── Fetch all symbol DataFrames ───────────────────────────────────────────
    sym_dfs: dict[str, tuple[pd.DataFrame, list]] = {}
    for i, (symbol, sym_positions) in enumerate(sym_groups.items()):
        if not use_cache and i > 0:
            time.sleep(_HISTORY_DELAY)
        earliest = min(p.date_added for p in sym_positions)
        df = _fetch_or_cache(symbol, earliest, use_cache)
        if not df.empty:
            sym_dfs[symbol] = (df, sym_positions)

    if not sym_dfs:
        return {}, []

    all_dates = sorted(set().union(*[df.index for df, _ in sym_dfs.values()]))

    combined: dict = defaultdict(lambda: {"pnl": 0.0, "mtm": 0.0, "cash_gic": 0.0})

    for symbol, (df, sym_positions) in sym_dfs.items():
        total_qty = sum(p.quantity for p in sym_positions)
        avg_cost = sum(p.quantity * p.cost_per_share for p in sym_positions) / total_qty

        stock_ccy = sym_positions[0].currency.upper()
        acct = accounts.get(sym_positions[0].account_id)
        acct_ccy = acct.base_currency.upper() if acct else reporting_currency

        df_aligned = df.reindex(all_dates).ffill().dropna(subset=["Close"])

        for dt, row in df_aligned.iterrows():
            close = float(row["Close"])
            fx = _fx_on_date(stock_ccy, acct_ccy, dt) * _fx_on_date(acct_ccy, reporting_currency, dt)
            combined[dt]["mtm"] += close * total_qty * fx
            combined[dt]["pnl"] += (close - avg_cost) * total_qty * fx

    return combined, all_dates


@router.get("/aggregate", response_model=HistoryOut)
def get_aggregate_history(
    account_id: Optional[int] = Query(default=None),
    use_cache: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """
    Aggregate historical PnL/MTM across all equity positions,
    optionally filtered to a single account. Values in reporting currency.
    Per-date historical FX rates are used where available.

    When ``use_cache=true`` the response is served from the local SQLite
    cache (fast).  When ``use_cache=false`` (default) data is fetched live
    from Yahoo Finance and the cache is updated.
    """
    reporting_currency = os.getenv("REPORTING_CURRENCY", "CAD").upper()

    q = db.query(Position).filter(Position.category == CategoryEnum.Equity)
    if account_id is not None:
        q = q.filter(Position.account_id == account_id)
    positions = q.all()
    if not positions:
        raise HTTPException(status_code=404, detail="No equity positions found")

    accounts = {a.id: a for a in db.query(Account).all()}
    latest_fx = _get_fx_rates(db)

    combined, all_dates = _compute_equity_aggregate(
        positions, accounts, latest_fx, reporting_currency, use_cache
    )

    if not combined:
        if use_cache:
            label = "Portfolio" if account_id is None else (
                accounts[account_id].name if account_id in accounts else f"Account {account_id}"
            )
            return HistoryOut(symbol=label, account_id=account_id, points=[])
        raise HTTPException(status_code=503, detail="Could not fetch historical data")

    # ── Add Cash and GIC contributions ───────────────────────────────────────
    non_eq_q = db.query(Position).filter(
        Position.category.in_([CategoryEnum.Cash, CategoryEnum.GIC])
    )
    if account_id is not None:
        non_eq_q = non_eq_q.filter(Position.account_id == account_id)

    for pos in non_eq_q.all():
        acct = accounts.get(pos.account_id)
        acct_ccy = acct.base_currency.upper() if acct else reporting_currency
        pos_ccy = pos.currency.upper()
        cat = pos.category.value if hasattr(pos.category, "value") else str(pos.category)

        for dt in all_dates:
            if dt < pos.date_added:
                continue

            if cat == "Cash":
                mtm_pos = pos.quantity * pos.cost_per_share
                pnl_pos = 0.0
            else:  # GIC
                days = (dt - pos.date_added).days
                spot = pos.cost_per_share * (1 + (pos.yield_rate or 0.0) * days / 365)
                mtm_pos = spot * pos.quantity
                pnl_pos = (spot - pos.cost_per_share) * pos.quantity

            fx = _lookup_fx(latest_fx, pos_ccy, acct_ccy) * _lookup_fx(latest_fx, acct_ccy, reporting_currency)
            combined[dt]["mtm"]      += mtm_pos * fx
            combined[dt]["pnl"]      += pnl_pos * fx
            combined[dt]["cash_gic"] += mtm_pos * fx

    label = "Portfolio" if account_id is None else (
        accounts[account_id].name if account_id in accounts else f"Account {account_id}"
    )
    points = [
        HistoryPoint(date=dt, close_price=0.0, pnl=v["pnl"], mtm=v["mtm"], cash_gic=v["cash_gic"])
        for dt, v in sorted(combined.items())
    ]
    return HistoryOut(symbol=label, account_id=account_id, points=points)


@router.get("/industry", response_model=HistoryOut)
def get_history_by_industry(
    industry: str = Query(..., description="Industry name to aggregate"),
    use_cache: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """
    Aggregate historical PnL/MTM for all equity positions belonging to a specific industry.
    Industry assignments come from the industry_mappings table.
    Symbols without a mapping are treated as 'Unspecified'.
    """
    reporting_currency = os.getenv("REPORTING_CURRENCY", "CAD").upper()

    mappings = {m.symbol: m.industry for m in db.query(IndustryMapping).all()}

    all_equity = db.query(Position).filter(Position.category == CategoryEnum.Equity).all()
    positions = [p for p in all_equity if mappings.get(p.symbol, "Unspecified") == industry]

    if not positions:
        raise HTTPException(
            status_code=404,
            detail=f"No equity positions found for industry '{industry}'"
        )

    accounts = {a.id: a for a in db.query(Account).all()}
    latest_fx = _get_fx_rates(db)

    combined, _ = _compute_equity_aggregate(
        positions, accounts, latest_fx, reporting_currency, use_cache
    )

    if not combined:
        if use_cache:
            return HistoryOut(symbol=industry, account_id=None, points=[])
        raise HTTPException(status_code=503, detail="Could not fetch historical data")

    points = [
        HistoryPoint(date=dt, close_price=0.0, pnl=v["pnl"], mtm=v["mtm"], cash_gic=0.0)
        for dt, v in sorted(combined.items())
    ]
    return HistoryOut(symbol=industry, account_id=None, points=points)


@router.get("/", response_model=HistoryOut)
def get_history(
    symbol: str = Query(..., description="Yahoo Finance symbol"),
    account_id: Optional[int] = Query(default=None),
    use_cache: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """
    Reconstructs historical PnL for a symbol (or specific position).

    When ``use_cache=true`` the response is served from the local SQLite
    cache (fast).  When ``use_cache=false`` (default) data is fetched live
    from Yahoo Finance and the cache is updated.
    """
    q = db.query(Position).filter(Position.symbol == symbol)
    if account_id is not None:
        q = q.filter(Position.account_id == account_id)

    positions = q.all()
    if not positions:
        raise HTTPException(status_code=404, detail=f"No positions found for symbol '{symbol}'")

    equity_positions = [p for p in positions if p.category == CategoryEnum.Equity]
    if not equity_positions:
        raise HTTPException(status_code=422, detail="Historical data is only available for Equity positions")

    earliest_date = min(p.date_added for p in equity_positions)
    total_quantity = sum(p.quantity for p in equity_positions)
    avg_cost = sum(p.quantity * p.cost_per_share for p in equity_positions) / total_quantity

    df = _fetch_or_cache(symbol, earliest_date, use_cache)
    if df.empty:
        if use_cache:
            return HistoryOut(symbol=symbol, account_id=account_id, points=[])
        raise HTTPException(status_code=503, detail=f"Could not fetch historical data for '{symbol}'")

    points = [
        HistoryPoint(
            date=dt,
            close_price=float(row["Close"]),
            pnl=(float(row["Close"]) - avg_cost) * total_quantity,
            mtm=float(row["Close"]) * total_quantity,
        )
        for dt, row in df.iterrows()
    ]
    return HistoryOut(symbol=symbol, account_id=account_id, points=points)
