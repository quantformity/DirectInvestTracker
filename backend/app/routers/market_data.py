from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import MarketData
from app.schemas import MarketDataOut
from app.services.scheduler import sync_market_data

router = APIRouter()


@router.get("/", response_model=list[MarketDataOut])
def get_market_data(db: Session = Depends(get_db)):
    """Return the latest market data row per symbol."""
    # Subquery: max timestamp per symbol
    subq = (
        db.query(
            MarketData.symbol,
            func.max(MarketData.timestamp).label("max_ts"),
        )
        .group_by(MarketData.symbol)
        .subquery()
    )
    rows = (
        db.query(MarketData)
        .join(subq, (MarketData.symbol == subq.c.symbol) & (MarketData.timestamp == subq.c.max_ts))
        .all()
    )
    return rows


@router.post("/refresh", status_code=202)
def refresh_market_data():
    """Trigger an immediate market data sync (runs in-process)."""
    sync_market_data()
    return {"message": "Market data refresh triggered"}
