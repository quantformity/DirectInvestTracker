"""QFI Report generation CLI."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import typer
import json
from typing import Optional
from datetime import datetime, date, timedelta

from cli.lib.db import get_session
from cli.lib.output import print_output, error_exit

app = typer.Typer(help="Generate investment reports.")

REPORTING_CURRENCY = os.getenv("REPORTING_CURRENCY", "CAD")


def _get_positions_enriched(db, account_id=None):
    from app.models import Position
    from app.routers.summary import _get_latest_prices, _get_latest_fx_rates, _enrich_positions

    reporting_currency = os.getenv("REPORTING_CURRENCY", REPORTING_CURRENCY)
    q = db.query(Position)
    if account_id is not None:
        q = q.filter(Position.account_id == account_id)
    positions = q.all()
    prices = _get_latest_prices(db)
    fx_rates = _get_latest_fx_rates(db)
    enriched = _enrich_positions(positions, prices, fx_rates, reporting_currency)
    return enriched, reporting_currency


def _enriched_to_dict(e):
    return {
        "id": e.id,
        "symbol": e.symbol,
        "category": e.category.value if hasattr(e.category, "value") else str(e.category),
        "account_id": e.account_id,
        "account_name": e.account_name,
        "quantity": e.quantity,
        "cost_per_share": round(e.cost_per_share, 4),
        "currency": e.stock_currency,
        "date_added": str(e.date_added),
        "yield_rate": e.yield_rate,
        "current_price": round(e.spot_price, 4) if e.spot_price else None,
        "mtm": round(e.mtm_reporting, 2),
        "pnl": round(e.pnl_reporting, 2),
        "proportion": round(e.proportion, 2),
    }


def _build_sector_breakdown(db):
    from app.models import SectorMapping
    from app.routers.summary import _get_latest_prices, _get_latest_fx_rates, _enrich_positions
    from app.models import Position

    reporting_currency = os.getenv("REPORTING_CURRENCY", REPORTING_CURRENCY)
    mappings = {m.symbol: m.sector for m in db.query(SectorMapping).all()}
    positions = db.query(Position).all()
    prices = _get_latest_prices(db)
    fx_rates = _get_latest_fx_rates(db)
    enriched = _enrich_positions(positions, prices, fx_rates, reporting_currency)

    sector_data = {}
    for e in enriched:
        s = mappings.get(e.symbol, "Unspecified")
        if s not in sector_data:
            sector_data[s] = {"sector": s, "total_mtm": 0.0, "total_pnl": 0.0, "positions": []}
        sector_data[s]["total_mtm"] += e.mtm_reporting
        sector_data[s]["total_pnl"] += e.pnl_reporting
        sector_data[s]["positions"].append(e.symbol)

    result = []
    for s, v in sorted(sector_data.items()):
        result.append({
            "sector": v["sector"],
            "total_mtm": round(v["total_mtm"], 2),
            "total_pnl": round(v["total_pnl"], 2),
            "symbols": sorted(set(v["positions"])),
        })
    return result


def _build_account_breakdown(db):
    from app.models import Account
    from app.routers.summary import _get_latest_prices, _get_latest_fx_rates, _enrich_positions
    from app.models import Position

    reporting_currency = os.getenv("REPORTING_CURRENCY", REPORTING_CURRENCY)
    accounts = db.query(Account).all()
    positions = db.query(Position).all()
    prices = _get_latest_prices(db)
    fx_rates = _get_latest_fx_rates(db)
    enriched = _enrich_positions(positions, prices, fx_rates, reporting_currency)

    acct_data = {}
    for e in enriched:
        key = e.account_id
        if key not in acct_data:
            acct_data[key] = {"account_id": key, "account_name": e.account_name, "total_mtm": 0.0, "total_pnl": 0.0}
        acct_data[key]["total_mtm"] += e.mtm_reporting
        acct_data[key]["total_pnl"] += e.pnl_reporting

    result = []
    for k, v in sorted(acct_data.items()):
        result.append({
            "account_id": v["account_id"],
            "account_name": v["account_name"],
            "total_mtm": round(v["total_mtm"], 2),
            "total_pnl": round(v["total_pnl"], 2),
        })
    return result


def _period_to_from_date(period: str) -> Optional[date]:
    today = date.today()
    if period == "1d":
        return today - timedelta(days=1)
    elif period == "1w":
        return today - timedelta(weeks=1)
    elif period == "1m":
        return today - timedelta(days=30)
    elif period == "3m":
        return today - timedelta(days=90)
    elif period == "1y":
        return today - timedelta(days=365)
    elif period == "all":
        return None
    return None


def _generate_html(report_data: dict) -> str:
    total_mtm = report_data.get("total_mtm", 0)
    total_pnl = report_data.get("total_pnl", 0)
    positions = report_data.get("positions", [])
    sector_breakdown = report_data.get("sector_breakdown", [])
    account_breakdown = report_data.get("account_breakdown", [])
    reporting_currency = report_data.get("reporting_currency", "CAD")

    positions_rows = ""
    for p in positions:
        pnl_class = "text-success" if p.get("pnl", 0) >= 0 else "text-danger"
        positions_rows += f"""
        <tr>
            <td>{p.get('symbol','')}</td>
            <td>{p.get('category','')}</td>
            <td>{p.get('account_name','')}</td>
            <td>{p.get('quantity','')}</td>
            <td>{p.get('cost_per_share','')}</td>
            <td>{p.get('current_price','')}</td>
            <td>{p.get('mtm','')}</td>
            <td class="{pnl_class}">{p.get('pnl','')}</td>
        </tr>"""

    sector_rows = ""
    for s in sector_breakdown:
        pnl_class = "text-success" if s.get("total_pnl", 0) >= 0 else "text-danger"
        sector_rows += f"""
        <tr>
            <td>{s.get('sector','')}</td>
            <td>{s.get('total_mtm','')}</td>
            <td class="{pnl_class}">{s.get('total_pnl','')}</td>
            <td>{', '.join(s.get('symbols',[]))}</td>
        </tr>"""

    account_rows = ""
    for a in account_breakdown:
        pnl_class = "text-success" if a.get("total_pnl", 0) >= 0 else "text-danger"
        account_rows += f"""
        <tr>
            <td>{a.get('account_name','')}</td>
            <td>{a.get('total_mtm','')}</td>
            <td class="{pnl_class}">{a.get('total_pnl','')}</td>
        </tr>"""

    context_json = json.dumps({"total_mtm": total_mtm, "total_pnl": total_pnl, "reporting_currency": reporting_currency})

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Investment Portfolio Report</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ padding: 20px; }}
        .llm-narrative {{ background: #f8f9fa; border-left: 4px solid #0d6efd; padding: 15px; margin: 15px 0; font-style: italic; color: #6c757d; }}
        .metric-card {{ border-radius: 8px; }}
    </style>
</head>
<body>
    <div class="container-fluid">
        <h1 class="mb-4">Investment Portfolio Report</h1>
        <p class="text-muted">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Currency: {reporting_currency}</p>

        <div class="row mb-4">
            <div class="col-md-4">
                <div class="card metric-card text-bg-primary">
                    <div class="card-body">
                        <h5 class="card-title">Total MTM</h5>
                        <p class="card-text fs-4">{reporting_currency} {total_mtm:,.2f}</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card metric-card {'text-bg-success' if total_pnl >= 0 else 'text-bg-danger'}">
                    <div class="card-body">
                        <h5 class="card-title">Total P&L</h5>
                        <p class="card-text fs-4">{reporting_currency} {total_pnl:,.2f}</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="llm-narrative" data-llm-section="portfolio_overview" data-context='{context_json}'>
            <!-- Agent: insert portfolio overview narrative here -->
        </div>

        <h2 class="mt-4">Positions</h2>
        <div class="table-responsive">
            <table class="table table-striped table-hover">
                <thead class="table-dark">
                    <tr>
                        <th>Symbol</th><th>Category</th><th>Account</th>
                        <th>Quantity</th><th>Cost</th><th>Price</th>
                        <th>MTM ({reporting_currency})</th><th>P&L ({reporting_currency})</th>
                    </tr>
                </thead>
                <tbody>{positions_rows}</tbody>
            </table>
        </div>

        <div class="llm-narrative" data-llm-section="positions_analysis" data-context='{json.dumps({"position_count": len(positions)})}'>
            <!-- Agent: insert positions analysis narrative here -->
        </div>

        <h2 class="mt-4">Sector Breakdown</h2>
        <div class="table-responsive">
            <table class="table table-striped table-hover">
                <thead class="table-dark">
                    <tr><th>Sector</th><th>MTM ({reporting_currency})</th><th>P&L ({reporting_currency})</th><th>Symbols</th></tr>
                </thead>
                <tbody>{sector_rows}</tbody>
            </table>
        </div>

        <div class="llm-narrative" data-llm-section="sector_analysis" data-context='{json.dumps({"sectors": [s["sector"] for s in sector_breakdown]})}'>
            <!-- Agent: insert sector analysis narrative here -->
        </div>

        <h2 class="mt-4">Account Breakdown</h2>
        <div class="table-responsive">
            <table class="table table-striped table-hover">
                <thead class="table-dark">
                    <tr><th>Account</th><th>MTM ({reporting_currency})</th><th>P&L ({reporting_currency})</th></tr>
                </thead>
                <tbody>{account_rows}</tbody>
            </table>
        </div>

        <div class="llm-narrative" data-llm-section="account_analysis" data-context='{json.dumps({"accounts": [a["account_name"] for a in account_breakdown]})}'>
            <!-- Agent: insert account analysis narrative here -->
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
    return html


def _generate_csv(positions: list) -> str:
    if not positions:
        return "symbol,category,account_name,quantity,cost_per_share,currency,current_price,mtm,pnl\n"
    headers = ["symbol", "category", "account_name", "quantity", "cost_per_share", "currency", "current_price", "mtm", "pnl"]
    lines = [",".join(headers)]
    for p in positions:
        row = [str(p.get(h, "")) for h in headers]
        lines.append(",".join(row))
    return "\n".join(lines) + "\n"


@app.command("generate")
def generate_report(
    format: str = typer.Option("json", "--format", help="Output format: json|csv|html"),
    account_id: Optional[int] = typer.Option(None, "--account-id", help="Filter by account ID"),
    from_date: Optional[str] = typer.Option(None, "--from", help="Start date YYYY-MM-DD"),
    to_date: Optional[str] = typer.Option(None, "--to", help="End date YYYY-MM-DD"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Generate a comprehensive report."""
    db = get_session()
    try:
        enriched, reporting_currency = _get_positions_enriched(db, account_id=account_id)
        positions_data = [_enriched_to_dict(e) for e in enriched]

        total_mtm = round(sum(e.mtm_reporting for e in enriched), 2)
        total_pnl = round(sum(e.pnl_reporting for e in enriched), 2)

        sector_breakdown = _build_sector_breakdown(db)
        account_breakdown = _build_account_breakdown(db)

        report_data = {
            "generated_at": str(datetime.now()),
            "reporting_currency": reporting_currency,
            "total_mtm": total_mtm,
            "total_pnl": total_pnl,
            "positions": positions_data,
            "sector_breakdown": sector_breakdown,
            "account_breakdown": account_breakdown,
        }

        if format == "json":
            import json as json_mod
            print(json_mod.dumps(report_data, indent=2, default=str))
        elif format == "html":
            print(_generate_html(report_data))
        elif format == "csv":
            print(_generate_csv(positions_data))
        else:
            error_exit(f"Unknown format: {format}. Use json|csv|html")
    finally:
        db.close()


