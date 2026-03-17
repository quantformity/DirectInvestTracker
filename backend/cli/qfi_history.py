"""QFI History CLI."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import typer
from typing import Optional
from datetime import datetime

from cli.lib.db import get_session
from cli.lib.output import print_output, error_exit

app = typer.Typer(help="View portfolio history (reads from DB cache).")


def _parse_date(date_str: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        error_exit(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def _filter_points(points, from_date=None, to_date=None):
    result = []
    for p in points:
        d = p.date if hasattr(p, "date") else p.get("date")
        if from_date and d < from_date:
            continue
        if to_date and d > to_date:
            continue
        result.append(p)
    return result


@app.command("portfolio")
def portfolio_history(
    account_id: Optional[int] = typer.Option(None, "--account-id", help="Filter by account ID"),
    from_date: Optional[str] = typer.Option(None, "--from", help="Start date YYYY-MM-DD"),
    to_date: Optional[str] = typer.Option(None, "--to", help="End date YYYY-MM-DD"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show aggregate portfolio history from DB cache."""
    db = get_session()
    try:
        from app.models import Position, Account, CategoryEnum, FxRate
        from app.routers.history import _compute_equity_aggregate, _get_fx_rates
        from sqlalchemy import func

        reporting_currency = os.getenv("REPORTING_CURRENCY", "CAD").upper()

        q = db.query(Position).filter(Position.category == CategoryEnum.Equity)
        if account_id is not None:
            q = q.filter(Position.account_id == account_id)
        positions = q.all()

        if not positions:
            print_output([], json_output)
            return

        accounts = {a.id: a for a in db.query(Account).all()}
        latest_fx = _get_fx_rates(db)

        combined, all_dates = _compute_equity_aggregate(
            positions, accounts, latest_fx, reporting_currency, use_cache=True
        )

        if not combined:
            print_output([], json_output)
            return

        # Add cash/GIC contributions
        from app.routers.history import _lookup_fx as _h_lookup_fx
        non_eq_q = db.query(Position).filter(
            Position.category.in_([CategoryEnum.Cash, CategoryEnum.GIC])
        )
        if account_id is not None:
            non_eq_q = non_eq_q.filter(Position.account_id == account_id)

        for pos in non_eq_q.all():
            acct = accounts.get(pos.account_id)
            acct_ccy = acct.base_currency.upper() if acct else reporting_currency
            pos_ccy = pos.currency.upper()
            cat = pos.category.value if hasattr(pos.category, "value") else str(pos.category)

            for dt in all_dates:
                if dt < pos.date_added:
                    continue
                if cat == "Cash":
                    mtm_pos = pos.quantity * pos.cost_per_share
                    pnl_pos = 0.0
                else:  # GIC
                    days = (dt - pos.date_added).days
                    spot = pos.cost_per_share * (1 + (pos.yield_rate or 0.0) * days / 365)
                    mtm_pos = spot * pos.quantity
                    pnl_pos = (spot - pos.cost_per_share) * pos.quantity

                fx = _h_lookup_fx(latest_fx, pos_ccy, acct_ccy) * _h_lookup_fx(latest_fx, acct_ccy, reporting_currency)
                combined[dt]["mtm"] += mtm_pos * fx
                combined[dt]["pnl"] += pnl_pos * fx
                combined[dt].setdefault("cash_gic", 0.0)
                combined[dt]["cash_gic"] += mtm_pos * fx

        points = [
            {
                "date": str(dt),
                "mtm": round(v["mtm"], 2),
                "pnl": round(v["pnl"], 2),
                "cash_gic": round(v.get("cash_gic", 0.0), 2),
            }
            for dt, v in sorted(combined.items())
        ]

        # Filter by date range
        if from_date:
            fd = _parse_date(from_date)
            points = [p for p in points if p["date"] >= str(fd)]
        if to_date:
            td = _parse_date(to_date)
            points = [p for p in points if p["date"] <= str(td)]

        print_output(points, json_output)
    finally:
        db.close()


