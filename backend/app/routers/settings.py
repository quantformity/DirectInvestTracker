import requests
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Setting
from app.schemas import OllamaSettingsOut, OllamaSettingsUpdate
from app.services import ollama

router = APIRouter()

_SETTING_KEYS = [
    "ai_provider",
    "ollama_base_url", "ollama_model", "ollama_code_model",
    "lmstudio_base_url", "lmstudio_model", "lmstudio_code_model",
    "gemini_api_key", "gemini_model", "gemini_code_model",
    "claude_api_key", "claude_model", "claude_code_model",
    "llamacpp_base_url", "llamacpp_model", "llamacpp_code_model",
]


@router.get("/", response_model=OllamaSettingsOut)
def get_settings(db: Session = Depends(get_db)):
    """Return current AI provider configuration."""
    rows = {r.key: r.value for r in db.query(Setting).all()}
    return OllamaSettingsOut(
        ai_provider=rows.get("ai_provider", ollama._config["provider"]),
        # Ollama
        ollama_base_url=rows.get("ollama_base_url", ollama._config["base_url"]),
        ollama_model=rows.get("ollama_model", ollama._config["model"]),
        ollama_code_model=rows.get("ollama_code_model", ollama._config["code_model"]),
        # LM Studio
        lmstudio_base_url=rows.get("lmstudio_base_url", ollama._config["lmstudio_base_url"]),
        lmstudio_model=rows.get("lmstudio_model", ollama._config["lmstudio_model"]),
        lmstudio_code_model=rows.get("lmstudio_code_model", ollama._config["lmstudio_code_model"]),
        # Gemini
        gemini_api_key=rows.get("gemini_api_key", ollama._config["gemini_api_key"]),
        gemini_model=rows.get("gemini_model", ollama._config["gemini_model"]),
        gemini_code_model=rows.get("gemini_code_model", ollama._config["gemini_code_model"]),
        # Claude
        claude_api_key=rows.get("claude_api_key", ollama._config["claude_api_key"]),
        claude_model=rows.get("claude_model", ollama._config["claude_model"]),
        claude_code_model=rows.get("claude_code_model", ollama._config["claude_code_model"]),
        # llama.cpp
        llamacpp_base_url=rows.get("llamacpp_base_url", ollama._config["llamacpp_base_url"]),
        llamacpp_model=rows.get("llamacpp_model", ollama._config["llamacpp_model"]),
        llamacpp_code_model=rows.get("llamacpp_code_model", ollama._config["llamacpp_code_model"]),
    )


@router.put("/", response_model=OllamaSettingsOut)
def update_settings(payload: OllamaSettingsUpdate, db: Session = Depends(get_db)):
    """Persist AI provider configuration and apply immediately (no restart needed)."""
    data = payload.model_dump()
    for key, value in data.items():
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(Setting(key=key, value=value))
    db.commit()

    # Apply immediately
    ollama.update_config(
        provider=data["ai_provider"],
        base_url=data["ollama_base_url"],
        model=data["ollama_model"],
        code_model=data["ollama_code_model"],
        lmstudio_base_url=data["lmstudio_base_url"],
        lmstudio_model=data["lmstudio_model"],
        lmstudio_code_model=data["lmstudio_code_model"],
        gemini_api_key=data["gemini_api_key"],
        gemini_model=data["gemini_model"],
        gemini_code_model=data["gemini_code_model"],
        claude_api_key=data["claude_api_key"],
        claude_model=data["claude_model"],
        claude_code_model=data["claude_code_model"],
        llamacpp_base_url=data["llamacpp_base_url"],
        llamacpp_model=data["llamacpp_model"],
        llamacpp_code_model=data["llamacpp_code_model"],
    )
    return OllamaSettingsOut(**data)


@router.get("/ollama-models")
def list_ollama_models():
    """Probe the configured Ollama server and return its available model names."""
    try:
        resp = requests.get(f"{ollama._config['base_url']}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return {"models": models, "error": None}
    except Exception as exc:
        return {"models": [], "error": str(exc)}


@router.get("/lmstudio-models")
def list_lmstudio_models():
    """Probe the configured LM Studio server and return loaded model IDs."""
    try:
        resp = requests.get(f"{ollama._config['lmstudio_base_url'].rstrip('/')}/models", timeout=5)
        resp.raise_for_status()
        models = [m["id"] for m in resp.json().get("data", [])]
        return {"models": models, "error": None}
    except Exception as exc:
        return {"models": [], "error": str(exc)}


@router.get("/llamacpp-models")
def list_llamacpp_models():
    """Probe the configured llama.cpp server and return loaded model IDs."""
    try:
        resp = requests.get(f"{ollama._config['llamacpp_base_url'].rstrip('/')}/models", timeout=5)
        resp.raise_for_status()
        models = [m["id"] for m in resp.json().get("data", [])]
        return {"models": models, "error": None}
    except Exception as exc:
        return {"models": [], "error": str(exc)}
