import os
import re
import json
import logging
import requests
from datetime import date as _date
from typing import Optional

logger = logging.getLogger(__name__)

_config: dict[str, str] = {
    "base_url":   os.getenv("OLLAMA_BASE_URL",    "http://192.168.0.117:11434"),
    "model":      os.getenv("OLLAMA_MODEL",       "glm-4.7-flash:latest"),
    "code_model": os.getenv("OLLAMA_CODE_MODEL",  "qwen3-coder-next:latest"),
}


def update_config(
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    code_model: Optional[str] = None,
) -> None:
    """Update the live Ollama configuration (call from settings router or init_db)."""
    if base_url is not None:
        _config["base_url"] = base_url
    if model is not None:
        _config["model"] = model
    if code_model is not None:
        _config["code_model"] = code_model

SCHEMA_DESCRIPTION = """
You have access to an SQLite investment portfolio database with the following tables:

TABLE: accounts
  - id INTEGER PRIMARY KEY
  - name TEXT (account name, e.g. "TFSA", "RRSP")
  - base_currency TEXT (e.g. "CAD", "USD")

TABLE: positions
  - id INTEGER PRIMARY KEY
  - account_id INTEGER (FK → accounts.id)
  - symbol TEXT (Yahoo Finance symbol for equities, e.g. "AAPL", "TD.TO"; descriptive for GIC/Cash)
  - category TEXT (one of: 'Equity', 'GIC', 'Cash', 'Dividend')
  - quantity REAL (number of shares or principal amount for GIC/Cash)
  - cost_per_share REAL (purchase price per share; 1.0 for Cash/GIC)
  - date_added DATE (purchase date)
  - yield_rate REAL (annual yield for GICs, e.g. 0.045 for 4.5%; NULL for equities)

TABLE: market_data
  - id INTEGER PRIMARY KEY
  - symbol TEXT
  - last_price REAL (latest market price)
  - pe_ratio REAL
  - change_percent REAL (daily % change)
  - beta REAL
  - timestamp DATETIME (UTC)

TABLE: fx_rates
  - id INTEGER PRIMARY KEY
  - pair TEXT (format: "FROM/TO", e.g. "USD/CAD")
  - rate REAL
  - timestamp DATETIME (UTC)

RELATIONSHIPS:
- positions.account_id → accounts.id
- Use MAX(timestamp) GROUP BY symbol to get latest market_data
- Use MAX(timestamp) GROUP BY pair to get latest fx_rates

COMPUTED NOTES:
- MTM (equities) = market_data.last_price × positions.quantity
- PnL (equities) = (market_data.last_price - positions.cost_per_share) × positions.quantity
- GIC accrued value = cost_per_share × (1 + yield_rate × days_since_purchase / 365)
- Reporting currency conversion: multiply local MTM by the appropriate fx_rate
"""


def build_system_prompt(extra_context: str = "") -> str:
    data_section = ""
    if extra_context:
        data_section = f"""
=== LIVE PORTFOLIO DATA (use this to answer ALL questions) ===
{extra_context}
=== END OF PORTFOLIO DATA ===
"""
    return f"""You are a personal investment portfolio assistant.

{data_section}
{SCHEMA_DESCRIPTION}

BEHAVIOUR RULES:
- Answer questions about positions, PnL, accounts, prices and FX rates by computing directly from the portfolio data provided above. Do NOT generate SQL for general questions.
- Compute equity PnL = (current_price - cost_per_share) × quantity.
- Only output a SQL SELECT statement when the user explicitly asks for a "SQL query".
- Only output a Python code block when the user explicitly asks for a "chart" or "plot".
- Be concise and direct. Round numbers to 2 decimal places.
"""


