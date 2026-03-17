"""QFI Summary CLI."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import typer
from typing import Optional

from cli.lib.db import get_session
from cli.lib.output import print_output, error_exit

app = typer.Typer(help="Portfolio summary views.")

REPORTING_CURRENCY = os.getenv("REPORTING_CURRENCY", "CAD")


def _build_summary(db, group_by="category", account_id=None, sector=None):
    from app.models import Position, SectorMapping, CategoryEnum
    from app.routers.summary import _get_latest_prices, _get_latest_fx_rates, _enrich_positions

    reporting_currency = os.getenv("REPORTING_CURRENCY", REPORTING_CURRENCY)

    q = db.query(Position)
    if account_id is not None:
        q = q.filter(Position.account_id == account_id)
    positions = q.all()

    prices = _get_latest_prices(db)
    fx_rates = _get_latest_fx_rates(db)
    enriched = _enrich_positions(positions, prices, fx_rates, reporting_currency)

    total_mtm = sum(e.mtm_reporting for e in enriched) or 1.0
    total_pnl = sum(e.pnl_reporting for e in enriched)

    for e in enriched:
        e.proportion = (e.mtm_reporting / total_mtm) * 100.0 if total_mtm else 0.0

    sector_map = {}
    if group_by == "sector":
        sector_map = {m.symbol: m.sector for m in db.query(SectorMapping).all()}

    group_map = {}
    for e in enriched:
        if group_by == "category":
            key = e.category.value if hasattr(e.category, "value") else str(e.category)
        elif group_by == "account":
            key = e.account_name
        elif group_by == "symbol":
            key = e.symbol
        elif group_by == "sector":
            key = sector_map.get(e.symbol, "Unspecified")
            if sector and key != sector:
                continue
        else:  # cash_gic
            key = "GIC/Cash" if e.category in (CategoryEnum.GIC, CategoryEnum.Cash) else "Other"

        if key not in group_map:
            group_map[key] = {"mtm": 0.0, "pnl": 0.0}
        group_map[key]["mtm"] += e.mtm_reporting
        group_map[key]["pnl"] += e.pnl_reporting

    groups = [
        {
            "group_key": k,
            "total_mtm_reporting": round(v["mtm"], 2),
            "total_pnl_reporting": round(v["pnl"], 2),
            "proportion": round((v["mtm"] / total_mtm * 100.0) if total_mtm else 0.0, 2),
        }
        for k, v in group_map.items()
    ]

    return {
        "groups": groups,
        "total_mtm_reporting": round(total_mtm, 2),
        "total_pnl_reporting": round(total_pnl, 2),
        "reporting_currency": reporting_currency,
    }


@app.command("show")
def show_summary(
    group_by: str = typer.Option("category", "--group-by", help="Group by: category|account|symbol|sector|cash_gic"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show portfolio summary."""
    db = get_session()
    try:
        valid = {"category", "account", "symbol", "sector", "cash_gic"}
        if group_by not in valid:
            error_exit(f"Invalid group-by: {group_by}. Use: {', '.join(sorted(valid))}")
        result = _build_summary(db, group_by=group_by)
        print_output(result, json_output)
    finally:
        db.close()


@app.command("account")
def account_summary(
    account_id: int = typer.Argument(..., help="Account ID"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show MTM breakdown for one account."""
    db = get_session()
    try:
        from app.models import Account
        acct = db.query(Account).filter(Account.id == account_id).first()
        if not acct:
            error_exit(f"Account {account_id} not found")
        result = _build_summary(db, group_by="symbol", account_id=account_id)
        result["account_id"] = account_id
        result["account_name"] = acct.name
        print_output(result, json_output)
    finally:
        db.close()


@app.command("sector")
def sector_summary(
    sector_name: Optional[str] = typer.Argument(None, help="Optional sector name to filter"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show holdings grouped by sector."""
    db = get_session()
    try:
        result = _build_summary(db, group_by="sector", sector=sector_name)
        print_output(result, json_output)
    finally:
        db.close()


@app.command("category")
def category_summary(
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show holdings split by category."""
    db = get_session()
    try:
        result = _build_summary(db, group_by="category")
        print_output(result, json_output)
    finally:
        db.close()


if __name__ == "__main__":
    app()
