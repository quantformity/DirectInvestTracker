"""
Settings router for the A2UI backend.
Reads/writes the shared investments.db settings table directly — no dependency
on the existing backend being up.
"""
import os
import sqlite3
import requests
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/settings", tags=["settings"])

_DB_PATH = os.getenv(
    "DATABASE_URL",
    str(Path(__file__).parent.parent.parent.parent / "backend" / "data" / "investments.db"),
)
if _DB_PATH.startswith("sqlite:///"):
    _DB_PATH = _DB_PATH[len("sqlite:///"):]

_DEFAULTS = {
    "ai_provider":          "ollama",
    "ollama_base_url":      "http://192.168.0.117:11434",
    "ollama_model":         "glm-4.7-flash:latest",
    "ollama_code_model":    "glm-4.7-flash:latest",
    "lmstudio_base_url":    "http://localhost:1234/v1",
    "lmstudio_model":       "",
    "lmstudio_code_model":  "",
    "gemini_api_key":       "",
    "gemini_model":         "gemini-2.0-flash",
    "gemini_code_model":    "gemini-2.0-flash",
    "claude_api_key":       "",
    "claude_model":         "claude-3-5-haiku-20241022",
    "claude_code_model":    "claude-3-5-haiku-20241022",
    "llamacpp_base_url":    "http://localhost:8080/v1",
    "llamacpp_model":       "",
    "llamacpp_code_model":  "",
    "history_cache_path":   "",
}

_SETTING_KEYS = list(_DEFAULTS.keys())


def _read_settings() -> dict[str, str]:
    rows = dict(_DEFAULTS)
    try:
        conn = sqlite3.connect(_DB_PATH)
        for key, value in conn.execute("SELECT key, value FROM settings").fetchall():
            rows[key] = value
        conn.close()
    except Exception:
        pass
    return rows


def _write_settings(data: dict[str, str]) -> None:
    conn = sqlite3.connect(_DB_PATH)
    for key, value in data.items():
        existing = conn.execute(
            "SELECT key FROM settings WHERE key = ?", (key,)
        ).fetchone()
        if existing:
            conn.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
        else:
            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


# ── Schemas ────────────────────────────────────────────────────────────────────

class AISettings(BaseModel):
    ai_provider: str = "ollama"
    ollama_base_url: str = ""
    ollama_model: str = ""
    ollama_code_model: str = ""
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_model: str = ""
    lmstudio_code_model: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_code_model: str = "gemini-2.0-flash"
    claude_api_key: str = ""
    claude_model: str = "claude-3-5-haiku-20241022"
    claude_code_model: str = "claude-3-5-haiku-20241022"
    llamacpp_base_url: str = "http://localhost:8080/v1"
    llamacpp_model: str = ""
    llamacpp_code_model: str = ""
    history_cache_path: str = ""
    db_path: str = ""


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/", response_model=AISettings)
def get_settings():
    rows = _read_settings()
    return AISettings(
        **{k: rows.get(k, _DEFAULTS.get(k, "")) for k in AISettings.model_fields},
        db_path=os.path.abspath(_DB_PATH),
    )


@router.put("/", response_model=AISettings)
def update_settings(payload: AISettings):
    data = {k: v for k, v in payload.model_dump().items() if k in _SETTING_KEYS}
    _write_settings(data)
    rows = _read_settings()
    return AISettings(
        **{k: rows.get(k, _DEFAULTS.get(k, "")) for k in AISettings.model_fields},
        db_path=os.path.abspath(_DB_PATH),
    )


@router.get("/ollama-models")
def list_ollama_models():
    rows = _read_settings()
    base_url = rows.get("ollama_base_url", _DEFAULTS["ollama_base_url"])
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return {"models": models, "error": None}
    except Exception as exc:
        return {"models": [], "error": str(exc)}


@router.get("/lmstudio-models")
def list_lmstudio_models():
    rows = _read_settings()
    base_url = rows.get("lmstudio_base_url", _DEFAULTS["lmstudio_base_url"])
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/models", timeout=5)
        resp.raise_for_status()
        models = [m["id"] for m in resp.json().get("data", [])]
        return {"models": models, "error": None}
    except Exception as exc:
        return {"models": [], "error": str(exc)}


@router.get("/llamacpp-models")
def list_llamacpp_models():
    rows = _read_settings()
    base_url = rows.get("llamacpp_base_url", _DEFAULTS["llamacpp_base_url"])
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/models", timeout=5)
        resp.raise_for_status()
        models = [m["id"] for m in resp.json().get("data", [])]
        return {"models": models, "error": None}
    except Exception as exc:
        return {"models": [], "error": str(exc)}
