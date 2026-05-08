from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from datetime import datetime

from app.database import get_db
import os
from app.models import Position, Account, CategoryEnum, FxRate, SellTransaction
from app.schemas import PositionCreate, PositionUpdate, PositionOut
from app.services.yahoo_finance import fetch_fx_rate


class PositionSell(BaseModel):
    quantity: float = Field(gt=0)
    price: float = Field(ge=0)
    fee: float = Field(ge=0, default=0.0)
    date: date_type = Field(default_factory=date_type.today)


class PositionSellResponse(BaseModel):
    position_id: int | None  # None if position was fully sold and deleted
    remaining_quantity: float
    net_cash: float
    currency: str

router = APIRouter()


def _latest_fx_rate(db: Session, from_ccy: str, to_ccy: str) -> float:
    """Latest FX rate with inverse fallback. Fetches live from Yahoo Finance if not in DB."""
    f, t = from_ccy.upper(), to_ccy.upper()
    if f == t:
        return 1.0
    row = (db.query(FxRate.rate)
           .filter(FxRate.pair == f"{f}/{t}")
           .order_by(FxRate.timestamp.desc())
           .first())
    if row:
        return row[0]
    row_inv = (db.query(FxRate.rate)
               .filter(FxRate.pair == f"{t}/{f}")
               .order_by(FxRate.timestamp.desc())
               .first())
    if row_inv and row_inv[0]:
        return 1.0 / row_inv[0]

    # Not in DB — fetch live and cache it
    rate = fetch_fx_rate(f, t)
    if rate:
        db.add(FxRate(pair=f"{f}/{t}", rate=rate, timestamp=datetime.utcnow()))
        return rate
    return 1.0


def _validate_position(payload_dict: dict):
    category = payload_dict.get("category")
    symbol = payload_dict.get("symbol", "")
    yield_rate = payload_dict.get("yield_rate")

    if category == CategoryEnum.GIC:
        if not yield_rate:
            raise HTTPException(
                status_code=422,
                detail="GIC positions must have a yield_rate"
            )
    elif category == CategoryEnum.Equity:
        if not symbol:
            raise HTTPException(
                status_code=422,
                detail="Equity positions must have a Yahoo Finance symbol"
            )


@router.get("/", response_model=list[PositionOut])
def list_positions(account_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Position)
    if account_id is not None:
        q = q.filter(Position.account_id == account_id)
    return q.all()


@router.post("/", response_model=PositionOut, status_code=201)
def create_position(payload: PositionCreate, db: Session = Depends(get_db)):
    # Validate account exists
    account = db.query(Account).filter(Account.id == payload.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    payload_dict = payload.model_dump()
    _validate_position(payload_dict)

    position = Position(**payload_dict)
    db.add(position)

    # Auto-create cash withdrawal in account currency, FX-converted from stock currency.
    if payload.category in (CategoryEnum.Equity, CategoryEnum.GIC) and payload.quantity > 0:
        total_cost_stock = payload.quantity * payload.cost_per_share
        fx = _latest_fx_rate(db, payload.currency, account.base_currency)
        cash_withdrawal = Position(
            account_id=payload.account_id,
            symbol="CASH",
            category=CategoryEnum.Cash,
            quantity=-(total_cost_stock * fx),
            cost_per_share=1.0,
            currency=account.base_currency,
            date_added=payload.date_added,
        )
        db.add(cash_withdrawal)

    db.commit()
    db.refresh(position)
    return position


@router.get("/{position_id}", response_model=PositionOut)
def get_position(position_id: int, db: Session = Depends(get_db)):
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


@router.put("/{position_id}", response_model=PositionOut)
def update_position(position_id: int, payload: PositionUpdate, db: Session = Depends(get_db)):
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Build merged dict for validation
    merged = {
        "category": update_data.get("category", position.category),
        "symbol": update_data.get("symbol", position.symbol),
        "yield_rate": update_data.get("yield_rate", position.yield_rate),
    }
    _validate_position(merged)

    for field, value in update_data.items():
        setattr(position, field, value)
    db.commit()
    db.refresh(position)
    return position


@router.delete("/{position_id}", status_code=204)
def delete_position(position_id: int, db: Session = Depends(get_db)):
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    db.delete(position)
    db.commit()


@router.post("/{position_id}/sell", response_model=PositionSellResponse)
def sell_position(position_id: int, payload: PositionSell, db: Session = Depends(get_db)):
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    if position.category not in (CategoryEnum.Equity, CategoryEnum.GIC):
        raise HTTPException(status_code=422, detail="Only Equity or GIC positions can be sold")

    if payload.quantity > position.quantity:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot sell {payload.quantity}; only {position.quantity} held",
        )

    account = db.query(Account).filter(Account.id == position.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    net_cash_stock = payload.quantity * payload.price - payload.fee

    # Deposit cash proceeds in account currency, FX-converted from stock currency.
    fx = _latest_fx_rate(db, position.currency, account.base_currency)
    net_cash_account = net_cash_stock * fx
    cash_deposit = Position(
        account_id=position.account_id,
        symbol="CASH",
        category=CategoryEnum.Cash,
        quantity=net_cash_account,
        cost_per_share=1.0,
        currency=account.base_currency,
        date_added=payload.date,
    )
    db.add(cash_deposit)

    # Record realized PnL for the sell transaction.
    reporting_currency = os.getenv("REPORTING_CURRENCY", "CAD")
    fx_account_to_reporting = _latest_fx_rate(db, account.base_currency, reporting_currency)
    realized_pnl_stock = payload.quantity * payload.price - payload.fee - payload.quantity * position.cost_per_share
    realized_pnl_account = realized_pnl_stock * fx
    db.add(SellTransaction(
        account_id=position.account_id,
        account_name=account.name,
        symbol=position.symbol,
        category=position.category,
        quantity=payload.quantity,
        sell_price=payload.price,
        cost_per_share=position.cost_per_share,
        fee=payload.fee,
        date=payload.date,
        stock_currency=position.currency,
        account_currency=account.base_currency,
        realized_pnl_stock=realized_pnl_stock,
        realized_pnl_account=realized_pnl_account,
        realized_pnl_reporting=realized_pnl_account * fx_account_to_reporting,
        fx_stock_to_account=fx,
        fx_account_to_reporting=fx_account_to_reporting,
    ))

    remaining = position.quantity - payload.quantity
    if remaining <= 0:
        db.delete(position)
        result_id: int | None = None
    else:
        position.quantity = remaining
        result_id = position.id

    db.commit()

    return PositionSellResponse(
        position_id=result_id,
        remaining_quantity=remaining,
        net_cash=net_cash_account,
        currency=account.base_currency,
    )
