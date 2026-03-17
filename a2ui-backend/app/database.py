"""
Database for the A2UI backend — stores surface history.
Uses a separate SQLite file alongside the main investments database.
"""
import os
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from datetime import datetime, timezone

_DEFAULT_DB = str(
    Path(__file__).parent.parent.parent / "backend" / "data" / "investments.db"
)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB}")
if DATABASE_URL.startswith("sqlite:///"):
    _db_path = DATABASE_URL[len("sqlite:///"):]
    _db_dir = os.path.dirname(_db_path)
    if _db_dir:
        os.makedirs(_db_dir, exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class SurfaceHistory(Base):
    __tablename__ = "surface_history"

    id = Column(String(36), primary_key=True)
    title = Column(String(200), nullable=False)
    snapshot = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
