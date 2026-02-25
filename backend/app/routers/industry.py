from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import IndustryMapping, Position
from app.schemas import IndustryMappingOut, IndustryMappingUpdate

router = APIRouter()


@router.get("/", response_model=list[IndustryMappingOut])
def get_industry_mappings(db: Session = Depends(get_db)):
    """Return all symbols from positions with their industry (defaults to Unspecified)."""
    symbols = sorted({p.symbol for p in db.query(Position).all() if p.symbol})
    existing = {m.symbol: m.industry for m in db.query(IndustryMapping).all()}
    return [
        IndustryMappingOut(symbol=sym, industry=existing.get(sym, "Unspecified"))
        for sym in symbols
    ]


@router.put("/{symbol}", response_model=IndustryMappingOut)
def upsert_industry_mapping(
    symbol: str,
    body: IndustryMappingUpdate,
    db: Session = Depends(get_db),
):
    """Create or update the industry for a symbol."""
    mapping = db.query(IndustryMapping).filter(IndustryMapping.symbol == symbol).first()
    if mapping:
        mapping.industry = body.industry
    else:
        mapping = IndustryMapping(symbol=symbol, industry=body.industry)
        db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@router.delete("/{symbol}")
def delete_industry_mapping(symbol: str, db: Session = Depends(get_db)):
    """Delete the industry mapping for a symbol (resets to Unspecified)."""
    mapping = db.query(IndustryMapping).filter(IndustryMapping.symbol == symbol).first()
    if mapping:
        db.delete(mapping)
        db.commit()
    return {"ok": True}
