from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Position, Account, CategoryEnum
from app.schemas import PositionCreate, PositionUpdate, PositionOut


class PositionSell(BaseModel):
    quantity: float = Field(gt=0)
    price: float = Field(ge=0)
    fee: float = Field(ge=0, default=0.0)
    date: date = Field(default_factory=date.today)


class PositionSellResponse(BaseModel):
    position_id: int | None  # None if position was fully sold and deleted
    remaining_quantity: float
    net_cash: float
    currency: str

router = APIRouter()


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

    # Auto-create a corresponding cash withdrawal for Equity/GIC purchases
    if payload.category in (CategoryEnum.Equity, CategoryEnum.GIC) and payload.quantity > 0:
        total_cost = payload.quantity * payload.cost_per_share
        cash_withdrawal = Position(
            account_id=payload.account_id,
            symbol="CASH",
            category=CategoryEnum.Cash,
            quantity=-total_cost,
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

    net_cash = payload.quantity * payload.price - payload.fee

    # Create cash deposit for net proceeds
    cash_deposit = Position(
        account_id=position.account_id,
        symbol="CASH",
        category=CategoryEnum.Cash,
        quantity=net_cash,
        cost_per_share=1.0,
        currency=account.base_currency,
        date_added=payload.date,
    )
    db.add(cash_deposit)

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
        net_cash=net_cash,
        currency=account.base_currency,
    )
