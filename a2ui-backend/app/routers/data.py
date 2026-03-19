"""
GET /data/prices — returns live-hydrated data for paths that change over time.

Used by the frontend background quote updater to refresh chart data every 3 minutes
without re-invoking the LLM.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.hydrator import hydrate_all

router = APIRouter(prefix="/data", tags=["data"])

# Paths whose data changes over time and should be refreshed periodically
_LIVE_PATHS = [
    "market/quotes",
    "positions/rows",
    "portfolio/kpi",
]


@router.get("/prices")
def get_live_prices():
    """
    Hydrate all live data paths and return as a dict of path → data.
    The frontend polls this endpoint every 3 minutes and patches the
    dataModel of every active surface that references these paths.
    """
    data = hydrate_all(_LIVE_PATHS)
    return JSONResponse(data)
