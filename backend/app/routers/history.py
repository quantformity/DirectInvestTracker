import os
import time
from collections import defaultdict
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Position, Account, CategoryEnum, FxRate
from app.schemas import HistoryOut, HistoryPoint
from app.services.yahoo_finance import fetch_history

router = APIRouter()

_HISTORY_DELAY = 0.3  # seconds between symbol fetches in aggregate


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


@router.get("/aggregate", response_model=HistoryOut)
def get_aggregate_history(
    account_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Aggregate historical PnL/MTM across all equity positions,
    optionally filtered to a single account. Values in reporting currency.
    Per-date historical FX rates are used where available.
    """
    reporting_currency = os.getenv("REPORTING_CURRENCY", "CAD").upper()

    q = db.query(Position).filter(Position.category == CategoryEnum.Equity)
    if account_id is not None:
        q = q.filter(Position.account_id == account_id)
    positions = q.all()
    if not positions:
        raise HTTPException(status_code=404, detail="No equity positions found")

    accounts = {a.id: a for a in db.query(Account).all()}
    latest_fx = _get_fx_rates(db)  # fallback when historical FX unavailable

    # Group positions by symbol
    sym_groups: dict[str, list[Position]] = defaultdict(list)
    for p in positions:
        sym_groups[p.symbol].append(p)

    # ── Fetch historical FX rates for every currency pair we'll need ──────────
    overall_earliest = min(p.date_added for p in positions)
    fx_pairs_needed: set[tuple[str, str]] = set()
    for sym_positions in sym_groups.values():
        stock_ccy = sym_positions[0].currency.upper()
        acct = accounts.get(sym_positions[0].account_id)
        acct_ccy = acct.base_currency.upper() if acct else reporting_currency
        if stock_ccy != acct_ccy:
            fx_pairs_needed.add((stock_ccy, acct_ccy))
        if acct_ccy != reporting_currency:
            fx_pairs_needed.add((acct_ccy, reporting_currency))

    # hist_fx["USD/CAD"] = {date: rate, ...}
    hist_fx: dict[str, dict] = {}
    for from_ccy, to_ccy in fx_pairs_needed:
        time.sleep(_HISTORY_DELAY)
        fx_df = fetch_history(f"{from_ccy}{to_ccy}=X", start_date=overall_earliest)
        if not fx_df.empty:
            hist_fx[f"{from_ccy}/{to_ccy}"] = dict(zip(fx_df.index, fx_df["Close"]))

    def _fx_on_date(from_ccy: str, to_ccy: str, dt) -> float:
        """Return the FX rate for a specific date; falls back to the latest DB rate."""
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

    # ── Fetch all symbol DataFrames first ─────────────────────────────────────
    # We need all DFs up-front so we can build the union of trading dates and
    # reindex each symbol to it — preventing drops when exchanges have different
    # holiday calendars (e.g. TSX closed on Victoria Day, NYSE open).
    sym_dfs: dict[str, tuple[pd.DataFrame, list[Position]]] = {}
    for i, (symbol, sym_positions) in enumerate(sym_groups.items()):
        if i > 0:
            time.sleep(_HISTORY_DELAY)
        earliest = min(p.date_added for p in sym_positions)
        df = fetch_history(symbol, start_date=earliest)
        if not df.empty:
            sym_dfs[symbol] = (df, sym_positions)

    if not sym_dfs:
        raise HTTPException(status_code=503, detail="Could not fetch historical data")

    # Build union of every date any symbol has a price for
    all_dates = sorted(set().union(*[df.index for df, _ in sym_dfs.values()]))

    # ── Accumulate equity: reindex each symbol to all_dates then ffill ────────
    combined: dict = defaultdict(lambda: {"pnl": 0.0, "mtm": 0.0, "cash_gic": 0.0})

    for symbol, (df, sym_positions) in sym_dfs.items():
        total_qty = sum(p.quantity for p in sym_positions)
        avg_cost = sum(p.quantity * p.cost_per_share for p in sym_positions) / total_qty

        stock_ccy = sym_positions[0].currency.upper()
        acct = accounts.get(sym_positions[0].account_id)
        acct_ccy = acct.base_currency.upper() if acct else reporting_currency

        # Reindex to the combined date universe, ffill across exchange holiday gaps,
        # then dropna so dates before this symbol's first price are excluded.
        df_aligned = df.reindex(all_dates).ffill().dropna(subset=["Close"])

        for dt, row in df_aligned.iterrows():
            close = float(row["Close"])
            fx = _fx_on_date(stock_ccy, acct_ccy, dt) * _fx_on_date(acct_ccy, reporting_currency, dt)
            combined[dt]["mtm"] += close * total_qty * fx
            combined[dt]["pnl"] += (close - avg_cost) * total_qty * fx

    # ── Add Cash and GIC contributions to every chart date ────────────────────
    from datetime import date as date_type
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
                continue  # position not yet open on this date

            if cat == "Cash":
                mtm_pos = pos.quantity * pos.cost_per_share
                pnl_pos = 0.0
            else:  # GIC
                days = (dt - pos.date_added).days
                spot = pos.cost_per_share * (1 + (pos.yield_rate or 0.0) * days / 365)
                mtm_pos = spot * pos.quantity
                pnl_pos = (spot - pos.cost_per_share) * pos.quantity

            fx = _fx_on_date(pos_ccy, acct_ccy, dt) * _fx_on_date(acct_ccy, reporting_currency, dt)
            combined[dt]["mtm"]     += mtm_pos * fx
            combined[dt]["pnl"]     += pnl_pos * fx
            combined[dt]["cash_gic"] += mtm_pos * fx   # running total for the dedicated line

    label = "Portfolio" if account_id is None else (accounts[account_id].name if account_id in accounts else f"Account {account_id}")
    points = [
        HistoryPoint(date=dt, close_price=0.0, pnl=v["pnl"], mtm=v["mtm"], cash_gic=v["cash_gic"])
        for dt, v in sorted(combined.items())
    ]
    return HistoryOut(symbol=label, account_id=account_id, points=points)


@router.get("/", response_model=HistoryOut)
def get_history(
    symbol: str = Query(..., description="Yahoo Finance symbol"),
    account_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Reconstructs historical PnL for a symbol (or specific position).
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

    df = fetch_history(symbol, start_date=earliest_date)
    if df.empty:
        raise HTTPException(status_code=503, detail=f"Could not fetch historical data for '{symbol}'")

    points = [
        HistoryPoint(date=dt, close_price=float(row["Close"]),
                     pnl=(float(row["Close"]) - avg_cost) * total_quantity,
                     mtm=float(row["Close"]) * total_quantity)
        for dt, row in df.iterrows()
    ]
    return HistoryOut(symbol=symbol, account_id=account_id, points=points)
