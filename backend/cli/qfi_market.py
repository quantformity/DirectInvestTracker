"""QFI Market data CLI."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import typer
from typing import Optional
from datetime import datetime, timezone

from cli.lib.db import get_session
from cli.lib.output import print_output, error_exit, success_output
from cli.lib.yahoo import fetch_prices, fetch_history

app = typer.Typer(help="Manage market data.")


def _md_to_dict(md):
    return {
        "symbol": md.symbol,
        "company_name": md.company_name,
        "last_price": md.last_price,
        "pe_ratio": md.pe_ratio,
        "change_percent": md.change_percent,
        "beta": md.beta,
        "timestamp": str(md.timestamp),
    }


@app.command("quote")
def quote(
    symbol: str = typer.Argument(..., help="Ticker symbol"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show latest market data for a symbol."""
    db = get_session()
    try:
        from app.models import MarketData
        from sqlalchemy import func
        latest_ts = (
            db.query(func.max(MarketData.timestamp))
            .filter(MarketData.symbol == symbol.upper())
            .scalar()
        )
        if latest_ts is None:
            error_exit(f"No market data found for symbol '{symbol}'")
        md = (
            db.query(MarketData)
            .filter(MarketData.symbol == symbol.upper(), MarketData.timestamp == latest_ts)
            .first()
        )
        if not md:
            error_exit(f"No market data found for symbol '{symbol}'")
        print_output(_md_to_dict(md), json_output)
    finally:
        db.close()


@app.command("quote-list")
def quote_list(
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show latest market data for all symbols."""
    db = get_session()
    try:
        from app.models import MarketData
        from sqlalchemy import func
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
        data = [_md_to_dict(r) for r in rows]
        print_output(data, json_output)
    finally:
        db.close()


@app.command("refresh")
def refresh(
    symbol: Optional[str] = typer.Option(None, "--symbol", help="Refresh specific symbol only"),
    full_history: bool = typer.Option(False, "--full-history", help="Also fetch full price history"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Fetch and store latest prices from Yahoo Finance."""
    db = get_session()
    try:
        from app.models import Position, MarketData, CategoryEnum
        from app.services import history_cache

        q = db.query(Position).filter(Position.category == CategoryEnum.Equity)
        if symbol:
            q = q.filter(Position.symbol == symbol.upper())
        positions = q.all()

        if not positions:
            msg = f"No equity positions found{' for ' + symbol if symbol else ''}"
            if json_output:
                print_output({"message": msg, "updated": []}, json_output)
            else:
                print_output(msg, json_output)
            return

        symbols = list(set(p.symbol for p in positions))
        prices = fetch_prices(symbols)

        now = datetime.now(timezone.utc)
        updated = []
        for sym, data in prices.items():
            md = MarketData(
                symbol=sym,
                company_name=data.get("company_name"),
                last_price=data.get("last_price"),
                pe_ratio=data.get("pe_ratio"),
                change_percent=data.get("change_percent"),
                beta=data.get("beta"),
                timestamp=now,
            )
            db.add(md)
            updated.append(sym)

        db.commit()

        if full_history:
            import time
            for pos in positions:
                try:
                    df = fetch_history(pos.symbol, start_date=pos.date_added)
                    if not df.empty:
                        history_cache.write_cache(pos.symbol, df)
                    time.sleep(0.3)
                except Exception as e:
                    pass

        result = {"updated": updated, "count": len(updated)}
        print_output(result, json_output)
    finally:
        db.close()


@app.command("add")
def add_market_data(
    symbol: str = typer.Argument(..., help="Ticker symbol"),
    price: float = typer.Option(..., "--price", help="Last price"),
    pe_ratio: Optional[float] = typer.Option(None, "--pe", help="P/E ratio"),
    change_percent: Optional[float] = typer.Option(None, "--change", help="Change percent"),
    beta: Optional[float] = typer.Option(None, "--beta", help="Beta"),
    name: Optional[str] = typer.Option(None, "--name", help="Company name"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Insert a market data row."""
    db = get_session()
    try:
        from app.models import MarketData
        now = datetime.now(timezone.utc)
        md = MarketData(
            symbol=symbol.upper(),
            company_name=name,
            last_price=price,
            pe_ratio=pe_ratio,
            change_percent=change_percent,
            beta=beta,
            timestamp=now,
        )
        db.add(md)
        db.commit()
        db.refresh(md)
        print_output(_md_to_dict(md), json_output)
    finally:
        db.close()


@app.command("modify")
def modify_market_data(
    symbol: str = typer.Argument(..., help="Ticker symbol"),
    price: Optional[float] = typer.Option(None, "--price", help="New price"),
    pe_ratio: Optional[float] = typer.Option(None, "--pe", help="New P/E ratio"),
    change_percent: Optional[float] = typer.Option(None, "--change", help="New change percent"),
    beta: Optional[float] = typer.Option(None, "--beta", help="New beta"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Insert a new market data row with updated values (append-only)."""
    db = get_session()
    try:
        from app.models import MarketData
        from sqlalchemy import func

        # Get existing values
        latest_ts = (
            db.query(func.max(MarketData.timestamp))
            .filter(MarketData.symbol == symbol.upper())
            .scalar()
        )
        existing = None
        if latest_ts:
            existing = (
                db.query(MarketData)
                .filter(MarketData.symbol == symbol.upper(), MarketData.timestamp == latest_ts)
                .first()
            )

        now = datetime.now(timezone.utc)
        md = MarketData(
            symbol=symbol.upper(),
            company_name=existing.company_name if existing else None,
            last_price=price if price is not None else (existing.last_price if existing else None),
            pe_ratio=pe_ratio if pe_ratio is not None else (existing.pe_ratio if existing else None),
            change_percent=change_percent if change_percent is not None else (existing.change_percent if existing else None),
            beta=beta if beta is not None else (existing.beta if existing else None),
            timestamp=now,
        )
        db.add(md)
        db.commit()
        db.refresh(md)
        print_output(_md_to_dict(md), json_output)
    finally:
        db.close()


@app.command("history")
def history(
    symbol: str = typer.Argument(..., help="Ticker symbol"),
    from_date: Optional[str] = typer.Option(None, "--from", help="Start date YYYY-MM-DD"),
    to_date: Optional[str] = typer.Option(None, "--to", help="End date YYYY-MM-DD"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show market data history for a symbol."""
    db = get_session()
    try:
        from app.models import MarketData
        from datetime import datetime as dt
        q = db.query(MarketData).filter(MarketData.symbol == symbol.upper())
        if from_date:
            try:
                start = dt.strptime(from_date, "%Y-%m-%d")
                q = q.filter(MarketData.timestamp >= start)
            except ValueError:
                error_exit(f"Invalid date format: {from_date}. Use YYYY-MM-DD")
        if to_date:
            try:
                end = dt.strptime(to_date, "%Y-%m-%d")
                # Include the entire end date
                from datetime import timedelta
                end = end + timedelta(days=1)
                q = q.filter(MarketData.timestamp < end)
            except ValueError:
                error_exit(f"Invalid date format: {to_date}. Use YYYY-MM-DD")
        rows = q.order_by(MarketData.timestamp).all()
        data = [_md_to_dict(r) for r in rows]
        print_output(data, json_output)
    finally:
        db.close()


if __name__ == "__main__":
    app()
