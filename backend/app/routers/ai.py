import re
import io
import json
import base64
import logging
import traceback
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Position, Account, CategoryEnum, SectorMapping
from app.schemas import (
    ChatRequest, ChatResponse, ChartRequest, ChartResponse,
    ActionRequest, ActionPlan, ExecuteActionRequest, ExecuteActionResponse,
    SqlExecuteRequest, ReportSummaryRequest, ReportSummaryResponse,
)
from app.services import ollama

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── SQL Safety ──────────────────────────────────────────────────────────────

_ALLOWED_SQL_PATTERN = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|DETACH|REPLACE|TRUNCATE|EXEC|EXECUTE|PRAGMA)\b",
    re.IGNORECASE,
)


def _sanitize_sql(sql: str) -> str | None:
    """Return cleaned SQL if safe, else None."""
    sql = sql.strip().rstrip(";")
    if not _ALLOWED_SQL_PATTERN.match(sql):
        return None
    if _FORBIDDEN_SQL_PATTERN.search(sql):
        return None
    return sql


def _extract_code_block(text: str, lang: str) -> str | None:
    """Extract the first fenced code block of the given language."""
    pattern = rf"```{lang}\s*(.*?)```"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else None


# ─── Restricted exec environment ─────────────────────────────────────────────

def _build_exec_globals(db: Session) -> dict[str, Any]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import plotly.graph_objects as go
    import pandas as pd

    return {
        "__builtins__": {
            "print": print, "len": len, "range": range,
            "list": list, "dict": dict, "str": str, "int": int,
            "float": float, "round": round, "sum": sum, "min": min,
            "max": max, "zip": zip, "enumerate": enumerate,
            "sorted": sorted, "abs": abs,
        },
        "db_session": db,
        "plt": plt,
        "go": go,
        "pd": pd,
        "json": json,
        "fig": None,
        "plotly_json": None,
    }


# ─── Portfolio snapshot ───────────────────────────────────────────────────────

