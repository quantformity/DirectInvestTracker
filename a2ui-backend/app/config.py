"""
Configuration — reads AI provider settings from the shared investments SQLite database.
Falls back to environment variables if the DB has no settings yet.
"""
import os
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to the shared investments database
_DB_PATH = os.getenv(
    "DATABASE_URL",
    str(Path(__file__).parent.parent.parent / "backend" / "data" / "investments.db"),
)
if _DB_PATH.startswith("sqlite:///"):
    _DB_PATH = _DB_PATH[len("sqlite:///"):]


def _load_settings() -> dict[str, str]:
    """Load all key-value pairs from the settings table."""
    settings: dict[str, str] = {}
    try:
        conn = sqlite3.connect(_DB_PATH)
        cursor = conn.execute("SELECT key, value FROM settings")
        for key, value in cursor.fetchall():
            settings[key] = value
        conn.close()
    except Exception as exc:
        logger.warning("Could not read settings from DB (%s): %s", _DB_PATH, exc)
    return settings


def get_llm_config() -> dict[str, str]:
    """Return LLM configuration, merging DB settings over env-var defaults."""
    db = _load_settings()

    return {
        "provider": db.get("ai_provider") or os.getenv("AI_PROVIDER", "ollama"),

        # Ollama
        "ollama_base_url":   db.get("ollama_base_url")   or os.getenv("OLLAMA_BASE_URL",    "http://192.168.0.117:11434"),
        "ollama_model":      db.get("ollama_model")      or os.getenv("OLLAMA_MODEL",        "glm-4.7-flash:latest"),
        "ollama_code_model": db.get("ollama_code_model") or os.getenv("OLLAMA_CODE_MODEL",   "glm-4.7-flash:latest"),

        # LM Studio
        "lmstudio_base_url":   db.get("lmstudio_base_url")   or os.getenv("LMSTUDIO_BASE_URL",   "http://localhost:1234/v1"),
        "lmstudio_model":      db.get("lmstudio_model")      or os.getenv("LMSTUDIO_MODEL",       ""),
        "lmstudio_code_model": db.get("lmstudio_code_model") or os.getenv("LMSTUDIO_CODE_MODEL",  ""),

        # Gemini
        "gemini_api_key":    db.get("gemini_api_key")    or os.getenv("GEMINI_API_KEY",  ""),
        "gemini_model":      db.get("gemini_model")      or os.getenv("GEMINI_MODEL",    "gemini-2.0-flash"),
        "gemini_code_model": db.get("gemini_code_model") or os.getenv("GEMINI_CODE_MODEL", "gemini-2.0-flash"),

        # Claude
        "claude_api_key":    db.get("claude_api_key")    or os.getenv("CLAUDE_API_KEY",  ""),
        "claude_model":      db.get("claude_model")      or os.getenv("CLAUDE_MODEL",    "claude-3-5-haiku-20241022"),
        "claude_code_model": db.get("claude_code_model") or os.getenv("CLAUDE_CODE_MODEL", "claude-3-5-haiku-20241022"),
    }