@app.command("positions")
def positions_report(
    account_id: Optional[int] = typer.Option(None, "--account-id", help="Filter by account ID"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Generate positions report."""
    db = get_session()
    try:
        enriched, reporting_currency = _get_positions_enriched(db, account_id=account_id)
        data = [_enriched_to_dict(e) for e in enriched]
        print_output(data, json_output)
    finally:
        db.close()


@app.command("pnl")
def pnl_report(
    period: str = typer.Option("1m", "--period", help="Period: 1d|1w|1m|3m|1y|all"),
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """P&L report for period."""
    db = get_session()
    try:
        enriched, reporting_currency = _get_positions_enriched(db)
        from_dt = _period_to_from_date(period)

        positions_data = []
        for e in enriched:
            if from_dt and e.date_added < from_dt:
                continue
            positions_data.append({
                "symbol": e.symbol,
                "category": e.category.value if hasattr(e.category, "value") else str(e.category),
                "account_name": e.account_name,
                "pnl": round(e.pnl_reporting, 2),
                "mtm": round(e.mtm_reporting, 2),
                "period": period,
            })

        total_pnl = round(sum(p["pnl"] for p in positions_data), 2)
        result = {
            "period": period,
            "reporting_currency": reporting_currency,
            "total_pnl": total_pnl,
            "positions": positions_data,
        }
        print_output(result, json_output)
    finally:
        db.close()


@app.command("sector-breakdown")
def sector_breakdown_report(
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Sector breakdown report."""
    db = get_session()
    try:
        data = _build_sector_breakdown(db)
        print_output(data, json_output)
    finally:
        db.close()


@app.command("account-breakdown")
def account_breakdown_report(
    json_output: bool = typer.Option(False, "--json", flag_value=True, help="Output as JSON"),
):
    """Account breakdown report."""
    db = get_session()
    try:
        data = _build_account_breakdown(db)
        print_output(data, json_output)
    finally:
        db.close()


if __name__ == "__main__":
    app()
