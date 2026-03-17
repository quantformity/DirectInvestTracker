"""
A2UI Backend — FastAPI application on port 10201.

This is a separate app from the existing investment tracker backend (port 8000).
It bridges the LLM ↔ A2UI frontend via the A2UI protocol.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import chat, action, surfaces

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="QFI A2UI Backend",
    version="1.0.0",
    description="A2UI protocol bridge for the QFI investment portfolio assistant",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, tags=["chat"])
app.include_router(action.router, tags=["action"])
app.include_router(surfaces.router, tags=["surfaces"])


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("A2UI backend started — surface_history table ready")


@app.get("/health")
def health():
    return {"status": "ok", "service": "qfi-a2ui-backend"}
