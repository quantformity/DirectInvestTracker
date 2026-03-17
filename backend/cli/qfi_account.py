"""QFI Account management CLI."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import typer
from typing import Optional
from sqlalchemy import func

from cli.lib.db import get_session
from cli.lib.output import print_output, error_exit, success_output

app = typer.Typer(help="Manage investment accounts.")

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


def _compute_account_mtm(account, db, reporting_currency):
    from app.models import CategoryEnum
    prices = _get_latest_prices(db)
    fx_rates = _get_latest_fx_rates(db)
    total_mtm = 0.0

    for p in account.positions:
        acct_currency = account.base_currency.upper()
        stock_currency = p.currency.upper()

        if p.category in (CategoryEnum.GIC, CategoryEnum.Cash, CategoryEnum.Dividend):
            spot = p.cost_per_share
        else:
            spot = prices.get(p.symbol, p.cost_per_share)

        fx_stock_to_account = _lookup_fx(fx_rates, stock_currency, acct_currency)
        fx_account_to_reporting = _lookup_fx(fx_rates, acct_currency, reporting_currency)
        mtm_reporting = spot * p.quantity * fx_stock_to_account * fx_account_to_reporting
        total_mtm += mtm_reporting

    return round(total_mtm, 2)


@app.command("list")
def list_accounts(
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """List all accounts."""
    db = get_session()
    try:
        from app.models import Account
        accounts = db.query(Account).all()
        data = [{"id": a.id, "name": a.name, "base_currency": a.base_currency} for a in accounts]
        print_output(data, json_output)
    finally:
        db.close()


@app.command("add")
def add_account(
    name: str = typer.Argument(..., help="Account name"),
    currency: str = typer.Option("CAD", "--currency", help="Base currency"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Add a new account."""
    db = get_session()
    try:
        from app.models import Account
        account = Account(name=name, base_currency=currency.upper())
        db.add(account)
        db.commit()
        db.refresh(account)
        data = {"id": account.id, "name": account.name, "base_currency": account.base_currency}
        print_output(data, json_output)
    finally:
        db.close()


@app.command("show")
def show_account(
    account_id: int = typer.Argument(..., help="Account ID"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show account details with MTM."""
    db = get_session()
    try:
        from app.models import Account
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            error_exit(f"Account {account_id} not found")

        reporting_currency = os.getenv("REPORTING_CURRENCY", REPORTING_CURRENCY)
        total_mtm = _compute_account_mtm(account, db, reporting_currency.upper())

        data = {
            "id": account.id,
            "name": account.name,
            "base_currency": account.base_currency,
            "total_mtm": total_mtm,
            "reporting_currency": reporting_currency,
        }
        print_output(data, json_output)
    finally:
        db.close()


@app.command("rename")
def rename_account(
    account_id: int = typer.Argument(..., help="Account ID"),
    name: str = typer.Argument(..., help="New name"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Rename an account."""
    db = get_session()
    try:
        from app.models import Account
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            error_exit(f"Account {account_id} not found")
        account.name = name
        db.commit()
        db.refresh(account)
        data = {"id": account.id, "name": account.name, "base_currency": account.base_currency}
        print_output(data, json_output)
    finally:
        db.close()


@app.command("delete")
def delete_account(
    account_id: int = typer.Argument(..., help="Account ID"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Delete an account."""
    db = get_session()
    try:
        from app.models import Account
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            error_exit(f"Account {account_id} not found")
        db.delete(account)
        db.commit()
        success_output(f"Account {account_id} deleted", json_output)
    finally:
        db.close()


@app.command("mtm")
def account_mtm(
    account_id: Optional[int] = typer.Option(None, "--account-id", help="Filter by account ID"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Show mark-to-market per account."""
    db = get_session()
    try:
        from app.models import Account
        reporting_currency = os.getenv("REPORTING_CURRENCY", REPORTING_CURRENCY)
        q = db.query(Account)
        if account_id is not None:
            q = q.filter(Account.id == account_id)
        accounts = q.all()

        data = []
        for account in accounts:
            total_mtm = _compute_account_mtm(account, db, reporting_currency.upper())
            data.append({
                "account_id": account.id,
                "account_name": account.name,
                "mtm": total_mtm,
                "reporting_currency": reporting_currency,
            })
        print_output(data, json_output)
    finally:
        db.close()


if __name__ == "__main__":
    app()
