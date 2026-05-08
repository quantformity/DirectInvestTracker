import os
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SellTransaction

router = APIRouter()


class SellTransactionOut(BaseModel):
    id: int
    account_id: int
    account_name: str
    symbol: str
    category: str
    quantity: float
    sell_price: float
    cost_per_share: float
    fee: float
    date: date
    stock_currency: str
    account_currency: str
    realized_pnl_stock: float
    realized_pnl_account: float
    realized_pnl_reporting: float
    fx_stock_to_account: float
    fx_account_to_reporting: float

    class Config:
        from_attributes = True


class RealizedPnLOut(BaseModel):
    transactions: list[SellTransactionOut]
    total_realized_pnl_reporting: float
    reporting_currency: str


@router.get("/", response_model=RealizedPnLOut)
def get_realized_pnl(account_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(SellTransaction)
    if account_id is not None:
        q = q.filter(SellTransaction.account_id == account_id)
    transactions = q.order_by(SellTransaction.date.desc(), SellTransaction.id.desc()).all()
    total = sum(t.realized_pnl_reporting for t in transactions)
    return RealizedPnLOut(
        transactions=transactions,
        total_realized_pnl_reporting=total,
        reporting_currency=os.getenv("REPORTING_CURRENCY", "CAD"),
    )
