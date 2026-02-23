import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/investments.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate():
    """Add new columns to existing tables without destroying data."""
    with engine.connect() as conn:
        existing = [row[1] for row in conn.execute(text("PRAGMA table_info(positions)")).fetchall()]
        if "currency" not in existing:
            conn.execute(text("ALTER TABLE positions ADD COLUMN currency VARCHAR(10) NOT NULL DEFAULT 'USD'"))
            conn.commit()


def _load_settings():
    """Restore persisted Ollama config from the settings table into the live config dict."""
    from app.services import ollama
    from app.models import Setting
    try:
        with SessionLocal() as db:
            rows = {r.key: r.value for r in db.query(Setting).all()}
            ollama.update_config(
                base_url=rows.get("ollama_base_url"),
                model=rows.get("ollama_model"),
                code_model=rows.get("ollama_code_model"),
            )
    except Exception:
        pass  # Table may not exist on very first boot; fine to skip


def init_db():
    # Import models so they register with Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate()
    _load_settings()
