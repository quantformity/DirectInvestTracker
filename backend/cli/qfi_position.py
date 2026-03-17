"""QFI Position management CLI."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import typer
from typing import Optional
from datetime import date, datetime
from sqlalchemy import func

from cli.lib.db import get_session
from cli.lib.output import print_output, error_exit, success_output

app = typer.Typer(help="Manage investment positions.")

REPORTING_CURRENCY = os.getenv("REPORTING_CURRENCY", "CAD")


def _get_latest_prices(db):
    from app.models import MarketData
    subq = (
        db.query(MarketData.symbol, func.max(MarketData.timestamp).label("max_ts"))
        .group_by(MarketData.symbol)
        .subquery()
    )
    rows = (
        db.query(MarketData)
        .join(subq, (MarketData.symbol == subq.c.symbol) & (MarketData.timestamp == subq.c.max_ts))
        .all()
    )
    return {r.symbol: r.last_price for r in rows if r.last_price is not None}


def _get_latest_fx_rates(db):
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
    return {r.pair: r.rate for r in rows}


def _lookup_fx(fx_rates, from_ccy, to_ccy):
    if from_ccy == to_ccy:
        return 1.0
    pair = f"{from_ccy}/{to_ccy}"
    pair_inv = f"{to_ccy}/{from_ccy}"
    if pair in fx_rates:
        return fx_rates[pair]
    if pair_inv in fx_rates and fx_rates[pair_inv] != 0:
        return 1.0 / fx_rates[pair_inv]
    return 1.0


def _enrich_position(p, prices, fx_rates, reporting_currency):
    from app.models import CategoryEnum
    acct_currency = p.account.base_currency.upper()
    stock_currency = p.currency.upper()
    rep_currency = reporting_currency.upper()

    if p.category in (CategoryEnum.GIC, CategoryEnum.Cash, CategoryEnum.Dividend):
        spot = p.cost_per_share
    else:
        spot = prices.get(p.symbol, p.cost_per_share)

    fx_stock_to_account = _lookup_fx(fx_rates, stock_currency, acct_currency)
    fx_account_to_reporting = _lookup_fx(fx_rates, acct_currency, rep_currency)

    mtm_reporting = spot * p.quantity * fx_stock_to_account * fx_account_to_reporting
    pnl_reporting = (spot - p.cost_per_share) * p.quantity * fx_stock_to_account * fx_account_to_reporting

    return {
        "id": p.id,
        "symbol": p.symbol,
        "category": p.category.value if hasattr(p.category, "value") else str(p.category),
        "account_id": p.account_id,
        "account_name": p.account.name,
        "quantity": p.quantity,
        "cost_per_share": p.cost_per_share,
        "currency": p.currency,
        "date_added": str(p.date_added),
        "yield_rate": p.yield_rate,
        "current_price": round(spot, 4),
        "mtm": round(mtm_reporting, 2),
        "pnl": round(pnl_reporting, 2),
    }


@app.command("list")
def list_positions(
    account_id: Optional[int] = typer.Option(None, "--account-id", help="Filter by account ID"),
    category: Optional[str] = typer.Option(None, "--category", help="Filter by category (equity|gic|cash|dividend)"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """List positions with enrichment."""
    db = get_session()
    try:
        from app.models import Position, CategoryEnum
        q = db.query(Position)
        if account_id is not None:
            q = q.filter(Position.account_id == account_id)
        if category:
            cat_map = {
                "equity": CategoryEnum.Equity,
                "gic": CategoryEnum.GIC,
                "cash": CategoryEnum.Cash,
                "dividend": CategoryEnum.Dividend,
            }
            cat_enum = cat_map.get(category.lower())
            if cat_enum:
                q = q.filter(Position.category == cat_enum)
        positions = q.all()
        prices = _get_latest_prices(db)
        fx_rates = _get_latest_fx_rates(db)
        reporting_currency = os.getenv("REPORTING_CURRENCY", REPORTING_CURRENCY)
        data = [_enrich_position(p, prices, fx_rates, reporting_currency) for p in positions]
        print_output(data, json_output)
    finally:
        db.close()


@app.command("show")
def show_position(
    position_id: int = typer.Argument(..., help="Position ID"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show a single position fully enriched."""
    db = get_session()
    try:
        from app.models import Position
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            error_exit(f"Position {position_id} not found")
        prices = _get_latest_prices(db)
        fx_rates = _get_latest_fx_rates(db)
        reporting_currency = os.getenv("REPORTING_CURRENCY", REPORTING_CURRENCY)
        data = _enrich_position(position, prices, fx_rates, reporting_currency)
        print_output(data, json_output)
    finally:
        db.close()