def _build_portfolio_context(db: Session) -> str:
    """Build a human-readable portfolio snapshot with pre-computed PnL for LLM context."""
    from sqlalchemy import func
    from app.models import MarketData, FxRate

    # Accounts
    accounts = db.query(Account).all()
    acct_map = {a.id: a for a in accounts}

    # Latest prices
    subq_md = (
        db.query(MarketData.symbol, func.max(MarketData.timestamp).label("max_ts"))
        .group_by(MarketData.symbol).subquery()
    )
    prices = {
        r.symbol: r for r in
        db.query(MarketData)
        .join(subq_md, (MarketData.symbol == subq_md.c.symbol) & (MarketData.timestamp == subq_md.c.max_ts))
        .all()
    }

    # Latest FX rates
    subq_fx = (
        db.query(FxRate.pair, func.max(FxRate.timestamp).label("max_ts"))
        .group_by(FxRate.pair).subquery()
    )
    fx_rates = {
        r.pair: r.rate for r in
        db.query(FxRate)
        .join(subq_fx, (FxRate.pair == subq_fx.c.pair) & (FxRate.timestamp == subq_fx.c.max_ts))
        .all()
    }

    lines: list[str] = []

    # Accounts table
    lines.append("ACCOUNTS:")
    lines.append("  ID | Name                | Currency")
    for a in accounts:
        lines.append(f"  {a.id:<3}| {a.name:<20} | {a.base_currency}")

    # Positions table with pre-computed PnL
    positions = db.query(Position).all()
    lines.append("\nPOSITIONS (with live PnL in position currency):")
    lines.append("  ID  | Symbol           | Category | Account              | Qty        | Cost/sh  | Price    | PnL         | MTM")

    for p in positions:
        acct = acct_map.get(p.account_id)
        acct_name = acct.name if acct else f"#{p.account_id}"
        cat = p.category.value if hasattr(p.category, "value") else str(p.category)

        md = prices.get(p.symbol)
        if cat == "Equity" and md and md.last_price:
            price = md.last_price
            pnl   = (price - p.cost_per_share) * p.quantity
            mtm   = price * p.quantity
            price_s = f"{price:>8.2f}"
            pnl_s   = f"{pnl:>+12.2f}"
            mtm_s   = f"{mtm:>12.2f}"
        else:
            price_s = "      —"
            pnl_s   = "           —"
            mtm_s   = f"{p.cost_per_share * p.quantity:>12.2f}"

        lines.append(
            f"  {p.id:<5}| {p.symbol:<17}| {cat:<9}| {acct_name:<21}| {p.quantity:>10,.2f} | "
            f"{p.cost_per_share:>8.4f} | {price_s} | {pnl_s} | {mtm_s}  {p.currency}"
        )

    # Market data summary
    if prices:
        lines.append("\nLATEST MARKET PRICES:")
        for sym, m in prices.items():
            chg  = f"{m.change_percent:+.2f}%" if m.change_percent is not None else "n/a"
            pe   = f"{m.pe_ratio:.1f}" if m.pe_ratio else "—"
            beta = f"{m.beta:.2f}" if m.beta else "—"
            lines.append(f"  {sym}: price={m.last_price:.4f} | 1d chg={chg} | PE={pe} | beta={beta}")

    # FX rates
    if fx_rates:
        lines.append("\nLATEST FX RATES:")
        for pair, rate in fx_rates.items():
            lines.append(f"  {pair}: {rate:.6f}")

    # Sector mappings (only if any are set)
    sector_mappings = db.query(SectorMapping).all()
    if sector_mappings:
        sector_map = {m.symbol: m.sector for m in sector_mappings}
        # Group symbols by sector
        from collections import defaultdict
        by_sector: dict[str, list[str]] = defaultdict(list)
        for sym, sec in sorted(sector_map.items()):
            by_sector[sec].append(sym)
        lines.append("\nSECTOR MAPPINGS:")
        for sec, syms in sorted(by_sector.items()):
            lines.append(f"  {sec}: {', '.join(syms)}")

    return "\n".join(lines)


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
def ai_chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Send a message to the AI.
    - If the question looks data-oriented, generate SQL and return it as
      pending_sql for the user to confirm before execution.
    - Otherwise fall back to priming-exchange chat with live portfolio context.
    """
    user_messages = [m for m in request.messages if m.role == "user"]
    if not user_messages:
        return ChatResponse(reply="Please ask a question about your portfolio.")

    last_question = user_messages[-1].content

    # ── Text-to-SQL pipeline: generate only, do NOT execute yet ──────────────
    try:
        sql_messages = [{"role": m.role, "content": m.content} for m in request.messages]
        raw_sql = ollama.generate_sql_for_question(sql_messages)

        sql_block = _extract_code_block(raw_sql, "sql")
        sql = _sanitize_sql(sql_block or raw_sql)

        if sql:
            return ChatResponse(
                reply="I can answer that with the following SQL query. Run it to see the results:",
                pending_sql=sql,
            )

        logger.info("SQL pipeline: sanitize rejected output — falling back to chat")
    except Exception as exc:
        logger.warning("Text-to-SQL pipeline failed: %s — falling back to chat", exc)

    # ── Fallback: priming exchange with live portfolio snapshot ───────────────
    portfolio_context = _build_portfolio_context(db)
    priming: list[dict] = [
        {
            "role": "user",
            "content": (
                "Here is my current portfolio data. Use it to answer all my questions:\n\n"
                + portfolio_context
            ),
        },
        {
            "role": "assistant",
            "content": (
                "I have your portfolio data loaded. I can see your accounts, positions, "
                "current market prices and FX rates. Ask me anything about your portfolio."
            ),
        },
    ]
    system_prompt = ollama.build_system_prompt()
    messages = priming + [m.model_dump() for m in request.messages]
    reply = ollama.chat(messages, system_prompt=system_prompt)

    # Surface Ollama errors clearly so the user knows to check AI Settings
    if reply.startswith("Error"):
        return ChatResponse(
            reply=f"⚠️ AI service error: {reply}\n\nTip: open **AI Settings** (⚙️ in the sidebar) and verify the Ollama URL and model names."
        )
    return ChatResponse(reply=reply)


@router.post("/sql/execute", response_model=ChatResponse)
def ai_sql_execute(request: SqlExecuteRequest, db: Session = Depends(get_db)):
    """Execute a user-confirmed SQL query and return a natural-language answer."""
    sql = _sanitize_sql(request.sql)
    if not sql:
        return ChatResponse(reply="❌ That query cannot be executed (only SELECT statements are allowed).")
    try:
        from sqlalchemy import text as sa_text
        result = db.execute(sa_text(sql))
        rows = result.fetchall()
        columns = list(result.keys())
        data = [dict(zip(columns, row)) for row in rows]
        reply = ollama.format_sql_results(request.question, sql, data)
        return ChatResponse(reply=reply)
    except Exception as exc:
        logger.error("SQL execute error: %s\nSQL: %s", exc, sql)
        return ChatResponse(reply=f"❌ Query failed: {exc}")


@router.post("/chart", response_model=ChartResponse)
def ai_chart(request: ChartRequest, db: Session = Depends(get_db)):
    """
    Generate a chart or data table from a natural language prompt.
    The LLM produces either a SQL SELECT or a Python snippet.
    """
    llm_output = ollama.generate_sql_or_code(request.prompt)

    # ── Try SQL path first ───────────────────────────────────────────────────
    sql_block = _extract_code_block(llm_output, "sql")
    if sql_block:
        sql = _sanitize_sql(sql_block)
        if sql is None:
            return ChartResponse(type="error", data="LLM generated unsafe SQL. Only SELECT queries are allowed.")
        try:
            from sqlalchemy import text
            result = db.execute(text(sql))
            rows = result.fetchall()
            columns = list(result.keys())
            data = [dict(zip(columns, row)) for row in rows]
            return ChartResponse(type="table", data=json.dumps(data))
        except Exception as exc:
            logger.error("SQL execution error: %s\nSQL: %s", exc, sql)
            return ChartResponse(type="error", data=f"SQL execution failed: {exc}")

    # ── Try Python plot path ─────────────────────────────────────────────────
    py_block = _extract_code_block(llm_output, "python")
    if py_block:
        g = _build_exec_globals(db)
        try:
            exec(py_block, g)  # noqa: S102

            # Matplotlib figure
            if g.get("fig") is not None:
                buf = io.BytesIO()
                g["fig"].savefig(buf, format="png", bbox_inches="tight")
                buf.seek(0)
                encoded = base64.b64encode(buf.read()).decode("utf-8")
                return ChartResponse(type="image", data=encoded)

            # Plotly JSON
            if g.get("plotly_json") is not None:
                return ChartResponse(type="plotly", data=g["plotly_json"])

            # Check if matplotlib has a current figure
            import matplotlib.pyplot as plt
            current_fig = plt.gcf()
            if current_fig.get_axes():
                buf = io.BytesIO()
                current_fig.savefig(buf, format="png", bbox_inches="tight")
                buf.seek(0)
                encoded = base64.b64encode(buf.read()).decode("utf-8")
                plt.close("all")
                return ChartResponse(type="image", data=encoded)

            plt.close("all")
            return ChartResponse(type="error", data="Python code ran but produced no chart output.")
        except Exception:
            tb = traceback.format_exc()
            logger.error("Python exec error:\n%s", tb)
            return ChartResponse(type="error", data=f"Chart generation failed: {tb[:500]}")

    # ── Fallback: no code block found, return as text ────────────────────────
    return ChartResponse(type="error", data=f"Could not parse LLM output into SQL or Python. Raw: {llm_output[:300]}")


# ─── Report summary endpoint ─────────────────────────────────────────────────

@router.post("/report-summary", response_model=ReportSummaryResponse)
def ai_report_summary(request: ReportSummaryRequest):
    """Generate an AI narrative analysis of the portfolio report data."""

    # ── Build a compact text snapshot of the report data ─────────────────────
    lines: list[str] = [
        f"PORTFOLIO REPORT — {request.period_label} ({request.date_range})",
        f"Reporting Currency: {request.reporting_currency}",
        "",
        "OVERVIEW:",
        f"  Total MTM:  {request.reporting_currency} {request.total_mtm:,.2f}",
        f"  Total PnL:  {request.reporting_currency} {request.total_pnl:+,.2f}",
    ]
    if request.period_gain is not None:
        pct = f" ({request.period_pct:+.1f}%)" if request.period_pct is not None else ""
        lines.append(
            f"  {request.period_label} Gain: {request.reporting_currency} "
            f"{request.period_gain:+,.2f}{pct}"
        )

    lines += ["", "BY CATEGORY:"]
    for g in request.summary_by_category:
        lines.append(
            f"  {g.get('group_key','?')}: "
            f"MTM={g.get('total_mtm_reporting',0):,.2f}  "
            f"PnL={g.get('total_pnl_reporting',0):+,.2f}  "
            f"({g.get('proportion',0):.1f}%)"
        )

    lines += ["", "BY ACCOUNT:"]
    for g in request.summary_by_account:
        lines.append(
            f"  {g.get('group_key','?')}: "
            f"MTM={g.get('total_mtm_reporting',0):,.2f}  "
            f"PnL={g.get('total_pnl_reporting',0):+,.2f}  "
            f"({g.get('proportion',0):.1f}%)"
        )

    equity = [p for p in request.positions if p.get("category") == "Equity"]
    if equity:
        lines += ["", "EQUITY POSITIONS (sorted by PnL, best to worst):"]
        for p in sorted(equity, key=lambda x: float(x.get("pnl_reporting", 0)), reverse=True):
            spot = f"{p['spot_price']:.2f}" if p.get("spot_price") else "—"
            lines.append(
                f"  {p.get('symbol','?')} | "
                f"qty={p.get('quantity',0):.0f}  cost={p.get('cost_per_share',0):.2f}  spot={spot}  "
                f"MTM={p.get('mtm_reporting',0):,.2f}  PnL={p.get('pnl_reporting',0):+,.2f}  "
                f"wt={p.get('proportion',0):.1f}%"
            )

    non_equity = [p for p in request.positions if p.get("category") in ("Cash", "GIC")]
    if non_equity:
        lines += ["", "CASH & GIC POSITIONS:"]
        for p in non_equity:
            lines.append(
                f"  {p.get('symbol','?')} ({p.get('category','?')}) | "
                f"MTM={p.get('mtm_reporting',0):,.2f}  wt={p.get('proportion',0):.1f}%"
            )

    if request.market_data:
        lines += ["", "MARKET DATA:"]
        for m in request.market_data:
            beta = f"beta={m['beta']:.2f}" if m.get("beta") else "beta=n/a"
            pe   = f"P/E={m['pe_ratio']:.1f}" if m.get("pe_ratio") else "P/E=n/a"
            chg  = f"1d={m['change_percent']:+.2f}%" if m.get("change_percent") is not None else "1d=n/a"
            lines.append(
                f"  {m.get('symbol','?')}: price={m.get('last_price',0):.2f}  "
                f"{chg}  {pe}  {beta}"
            )

    data_text = "\n".join(lines)

    system = (
        "You are a professional portfolio analyst writing a concise narrative summary "
        "for inclusion in a printed investment report.\n\n"
        "Analyse the data provided and write a clear, insightful summary covering:\n"
        "1. **Overall Portfolio Health** — total value, cumulative PnL and period performance in plain terms.\n"
        "2. **Top Performer** — the single biggest positive PnL contributor, with the gain amount and % weight.\n"
        "3. **Worst Performer** — the biggest PnL drag, with the loss amount.\n"
        "4. **Concentration Risk** — flag any position(s) with weight >20% and explain the risk.\n"
        "5. **Market Sensitivity** — identify the highest-beta equity and what that means for the portfolio.\n"
        "6. **Other Observations** — e.g. currency exposure, Cash/GIC cushion, P/E outliers, "
        "or any notable patterns worth mentioning.\n\n"
        "Style rules:\n"
        "- Use professional but plain language — avoid jargon.\n"
        "- Cite actual numbers (rounded to 2 d.p.) to support every point.\n"
        "- 3–5 sentences per section.\n"
        "- Do NOT reproduce raw tables — synthesise into narrative.\n"
        "- Total length: 400–600 words.\n"
        "- Use section headings in **bold** (markdown).\n"
    )

    messages = [
        {
            "role": "user",
            "content": (
                f"Here is the portfolio data for the report:\n\n{data_text}\n\n"
                "Please write the analyst summary."
            ),
        }
    ]

    reply = ollama.chat(messages, system_prompt=system)

    if reply.startswith("Error"):
        return ReportSummaryResponse(summary="", error=reply)
    return ReportSummaryResponse(summary=reply)


# ─── Action endpoints ─────────────────────────────────────────────────────────

@router.post("/action/plan", response_model=ActionPlan)
def ai_action_plan(request: ActionRequest, db: Session = Depends(get_db)):
    """Parse a natural-language modification request into a structured action plan."""
    accounts = [{"id": a.id, "name": a.name, "base_currency": a.base_currency}
                for a in db.query(Account).all()]
    positions = [
        {"id": p.id, "symbol": p.symbol,
         "category": p.category.value if hasattr(p.category, "value") else str(p.category),
         "quantity": p.quantity, "account_id": p.account_id}
        for p in db.query(Position).all()
    ]
    plan = ollama.plan_action(request.message, accounts, positions)
    return ActionPlan(
        action=plan.get("action", "none"),
        description=plan.get("description", ""),
        params=plan.get("params", {}),
    )


@router.post("/action/execute", response_model=ExecuteActionResponse)
def ai_action_execute(request: ExecuteActionRequest, db: Session = Depends(get_db)):
    """Execute a confirmed action plan against the database."""
    from datetime import date
    action = request.action
    p = request.params

    try:
        if action == "add_position":
            acct = db.query(Account).filter(Account.id == p["account_id"]).first()
            if not acct:
                return ExecuteActionResponse(success=False, message=f"Account id={p['account_id']} not found.")
            pos = Position(
                account_id=p["account_id"],
                symbol=str(p["symbol"]).upper(),
                category=CategoryEnum(p["category"]),
                quantity=float(p["quantity"]),
                cost_per_share=float(p["cost_per_share"]),
                currency=str(p.get("currency", acct.base_currency)).upper(),
                date_added=date.fromisoformat(p.get("date_added", date.today().isoformat())),
                yield_rate=float(p["yield_rate"]) if p.get("yield_rate") else None,
            )
            db.add(pos)
            db.commit()
            return ExecuteActionResponse(success=True,
                message=f"Added {p['quantity']} × {p['symbol']} to {acct.name}.")

        elif action == "delete_position":
            symbol = str(p["symbol"]).upper()
            q = db.query(Position).filter(Position.symbol == symbol)
            if p.get("account_id"):
                q = q.filter(Position.account_id == p["account_id"])
            deleted = q.count()
            q.delete()
            db.commit()
            return ExecuteActionResponse(success=True,
                message=f"Deleted {deleted} position(s) for {symbol}.")

        elif action == "record_cash":
            acct = db.query(Account).filter(Account.id == p["account_id"]).first()
            if not acct:
                return ExecuteActionResponse(success=False, message=f"Account id={p['account_id']} not found.")
            amount = float(p["amount"])
            is_withdraw = str(p.get("type", "deposit")).lower() == "withdraw"
            pos = Position(
                account_id=p["account_id"],
                symbol="CASH",
                category=CategoryEnum.Cash,
                quantity=-amount if is_withdraw else amount,
                cost_per_share=1.0,
                currency=acct.base_currency,
                date_added=date.fromisoformat(p.get("date", date.today().isoformat())),
            )
            db.add(pos)
            db.commit()
            verb = "Withdrew" if is_withdraw else "Deposited"
            return ExecuteActionResponse(success=True,
                message=f"{verb} {acct.base_currency} {amount:,.2f} {'from' if is_withdraw else 'into'} {acct.name}.")

        elif action == "record_dividend":
            acct = db.query(Account).filter(Account.id == p["account_id"]).first()
            if not acct:
                return ExecuteActionResponse(success=False, message=f"Account id={p['account_id']} not found.")
            pos = Position(
                account_id=p["account_id"],
                symbol=str(p["symbol"]).upper(),
                category=CategoryEnum.Dividend,
                quantity=float(p["amount"]),
                cost_per_share=1.0,
                currency=acct.base_currency,
                date_added=date.fromisoformat(p.get("date", date.today().isoformat())),
            )
            db.add(pos)
            db.commit()
            return ExecuteActionResponse(success=True,
                message=f"Recorded {acct.base_currency} {p['amount']:,.2f} dividend from {p['symbol']} in {acct.name}.")

        elif action == "update_position":
            def _apply_updates(pos: Position) -> None:
                if "quantity" in p and p["quantity"] is not None:
                    pos.quantity = float(p["quantity"])
                if "cost_per_share" in p and p["cost_per_share"] is not None:
                    pos.cost_per_share = float(p["cost_per_share"])
                if "currency" in p and p["currency"] is not None:
                    pos.currency = str(p["currency"]).upper()
                if "yield_rate" in p:
                    pos.yield_rate = float(p["yield_rate"]) if p["yield_rate"] is not None else None
                if "date_added" in p and p["date_added"]:
                    pos.date_added = date.fromisoformat(p["date_added"])

            symbol_raw = p.get("symbol")
            is_bulk = (
                not p.get("position_id")
                and (not symbol_raw or str(symbol_raw).lower() in ("all", "*", ""))
            )

            if is_bulk:
                q = db.query(Position)
                if p.get("account_id"):
                    q = q.filter(Position.account_id == int(p["account_id"]))
                all_positions = q.all()
                if not all_positions:
                    return ExecuteActionResponse(success=False, message="No positions found.")
                for pos in all_positions:
                    _apply_updates(pos)
                db.commit()
                return ExecuteActionResponse(success=True,
                    message=f"Updated {len(all_positions)} position(s).")

            pos = None
            if p.get("position_id"):
                pos = db.query(Position).filter(Position.id == int(p["position_id"])).first()
            if pos is None and symbol_raw:
                symbol = str(symbol_raw).upper()
                q = db.query(Position).filter(Position.symbol == symbol)
                if p.get("account_id"):
                    q = q.filter(Position.account_id == int(p["account_id"]))
                pos = q.first()
            if not pos:
                return ExecuteActionResponse(success=False, message="Position not found.")
            _apply_updates(pos)
            db.commit()
            return ExecuteActionResponse(success=True,
                message=f"Updated position {pos.symbol} (id={pos.id}).")

        elif action == "create_account":
            acct = Account(
                name=str(p["name"]),
                base_currency=str(p.get("base_currency", "CAD")).upper(),
            )
            db.add(acct)
            db.commit()
            db.refresh(acct)
            return ExecuteActionResponse(success=True,
                message=f"Created account '{acct.name}' ({acct.base_currency}), id={acct.id}.")

        elif action == "update_account":
            acct = db.query(Account).filter(Account.id == int(p["account_id"])).first()
            if not acct:
                return ExecuteActionResponse(success=False, message=f"Account id={p['account_id']} not found.")
            if p.get("name"):
                acct.name = str(p["name"])
            if p.get("base_currency"):
                acct.base_currency = str(p["base_currency"]).upper()
            db.commit()
            return ExecuteActionResponse(success=True,
                message=f"Updated account to '{acct.name}' ({acct.base_currency}).")

        elif action == "delete_account":
            acct = db.query(Account).filter(Account.id == int(p["account_id"])).first()
            if not acct:
                return ExecuteActionResponse(success=False, message=f"Account id={p['account_id']} not found.")
            name = acct.name
            db.delete(acct)
            db.commit()
            return ExecuteActionResponse(success=True,
                message=f"Deleted account '{name}' and all its positions.")

        elif action == "refresh_market_data":
            from app.services.scheduler import sync_market_data
            sync_market_data()
            return ExecuteActionResponse(success=True, message="Market data refreshed for all symbols.")

        else:
            return ExecuteActionResponse(success=False, message=f"Unknown action: {action}")

    except Exception as exc:
        logger.error("Action execute error: %s", exc)
        db.rollback()
        return ExecuteActionResponse(success=False, message=f"Execution failed: {exc}")
