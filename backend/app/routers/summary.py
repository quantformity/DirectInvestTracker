import os
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Position, Account, MarketData, FxRate, CategoryEnum
from app.schemas import EnrichedPosition, SummaryGroup, SummaryOut

router = APIRouter()

REPORTING_CURRENCY = os.getenv("REPORTING_CURRENCY", "CAD")


def _get_latest_prices(db: Session) -> dict[str, float]:
    """Return {symbol: last_price} for the most recent market data row per symbol."""
    subq = (
        db.query(MarketData.symbol, func.max(MarketData.timestamp).label("max_ts"))
        .group_by(MarketData.symbol)
        .subquery()
    )
    rows = (
        db.query(MarketData)
        .join(subq, (MarketData.symbol == subq.c.symbol) & (MarketData.timestamp == subq.c.max_ts))
        .all()
    )
    return {r.symbol: r.last_price for r in rows if r.last_price is not None}


def _get_latest_fx_rates(db: Session) -> dict[str, float]:
    """Return {pair: rate} for the most recent FX rate per pair."""
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


def _lookup_fx(fx_rates: dict[str, float], from_ccy: str, to_ccy: str) -> float:
    """Look up FX rate with inverse fallback. Returns 1.0 if same currency."""
    if from_ccy == to_ccy:
        return 1.0
    pair = f"{from_ccy}/{to_ccy}"
    pair_inv = f"{to_ccy}/{from_ccy}"
    if pair in fx_rates:
        return fx_rates[pair]
    if pair_inv in fx_rates and fx_rates[pair_inv] != 0:
        return 1.0 / fx_rates[pair_inv]
    return 1.0  # fallback


def _enrich_positions(
    positions: list[Position],
    prices: dict[str, float],
    fx_rates: dict[str, float],
    reporting_currency: str,
) -> list[EnrichedPosition]:
    enriched = []
    rep_currency = reporting_currency.upper()

    for p in positions:
        account: Account = p.account
        acct_currency = account.base_currency.upper()
        stock_currency = p.currency.upper()

        # Spot price in stock currency
        if p.category in (CategoryEnum.GIC, CategoryEnum.Cash, CategoryEnum.Dividend):
            spot = p.cost_per_share  # fixed at cost
        else:
            spot = prices.get(p.symbol, p.cost_per_share)

        # Two-hop FX
        fx_stock_to_account = _lookup_fx(fx_rates, stock_currency, acct_currency)
        fx_account_to_reporting = _lookup_fx(fx_rates, acct_currency, rep_currency)

        mtm_account = spot * p.quantity * fx_stock_to_account
        pnl_account = (spot - p.cost_per_share) * p.quantity * fx_stock_to_account
        mtm_reporting = mtm_account * fx_account_to_reporting
        pnl_reporting = pnl_account * fx_account_to_reporting

        enriched.append(EnrichedPosition(
            id=p.id,
            symbol=p.symbol,
            category=p.category,
            account_id=account.id,
            account_name=account.name,
            account_currency=acct_currency,
            quantity=p.quantity,
            cost_per_share=p.cost_per_share,
            date_added=p.date_added,
            yield_rate=p.yield_rate,
            stock_currency=stock_currency,
            spot_price=spot,
            fx_stock_to_account=fx_stock_to_account,
            fx_account_to_reporting=fx_account_to_reporting,
            mtm_account=mtm_account,
            pnl_account=pnl_account,
            mtm_reporting=mtm_reporting,
            pnl_reporting=pnl_reporting,
            proportion=0.0,  # filled after totals computed
        ))

    return enriched


@router.get("/", response_model=SummaryOut)
def get_summary(
    group_by: str = Query(default="category", enum=["category", "account", "symbol", "cash_gic"]),
    db: Session = Depends(get_db),
):
    reporting_currency = os.getenv("REPORTING_CURRENCY", REPORTING_CURRENCY)

    positions = db.query(Position).all()
    prices = _get_latest_prices(db)
    fx_rates = _get_latest_fx_rates(db)

    enriched = _enrich_positions(positions, prices, fx_rates, reporting_currency)

    total_mtm = sum(e.mtm_reporting for e in enriched) or 1.0
    total_pnl = sum(e.pnl_reporting for e in enriched)

    # Assign proportions
    for e in enriched:
        e.proportion = (e.mtm_reporting / total_mtm) * 100.0 if total_mtm else 0.0

    # Build groups
    group_map: dict[str, dict] = {}
    for e in enriched:
        if group_by == "category":
            key = e.category.value
        elif group_by == "account":
            key = e.account_name
        elif group_by == "symbol":
            key = e.symbol
        else:  # cash_gic
            key = "GIC/Cash" if e.category in (CategoryEnum.GIC, CategoryEnum.Cash) else "Other"

        if key not in group_map:
            group_map[key] = {"mtm": 0.0, "pnl": 0.0}
        group_map[key]["mtm"] += e.mtm_reporting
        group_map[key]["pnl"] += e.pnl_reporting

    groups = [
        SummaryGroup(
            group_key=k,
            total_mtm_reporting=v["mtm"],
            total_pnl_reporting=v["pnl"],
            proportion=(v["mtm"] / total_mtm * 100.0) if total_mtm else 0.0,
        )
        for k, v in group_map.items()
    ]

    return SummaryOut(
        positions=enriched,
        groups=groups,
        total_mtm_reporting=total_mtm,
        total_pnl_reporting=total_pnl,
        reporting_currency=reporting_currency,
    )