@app.command("add")
def add_position(
    symbol: str = typer.Argument(..., help="Ticker symbol"),
    qty: float = typer.Argument(..., help="Quantity"),
    cost: float = typer.Argument(..., help="Cost per share"),
    account_id: int = typer.Option(..., "--account-id", help="Account ID"),
    category: str = typer.Option(..., "--category", help="Category: equity|gic|cash|dividend"),
    currency: str = typer.Option("USD", "--currency", help="Position currency"),
    date_str: Optional[str] = typer.Option(None, "--date", help="Date added YYYY-MM-DD"),
    yield_rate: Optional[float] = typer.Option(None, "--yield-rate", help="Yield rate"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Add a new position."""
    db = get_session()
    try:
        from app.models import Position, CategoryEnum
        cat_map = {
            "equity": CategoryEnum.Equity,
            "gic": CategoryEnum.GIC,
            "cash": CategoryEnum.Cash,
            "dividend": CategoryEnum.Dividend,
        }
        cat_enum = cat_map.get(category.lower())
        if cat_enum is None:
            error_exit(f"Invalid category: {category}. Use equity|gic|cash|dividend")

        date_added = date.today()
        if date_str:
            try:
                date_added = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                error_exit(f"Invalid date format: {date_str}. Use YYYY-MM-DD")

        position = Position(
            account_id=account_id,
            symbol=symbol.upper(),
            category=cat_enum,
            quantity=qty,
            cost_per_share=cost,
            currency=currency.upper(),
            date_added=date_added,
            yield_rate=yield_rate,
        )
        db.add(position)
        db.commit()
        db.refresh(position)

        prices = _get_latest_prices(db)
        fx_rates = _get_latest_fx_rates(db)
        reporting_currency = os.getenv("REPORTING_CURRENCY", REPORTING_CURRENCY)
        data = _enrich_position(position, prices, fx_rates, reporting_currency)
        print_output(data, json_output)
    finally:
        db.close()


@app.command("modify")
def modify_position(
    position_id: int = typer.Argument(..., help="Position ID"),
    qty: Optional[float] = typer.Option(None, "--qty", help="New quantity"),
    cost: Optional[float] = typer.Option(None, "--cost", help="New cost per share"),
    currency: Optional[str] = typer.Option(None, "--currency", help="New currency"),
    yield_rate: Optional[float] = typer.Option(None, "--yield-rate", help="New yield rate"),
    account_id: Optional[int] = typer.Option(None, "--account-id", help="New account ID"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Modify a position."""
    db = get_session()
    try:
        from app.models import Position
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            error_exit(f"Position {position_id} not found")

        if qty is not None:
            position.quantity = qty
        if cost is not None:
            position.cost_per_share = cost
        if currency is not None:
            position.currency = currency.upper()
        if yield_rate is not None:
            position.yield_rate = yield_rate
        if account_id is not None:
            position.account_id = account_id

        db.commit()
        db.refresh(position)

        prices = _get_latest_prices(db)
        fx_rates = _get_latest_fx_rates(db)
        reporting_currency = os.getenv("REPORTING_CURRENCY", REPORTING_CURRENCY)
        data = _enrich_position(position, prices, fx_rates, reporting_currency)
        print_output(data, json_output)
    finally:
        db.close()


@app.command("delete")
def delete_position(
    position_id: int = typer.Argument(..., help="Position ID"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Delete a position."""
    db = get_session()
    try:
        from app.models import Position
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            error_exit(f"Position {position_id} not found")
        db.delete(position)
        db.commit()
        success_output(f"Position {position_id} deleted", json_output)
    finally:
        db.close()


@app.command("pnl")
def position_pnl(
    account_id: Optional[int] = typer.Option(None, "--account-id", help="Filter by account ID"),
    symbol: Optional[str] = typer.Option(None, "--symbol", help="Filter by symbol"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show unrealised P&L per position."""
    db = get_session()
    try:
        from app.models import Position
        q = db.query(Position)
        if account_id is not None:
            q = q.filter(Position.account_id == account_id)
        if symbol is not None:
            q = q.filter(Position.symbol == symbol.upper())
        positions = q.all()

        prices = _get_latest_prices(db)
        fx_rates = _get_latest_fx_rates(db)
        reporting_currency = os.getenv("REPORTING_CURRENCY", REPORTING_CURRENCY)

        data = []
        for p in positions:
            enriched = _enrich_position(p, prices, fx_rates, reporting_currency)
            data.append({
                "id": enriched["id"],
                "symbol": enriched["symbol"],
                "account_name": enriched["account_name"],
                "quantity": enriched["quantity"],
                "cost_per_share": enriched["cost_per_share"],
                "current_price": enriched["current_price"],
                "mtm": enriched["mtm"],
                "pnl": enriched["pnl"],
                "currency": enriched["currency"],
            })
        print_output(data, json_output)
    finally:
        db.close()


if __name__ == "__main__":
    app()
