import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.services.scheduler import start_scheduler, shutdown_scheduler
from app.routers import accounts, positions, market_data, fx_rates, summary, history, ai, settings, sector


def _read_version() -> str:
    """Read version from the repo-root VERSION file.

    Works both in development (walk up from app/) and when packaged with
    PyInstaller (VERSION is bundled next to the binary via backend.spec).
    """
    # PyInstaller sets sys._MEIPASS when running from a bundle
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        candidate = os.path.join(base, "VERSION")
        if os.path.isfile(candidate):
            return open(candidate).read().strip()

    # Development: walk up from this file's directory to find VERSION
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        candidate = os.path.join(here, "VERSION")
        if os.path.isfile(candidate):
            return open(candidate).read().strip()
        here = os.path.dirname(here)

    return "0.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Qf Direct Invest Tracker API",
    description="Backend for the Qf Direct Invest Tracker portfolio tracker",
    version=_read_version(),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(accounts.router, prefix="/accounts", tags=["Accounts"])
app.include_router(positions.router, prefix="/positions", tags=["Positions"])
app.include_router(market_data.router, prefix="/market-data", tags=["Market Data"])
app.include_router(fx_rates.router, prefix="/fx-rates", tags=["FX Rates"])
app.include_router(summary.router, prefix="/summary", tags=["Summary"])
app.include_router(history.router, prefix="/history", tags=["History"])
app.include_router(ai.router, prefix="/ai", tags=["AI"])
app.include_router(settings.router, prefix="/settings", tags=["Settings"])
app.include_router(sector.router, prefix="/sector", tags=["Sector"])


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Qf Direct Invest Tracker API running"}
