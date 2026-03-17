"""QFI FX rate management CLI."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import typer
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import func

from cli.lib.db import get_session
from cli.lib.output import print_output, error_exit, success_output
from cli.lib.yahoo import fetch_fx_rates_batch

app = typer.Typer(help="Manage FX rates.")


def _fx_to_dict(fx):
    return {
        "pair": fx.pair,
        "rate": fx.rate,
        "timestamp": str(fx.timestamp),
    }


@app.command("list")
def list_fx(
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show latest FX rate per pair."""
    db = get_session()
    try:
        from app.models import FxRate
        subq = (
            db.query(FxRate.pair, func.max(FxRate.timestamp).label("max_ts"))
            .group_by(FxRate.pair)
            .subquery()
        )
        rows = (
            db.query(FxRate)
            .join(subq, (FxRate.pair == subq.c.pair) & (FxRate.timestamp == subq.c.max_ts))
            .all()
        )
        data = [_fx_to_dict(r) for r in rows]
        print_output(data, json_output)
    finally:
        db.close()


@app.command("show")
def show_fx(
    pair: str = typer.Argument(..., help="FX pair, e.g. USD/CAD"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show latest FX rate for a pair."""
    db = get_session()
    try:
        from app.models import FxRate
        latest_ts = (
            db.query(func.max(FxRate.timestamp))
            .filter(FxRate.pair == pair)
            .scalar()
        )
        if latest_ts is None:
            error_exit(f"No FX rate found for pair '{pair}'")
        fx = (
            db.query(FxRate)
            .filter(FxRate.pair == pair, FxRate.timestamp == latest_ts)
            .first()
        )
        if not fx:
            error_exit(f"No FX rate found for pair '{pair}'")
        print_output(_fx_to_dict(fx), json_output)
    finally:
        db.close()


@app.command("refresh")
def refresh_fx(
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Fetch all needed FX pairs from Yahoo Finance."""
    db = get_session()
    try:
        from app.models import Position, Account, FxRate

        # Determine which FX pairs are needed
        reporting_currency = os.getenv("REPORTING_CURRENCY", "CAD").upper()
        accounts = db.query(Account).all()
        positions = db.query(Position).all()

        pairs = set()
        for pos in positions:
            pos_ccy = pos.currency.upper()
            acct = next((a for a in accounts if a.id == pos.account_id), None)
            acct_ccy = acct.base_currency.upper() if acct else reporting_currency
            if pos_ccy != acct_ccy:
                pairs.add(f"{pos_ccy}/{acct_ccy}")
            if acct_ccy != reporting_currency:
                pairs.add(f"{acct_ccy}/{reporting_currency}")

        if not pairs:
            print_output({"message": "No FX pairs needed", "updated": []}, json_output)
            return

        rates = fetch_fx_rates_batch(list(pairs))

        now = datetime.now(timezone.utc)
        updated = []
        for pair, rate in rates.items():
            fx = FxRate(pair=pair, rate=rate, timestamp=now)
            db.add(fx)
            updated.append(pair)
        db.commit()

        print_output({"updated": updated, "count": len(updated)}, json_output)
    finally:
        db.close()


@app.command("add")
def add_fx(
    pair: str = typer.Argument(..., help="FX pair, e.g. USD/CAD"),
    rate: float = typer.Argument(..., help="Exchange rate"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Insert an FX rate row."""
    db = get_session()
    try:
        from app.models import FxRate
        now = datetime.now(timezone.utc)
        fx = FxRate(pair=pair, rate=rate, timestamp=now)
        db.add(fx)
        db.commit()
        db.refresh(fx)
        print_output(_fx_to_dict(fx), json_output)
    finally:
        db.close()


@app.command("modify")
def modify_fx(
    pair: str = typer.Argument(..., help="FX pair, e.g. USD/CAD"),
    rate: float = typer.Argument(..., help="New exchange rate"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Insert a new FX rate row with updated rate (append-only)."""
    db = get_session()
    try:
        from app.models import FxRate
        now = datetime.now(timezone.utc)
        fx = FxRate(pair=pair, rate=rate, timestamp=now)
        db.add(fx)
        db.commit()
        db.refresh(fx)
        print_output(_fx_to_dict(fx), json_output)
    finally:
        db.close()


if __name__ == "__main__":
    app()
