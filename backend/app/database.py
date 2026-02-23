import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/investments.db")

# Ensure the database directory exists.
# Derive it from DATABASE_URL so it works both in Docker (relative "data/")
# and in the packaged desktop app (absolute path set by Electron).
if DATABASE_URL.startswith("sqlite:///"):
    _db_path = DATABASE_URL[len("sqlite:///"):]
    _db_dir = os.path.dirname(_db_path)
    if _db_dir:
        os.makedirs(_db_dir, exist_ok=True)

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
    """Restore persisted AI provider config from the settings table into the live config dict."""
    from app.services import ollama
    from app.models import Setting
    try:
        with SessionLocal() as db:
            rows = {r.key: r.value for r in db.query(Setting).all()}
            ollama.update_config(
                provider=rows.get("ai_provider"),
                base_url=rows.get("ollama_base_url"),
                model=rows.get("ollama_model"),
                code_model=rows.get("ollama_code_model"),
                lmstudio_base_url=rows.get("lmstudio_base_url"),
                lmstudio_model=rows.get("lmstudio_model"),
                lmstudio_code_model=rows.get("lmstudio_code_model"),
                gemini_api_key=rows.get("gemini_api_key"),
                gemini_model=rows.get("gemini_model"),
                gemini_code_model=rows.get("gemini_code_model"),
                claude_api_key=rows.get("claude_api_key"),
                claude_model=rows.get("claude_model"),
                claude_code_model=rows.get("claude_code_model"),
            )
    except Exception:
        pass  # Table may not exist on very first boot; fine to skip


def init_db():
    # Import models so they register with Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate()
    _load_settings()
