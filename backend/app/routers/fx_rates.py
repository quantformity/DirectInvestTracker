import os
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import FxRate, Account, Position
from app.schemas import FxRateOut

router = APIRouter()


@router.get("/", response_model=list[FxRateOut])
def get_fx_rates(db: Session = Depends(get_db)):
    """Return the latest FX rate per pair."""
    subq = (
        db.query(
            FxRate.pair,
            func.max(FxRate.timestamp).label("max_ts"),
        )
        .group_by(FxRate.pair)
        .subquery()
    )
    rows = (
        db.query(FxRate)
        .join(subq, (FxRate.pair == subq.c.pair) & (FxRate.timestamp == subq.c.max_ts))
        .all()
    )
    return rows


@router.get("/matrix")
def get_fx_matrix(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return a full N×N cross-rate matrix for every currency used in the portfolio.

    Cell [from][to] = how many *to* units you get for 1 *from* unit.
    Missing pairs are computed by inversion or triangulation via the reporting
    currency; null is returned when a rate cannot be determined.
    """
    reporting_currency = os.getenv("REPORTING_CURRENCY", "CAD").upper()

    # Collect every distinct currency referenced in the portfolio
    currencies: set[str] = {reporting_currency}
    for acct in db.query(Account).all():
        if acct.base_currency:
            currencies.add(acct.base_currency.upper())
    for pos in db.query(Position).all():
        if pos.currency:
            currencies.add(pos.currency.upper())

    currencies_sorted = sorted(currencies)

    # Latest rate per pair
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
    rate_map: dict[str, float] = {r.pair: r.rate for r in rows}
    updated_at = max((r.timestamp for r in rows), default=None)

    def lookup(from_ccy: str, to_ccy: str) -> float | None:
        if from_ccy == to_ccy:
            return 1.0
        key, inv = f"{from_ccy}/{to_ccy}", f"{to_ccy}/{from_ccy}"
        if key in rate_map and rate_map[key] > 0:
            return rate_map[key]
        if inv in rate_map and rate_map[inv] > 0:
            return 1.0 / rate_map[inv]
        # Triangulate via reporting currency
        via = reporting_currency
        if from_ccy != via and to_ccy != via:
            a = lookup(from_ccy, via)
            b = lookup(via, to_ccy)
            if a is not None and b is not None:
                return a * b
        return None

    matrix: dict[str, dict[str, float | None]] = {
        from_ccy: {to_ccy: lookup(from_ccy, to_ccy) for to_ccy in currencies_sorted}
        for from_ccy in currencies_sorted
    }

    return {
        "currencies": currencies_sorted,
        "matrix": matrix,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }
