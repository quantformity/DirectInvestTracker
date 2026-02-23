import requests
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Setting
from app.schemas import OllamaSettingsOut, OllamaSettingsUpdate
from app.services import ollama

router = APIRouter()


@router.get("/", response_model=OllamaSettingsOut)
def get_settings(db: Session = Depends(get_db)):
    """Return current Ollama configuration (DB values override env defaults)."""
    rows = {r.key: r.value for r in db.query(Setting).all()}
    return OllamaSettingsOut(
        ollama_base_url=rows.get("ollama_base_url", ollama._config["base_url"]),
        ollama_model=rows.get("ollama_model", ollama._config["model"]),
        ollama_code_model=rows.get("ollama_code_model", ollama._config["code_model"]),
    )


@router.put("/", response_model=OllamaSettingsOut)
def update_settings(payload: OllamaSettingsUpdate, db: Session = Depends(get_db)):
    """Persist Ollama configuration and apply it immediately (no restart needed)."""
    data = payload.model_dump()
    for key, value in data.items():
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(Setting(key=key, value=value))
    db.commit()

    # Apply immediately to live config
    ollama.update_config(
        base_url=data["ollama_base_url"],
        model=data["ollama_model"],
        code_model=data["ollama_code_model"],
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