def chat(
    messages: list[dict],
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Send a chat request to Ollama and return the assistant's reply.
    """
    url = f"{_config['base_url']}/api/chat"
    model = model or _config["model"]

    full_messages = messages
    if system_prompt:
        full_messages = [{"role": "system", "content": system_prompt}] + messages

    payload = {
        "model": model,
        "stream": False,
        "messages": full_messages,
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Ollama. Make sure Ollama is running on your host machine."
    except requests.exceptions.Timeout:
        return "Error: Ollama request timed out. The model may be loading — please try again."
    except Exception as exc:
        logger.error("Ollama chat error: %s", exc)
        return f"Error communicating with Ollama: {exc}"


def plan_action(user_message: str, accounts: list[dict], positions: list[dict] | None = None) -> dict:
    """
    Ask the LLM to parse a natural language data-modification request and
    return a structured action plan as a dict.
    Returns {"action": "none"} if the message is not an action request.
    """
    today = _date.today().isoformat()
    accounts_list = "\n".join(
        f"  id={a['id']}: {a['name']} ({a['base_currency']})" for a in accounts
    )
    positions_list = ""
    if positions:
        positions_list = "\nCURRENT POSITIONS (for reference):\n" + "\n".join(
            f"  id={p['id']}: {p['symbol']} | {p['category']} | qty={p['quantity']} "
            f"| account_id={p['account_id']}"
            for p in positions[:60]  # cap to keep prompt lean
        )
    system = f"""You are a portfolio data-entry assistant. Today's date is {today}.

AVAILABLE ACCOUNTS:
{accounts_list}
{positions_list}

{SCHEMA_DESCRIPTION}

Your ONLY job is to interpret data modification requests and return a JSON action plan.

SUPPORTED ACTIONS AND THEIR PARAMS:

add_position — add an equity, GIC, cash or dividend position
  params: account_id (int), symbol (str), category ("Equity"|"GIC"|"Cash"|"Dividend"),
          quantity (float), cost_per_share (float), currency (str, e.g. "USD"),
          date_added (str "YYYY-MM-DD"), yield_rate (float, GIC only)

delete_position — remove position(s) by symbol
  params: symbol (str), account_id (int or null for all accounts)

update_position — change fields of an existing position
  params: symbol (str or null), account_id (int or null), position_id (int, preferred if known),
          quantity (float, optional), cost_per_share (float, optional),
          currency (str, optional), yield_rate (float, optional),
          date_added (str "YYYY-MM-DD", optional)
  Note: if the user says "all positions" or does not name a specific symbol, set symbol=null
        and position_id=null — this will update EVERY position (optionally filtered by account_id).

record_cash — deposit or withdraw cash
  params: account_id (int), amount (float, always positive), type ("deposit"|"withdraw"),
          date (str "YYYY-MM-DD")

record_dividend — record a dividend payment received
  params: account_id (int), symbol (str, the stock that paid it), amount (float),
          date (str "YYYY-MM-DD")

create_account — create a new investment account
  params: name (str), base_currency (str, e.g. "CAD", "USD")

update_account — rename or change base currency of an existing account
  params: account_id (int), name (str, optional), base_currency (str, optional)

delete_account — permanently delete an account and all its positions
  params: account_id (int)

refresh_market_data — refresh live prices for all tracked symbols
  params: {{}}

OUTPUT RULES:
- Return ONLY raw JSON — no markdown fences, no explanation.
- For a valid action: {{"action": "<type>", "description": "<clear human summary>", "params": {{...}}}}
- If the request is NOT a data modification: {{"action": "none"}}
- Match account names case-insensitively. If ambiguous, pick the most likely one.
- Default currency to the account's base_currency if not specified.
- Use today's date ({today}) if no date is mentioned.
"""
    messages = [{"role": "user", "content": user_message}]
    raw = chat(messages, system_prompt=system, model=_config["model"])

    # Extract JSON from LLM output (model may wrap in markdown despite instructions)
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {"action": "none"}


def generate_sql_for_question(question: str) -> str:
    """
    Use the code model to turn a natural-language portfolio question into
    a SQLite SELECT query.  Returns raw text (may be fenced or bare SQL).
    """
    system = f"""You are a SQLite expert for an investment portfolio database.
Given a natural-language question, output ONLY the SQLite SELECT query that answers it.

{SCHEMA_DESCRIPTION}

STRICT RULES:
- Output raw SQL only — no markdown fences, no explanation, no comments.
- Only SELECT is allowed (no INSERT/UPDATE/DELETE/DROP etc.).
- Always use MAX(timestamp) + GROUP BY to get the latest row from market_data and fx_rates.
- Column and table names must exactly match the schema above.
"""
    messages = [{"role": "user", "content": question}]
    return chat(messages, system_prompt=system, model=_config["code_model"])


def format_sql_results(question: str, sql: str, results: list[dict]) -> str:
    """
    Use the chat model to convert SQL query results into a natural-language answer.
    """
    results_str = json.dumps(results[:50], indent=2, default=str)  # cap at 50 rows
    system = (
        "You are a helpful investment portfolio assistant. "
        "Given a user question, the SQL that was run, and the results, "
        "provide a clear, concise answer. Show numbers with 2 decimal places. "
        "Do not repeat the SQL or JSON verbatim — just answer the question."
    )
    content = (
        f"Question: {question}\n\n"
        f"SQL executed:\n{sql}\n\n"
        f"Results:\n{results_str}"
    )
    messages = [{"role": "user", "content": content}]
    return chat(messages, system_prompt=system, model=_config["model"])


def generate_sql_or_code(prompt: str, model: Optional[str] = None) -> str:
    """
    Ask the LLM to generate either a SQL query or a Python plotting snippet.
    Returns the raw LLM output.
    """
    system = build_system_prompt() + """
INSTRUCTIONS FOR THIS REQUEST:
- If the user asks for data/table/list → output ONLY a valid SQLite SELECT query.
  Start the SQL block with: ```sql
  End it with: ```
- If the user asks for a chart/plot/graph/visualization → output ONLY a Python code snippet.
  The snippet has access to: `db_session` (SQLAlchemy session), `plt` (matplotlib.pyplot),
  `go` (plotly.graph_objects), `pd` (pandas), `json` (json module).
  Save matplotlib figures to variable `fig` (plt.Figure) OR set `plotly_json` (str).
  Start the Python block with: ```python
  End it with: ```
- Do NOT output explanations, only the code block.
"""
    messages = [{"role": "user", "content": prompt}]
    return chat(messages, system_prompt=system, model=model or _config["code_model"])
