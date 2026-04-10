from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Position, Account, CategoryEnum
from app.schemas import PositionCreate, PositionUpdate, PositionOut

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
