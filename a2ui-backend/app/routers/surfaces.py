"""
Surface history endpoints.
GET  /surfaces       — list all saved surfaces (newest first)
GET  /surfaces/{id}  — get a specific surface snapshot
POST /surfaces       — save or update a surface
DELETE /surfaces/{id} — delete a surface
"""
from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db, SurfaceHistory
from app.schemas import SurfaceRecord, SaveSurfaceRequest

router = APIRouter()


@router.get("/surfaces", response_model=list[SurfaceRecord])
def list_surfaces(db: Session = Depends(get_db)):
    rows = (
        db.query(SurfaceHistory)
        .order_by(SurfaceHistory.created_at.desc())
        .all()
    )
    return [
        SurfaceRecord(
            id=r.id,
            title=r.title,
            snapshot=r.snapshot,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]


@router.get("/surfaces/{surface_id}", response_model=SurfaceRecord)
def get_surface(surface_id: str, db: Session = Depends(get_db)):
    row = db.query(SurfaceHistory).filter(SurfaceHistory.id == surface_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Surface not found")
    return SurfaceRecord(
        id=row.id,
        title=row.title,
        snapshot=row.snapshot,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


@router.post("/surfaces", response_model=SurfaceRecord)
def save_surface(request: SaveSurfaceRequest, db: Session = Depends(get_db)):
    from datetime import datetime
    existing = db.query(SurfaceHistory).filter(SurfaceHistory.id == request.id).first()
    if existing:
        existing.title = request.title
        existing.snapshot = request.snapshot
        db.commit()
        db.refresh(existing)
        row = existing
    else:
        row = SurfaceHistory(
            id=request.id,
            title=request.title,
            snapshot=request.snapshot,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return SurfaceRecord(
        id=row.id,
        title=row.title,
        snapshot=row.snapshot,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


@router.delete("/surfaces/{surface_id}")
def delete_surface(surface_id: str, db: Session = Depends(get_db)):
    row = db.query(SurfaceHistory).filter(SurfaceHistory.id == surface_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Surface not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
