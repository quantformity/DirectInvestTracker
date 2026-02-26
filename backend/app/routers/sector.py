from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SectorMapping, Position
from app.schemas import SectorMappingOut, SectorMappingUpdate

router = APIRouter()


@router.get("/", response_model=list[SectorMappingOut])
def get_sector_mappings(db: Session = Depends(get_db)):
    """Return all symbols from positions with their sector (defaults to Unspecified)."""
    symbols = sorted({p.symbol for p in db.query(Position).all() if p.symbol})
    existing = {m.symbol: m.sector for m in db.query(SectorMapping).all()}
    return [
        SectorMappingOut(symbol=sym, sector=existing.get(sym, "Unspecified"))
        for sym in symbols
    ]


@router.put("/{symbol}", response_model=SectorMappingOut)
def upsert_sector_mapping(
    symbol: str,
    body: SectorMappingUpdate,
    db: Session = Depends(get_db),
):
    """Create or update the sector for a symbol."""
    mapping = db.query(SectorMapping).filter(SectorMapping.symbol == symbol).first()
    if mapping:
        mapping.sector = body.sector
    else:
        mapping = SectorMapping(symbol=symbol, sector=body.sector)
        db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@router.delete("/{symbol}")
def delete_sector_mapping(symbol: str, db: Session = Depends(get_db)):
    """Delete the sector mapping for a symbol (resets to Unspecified)."""
    mapping = db.query(SectorMapping).filter(SectorMapping.symbol == symbol).first()
    if mapping:
        db.delete(mapping)
        db.commit()
    return {"ok": True}
