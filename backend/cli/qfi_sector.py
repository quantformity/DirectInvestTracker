"""QFI Sector mapping CLI."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import typer
from typing import Optional
from sqlalchemy import func

from cli.lib.db import get_session
from cli.lib.output import print_output, error_exit, success_output

app = typer.Typer(help="Manage sector mappings.")


@app.command("list")
def list_sectors(
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """List all sector mappings."""
    db = get_session()
    try:
        from app.models import SectorMapping
        rows = db.query(SectorMapping).order_by(SectorMapping.symbol).all()
        data = [{"symbol": r.symbol, "sector": r.sector} for r in rows]
        print_output(data, json_output)
    finally:
        db.close()


@app.command("add")
def add_sector(
    symbol: str = typer.Argument(..., help="Ticker symbol"),
    sector: str = typer.Argument(..., help="Sector name"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Add or update a sector mapping."""
    db = get_session()
    try:
        from app.models import SectorMapping
        existing = db.query(SectorMapping).filter(SectorMapping.symbol == symbol.upper()).first()
        if existing:
            existing.sector = sector
        else:
            mapping = SectorMapping(symbol=symbol.upper(), sector=sector)
            db.add(mapping)
        db.commit()
        data = {"symbol": symbol.upper(), "sector": sector}
        print_output(data, json_output)
    finally:
        db.close()


@app.command("update")
def update_sector(
    symbol: str = typer.Argument(..., help="Ticker symbol"),
    sector: str = typer.Argument(..., help="New sector name"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Update sector mapping (upsert)."""
    db = get_session()
    try:
        from app.models import SectorMapping
        existing = db.query(SectorMapping).filter(SectorMapping.symbol == symbol.upper()).first()
        if existing:
            existing.sector = sector
        else:
            mapping = SectorMapping(symbol=symbol.upper(), sector=sector)
            db.add(mapping)
        db.commit()
        data = {"symbol": symbol.upper(), "sector": sector}
        print_output(data, json_output)
    finally:
        db.close()


@app.command("delete")
def delete_sector(
    symbol: str = typer.Argument(..., help="Ticker symbol"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Delete a sector mapping."""
    db = get_session()
    try:
        from app.models import SectorMapping
        mapping = db.query(SectorMapping).filter(SectorMapping.symbol == symbol.upper()).first()
        if not mapping:
            error_exit(f"No sector mapping found for symbol '{symbol}'")
        db.delete(mapping)
        db.commit()
        success_output(f"Sector mapping for {symbol.upper()} deleted", json_output)
    finally:
        db.close()


@app.command("show")
def show_sector(
    sector: str = typer.Argument(..., help="Sector name"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """List all symbols mapped to a sector."""
    db = get_session()
    try:
        from app.models import SectorMapping
        rows = db.query(SectorMapping).filter(SectorMapping.sector == sector).all()
        data = [{"symbol": r.symbol, "sector": r.sector} for r in rows]
        print_output(data, json_output)
    finally:
        db.close()


@app.command("summary")
def sector_summary(
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show count and total MTM per sector."""
    db = get_session()
    try:
        from app.models import SectorMapping, Position, CategoryEnum
        from app.routers.summary import _get_latest_prices, _get_latest_fx_rates, _enrich_positions

        reporting_currency = os.getenv("REPORTING_CURRENCY", "CAD")
        mappings = {m.symbol: m.sector for m in db.query(SectorMapping).all()}
        positions = db.query(Position).all()
        prices = _get_latest_prices(db)
        fx_rates = _get_latest_fx_rates(db)
        enriched = _enrich_positions(positions, prices, fx_rates, reporting_currency)

        sector_data = {}
        for e in enriched:
            s = mappings.get(e.symbol, "Unspecified")
            if s not in sector_data:
                sector_data[s] = {"sector": s, "symbol_count": 0, "total_mtm": 0.0}
            sector_data[s]["symbol_count"] += 1
            sector_data[s]["total_mtm"] += e.mtm_reporting

        data = []
        for s, v in sorted(sector_data.items()):
            data.append({
                "sector": v["sector"],
                "symbol_count": v["symbol_count"],
                "total_mtm": round(v["total_mtm"], 2),
            })

        print_output(data, json_output)
    finally:
        db.close()


if __name__ == "__main__":
    app()