@app.command("symbol")
def symbol_history(
    symbol: str = typer.Argument(..., help="Ticker symbol"),
    from_date: Optional[str] = typer.Option(None, "--from", help="Start date YYYY-MM-DD"),
    to_date: Optional[str] = typer.Option(None, "--to", help="End date YYYY-MM-DD"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show symbol history from DB cache."""
    db = get_session()
    try:
        from app.models import Position, CategoryEnum
        from app.services import history_cache

        positions = (
            db.query(Position)
            .filter(Position.symbol == symbol.upper(), Position.category == CategoryEnum.Equity)
            .all()
        )

        if not positions:
            error_exit(f"No equity positions found for symbol '{symbol}'")

        earliest_date = min(p.date_added for p in positions)
        total_quantity = sum(p.quantity for p in positions)
        avg_cost = sum(p.quantity * p.cost_per_share for p in positions) / total_quantity

        df = history_cache.read_cache(symbol.upper(), earliest_date)

        if df.empty:
            print_output([], json_output)
            return

        points = []
        for dt, row in df.iterrows():
            close = float(row["Close"])
            points.append({
                "date": str(dt),
                "close_price": round(close, 4),
                "pnl": round((close - avg_cost) * total_quantity, 2),
                "mtm": round(close * total_quantity, 2),
            })

        if from_date:
            fd = _parse_date(from_date)
            points = [p for p in points if p["date"] >= str(fd)]
        if to_date:
            td = _parse_date(to_date)
            points = [p for p in points if p["date"] <= str(td)]

        print_output(points, json_output)
    finally:
        db.close()


@app.command("sector")
def sector_history(
    sector: str = typer.Argument(..., help="Sector name"),
    from_date: Optional[str] = typer.Option(None, "--from", help="Start date YYYY-MM-DD"),
    to_date: Optional[str] = typer.Option(None, "--to", help="End date YYYY-MM-DD"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show sector portfolio history from DB cache."""
    db = get_session()
    try:
        from app.models import Position, Account, CategoryEnum, SectorMapping
        from app.routers.history import _compute_equity_aggregate, _get_fx_rates

        reporting_currency = os.getenv("REPORTING_CURRENCY", "CAD").upper()

        mappings = {m.symbol: m.sector for m in db.query(SectorMapping).all()}
        all_equity = db.query(Position).filter(Position.category == CategoryEnum.Equity).all()
        positions = [p for p in all_equity if mappings.get(p.symbol, "Unspecified") == sector]

        if not positions:
            print_output([], json_output)
            return

        accounts = {a.id: a for a in db.query(Account).all()}
        latest_fx = _get_fx_rates(db)

        combined, _ = _compute_equity_aggregate(
            positions, accounts, latest_fx, reporting_currency, use_cache=True
        )

        if not combined:
            print_output([], json_output)
            return

        points = [
            {
                "date": str(dt),
                "mtm": round(v["mtm"], 2),
                "pnl": round(v["pnl"], 2),
                "cash_gic": 0.0,
            }
            for dt, v in sorted(combined.items())
        ]

        if from_date:
            fd = _parse_date(from_date)
            points = [p for p in points if p["date"] >= str(fd)]
        if to_date:
            td = _parse_date(to_date)
            points = [p for p in points if p["date"] <= str(td)]

        print_output(points, json_output)
    finally:
        db.close()


@app.command("account")
def account_history(
    account_id: int = typer.Argument(..., help="Account ID"),
    from_date: Optional[str] = typer.Option(None, "--from", help="Start date YYYY-MM-DD"),
    to_date: Optional[str] = typer.Option(None, "--to", help="End date YYYY-MM-DD"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show account portfolio history from DB cache."""
    db = get_session()
    try:
        from app.models import Position, Account, CategoryEnum, FxRate
        from app.routers.history import _compute_equity_aggregate, _get_fx_rates, _lookup_fx as _h_lookup_fx

        reporting_currency = os.getenv("REPORTING_CURRENCY", "CAD").upper()

        positions = (
            db.query(Position)
            .filter(Position.account_id == account_id, Position.category == CategoryEnum.Equity)
            .all()
        )

        if not positions:
            print_output([], json_output)
            return

        accounts = {a.id: a for a in db.query(Account).all()}
        latest_fx = _get_fx_rates(db)

        combined, all_dates = _compute_equity_aggregate(
            positions, accounts, latest_fx, reporting_currency, use_cache=True
        )

        if not combined:
            print_output([], json_output)
            return

        # Add cash/GIC for this account
        non_eq = (
            db.query(Position)
            .filter(
                Position.account_id == account_id,
                Position.category.in_([CategoryEnum.Cash, CategoryEnum.GIC])
            )
            .all()
        )

        for pos in non_eq:
            acct = accounts.get(pos.account_id)
            acct_ccy = acct.base_currency.upper() if acct else reporting_currency
            pos_ccy = pos.currency.upper()
            cat = pos.category.value if hasattr(pos.category, "value") else str(pos.category)

            for dt in all_dates:
                if dt < pos.date_added:
                    continue
                if cat == "Cash":
                    mtm_pos = pos.quantity * pos.cost_per_share
                    pnl_pos = 0.0
                else:
                    days = (dt - pos.date_added).days
                    spot = pos.cost_per_share * (1 + (pos.yield_rate or 0.0) * days / 365)
                    mtm_pos = spot * pos.quantity
                    pnl_pos = (spot - pos.cost_per_share) * pos.quantity

                fx = _h_lookup_fx(latest_fx, pos_ccy, acct_ccy) * _h_lookup_fx(latest_fx, acct_ccy, reporting_currency)
                combined[dt]["mtm"] += mtm_pos * fx
                combined[dt]["pnl"] += pnl_pos * fx
                combined[dt].setdefault("cash_gic", 0.0)
                combined[dt]["cash_gic"] += mtm_pos * fx

        points = [
            {
                "date": str(dt),
                "mtm": round(v["mtm"], 2),
                "pnl": round(v["pnl"], 2),
                "cash_gic": round(v.get("cash_gic", 0.0), 2),
            }
            for dt, v in sorted(combined.items())
        ]

        if from_date:
            fd = _parse_date(from_date)
            points = [p for p in points if p["date"] >= str(fd)]
        if to_date:
            td = _parse_date(to_date)
            points = [p for p in points if p["date"] <= str(td)]

        print_output(points, json_output)
    finally:
        db.close()


if __name__ == "__main__":
    app()
