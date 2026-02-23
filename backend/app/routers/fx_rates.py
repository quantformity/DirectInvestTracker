from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import FxRate
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
