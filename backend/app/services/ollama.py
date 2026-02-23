import os
import re
import json
import logging
import requests
from datetime import date as _date
from typing import Optional

logger = logging.getLogger(__name__)

# ── Live config ───────────────────────────────────────────────────────────────
# All values are strings (stored in SQLite Setting rows).
_config: dict[str, str] = {
    # Active provider: "ollama" | "lmstudio" | "gemini" | "claude"
    "provider":            os.getenv("AI_PROVIDER",           "ollama"),

    # Ollama
    "base_url":            os.getenv("OLLAMA_BASE_URL",       "http://192.168.0.117:11434"),
    "model":               os.getenv("OLLAMA_MODEL",          "glm-4.7-flash:latest"),
    "code_model":          os.getenv("OLLAMA_CODE_MODEL",     "qwen3-coder-next:latest"),

    # LM Studio (OpenAI-compatible)
    "lmstudio_base_url":   os.getenv("LMSTUDIO_BASE_URL",    "http://localhost:1234/v1"),
    "lmstudio_model":      os.getenv("LMSTUDIO_MODEL",        ""),
    "lmstudio_code_model": os.getenv("LMSTUDIO_CODE_MODEL",   ""),

    # Google Gemini (via OpenAI-compatible endpoint)
    "gemini_api_key":      os.getenv("GEMINI_API_KEY",        ""),
    "gemini_model":        os.getenv("GEMINI_MODEL",          "gemini-2.0-flash"),
    "gemini_code_model":   os.getenv("GEMINI_CODE_MODEL",     "gemini-2.0-flash"),

    # Anthropic Claude
    "claude_api_key":      os.getenv("CLAUDE_API_KEY",        ""),
    "claude_model":        os.getenv("CLAUDE_MODEL",          "claude-3-5-haiku-20241022"),
    "claude_code_model":   os.getenv("CLAUDE_CODE_MODEL",     "claude-3-5-haiku-20241022"),
}


def _sync_active_models() -> None:
    """Keep _config['model'] and _config['code_model'] aliased to the active provider."""
    provider = _config["provider"]
    if provider == "lmstudio":
        _config["model"]      = _config["lmstudio_model"] or "local-model"
        _config["code_model"] = _config["lmstudio_code_model"] or _config["lmstudio_model"] or "local-model"
    elif provider == "gemini":
        _config["model"]      = _config["gemini_model"]
        _config["code_model"] = _config["gemini_code_model"]
    elif provider == "claude":
        _config["model"]      = _config["claude_model"]
        _config["code_model"] = _config["claude_code_model"]
    # ollama: model/code_model are already set correctly


def update_config(
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    code_model: Optional[str] = None,
    lmstudio_base_url: Optional[str] = None,
    lmstudio_model: Optional[str] = None,
    lmstudio_code_model: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    gemini_model: Optional[str] = None,
    gemini_code_model: Optional[str] = None,
    claude_api_key: Optional[str] = None,
    claude_model: Optional[str] = None,
    claude_code_model: Optional[str] = None,
) -> None:
    """Update the live AI configuration (call from settings router or init_db)."""
    updates = {
        "provider":            provider,
        "base_url":            base_url,
        "model":               model,
        "code_model":          code_model,
        "lmstudio_base_url":   lmstudio_base_url,
        "lmstudio_model":      lmstudio_model,
        "lmstudio_code_model": lmstudio_code_model,
        "gemini_api_key":      gemini_api_key,
        "gemini_model":        gemini_model,
        "gemini_code_model":   gemini_code_model,
        "claude_api_key":      claude_api_key,
        "claude_model":        claude_model,
        "claude_code_model":   claude_code_model,
    }
    for key, value in updates.items():
        if value is not None:
            _config[key] = value
    _sync_active_models()


# ── Provider implementations ──────────────────────────────────────────────────

def _chat_ollama(messages: list[dict], model: str) -> str:
    url = f"{_config['base_url']}/api/chat"
    payload = {"model": model, "stream": False, "messages": messages}
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "")
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Ollama. Make sure Ollama is running on your host machine."
    except requests.exceptions.Timeout:
        return "Error: Ollama request timed out. The model may be loading — please try again."
    except Exception as exc:
        logger.error("Ollama chat error: %s", exc)
        return f"Error communicating with Ollama: {exc}"


def _chat_openai_compat(
    messages: list[dict],
    model: str,
    base_url: str,
    api_key: str = "",
) -> str:
    """OpenAI-compatible endpoint — handles LM Studio and Gemini."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "stream": False, "messages": messages}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.ConnectionError:
        return f"Error: Cannot connect to {base_url}. Check the URL and make sure the service is running."
    except requests.exceptions.Timeout:
        return "Error: Request timed out. The model may be loading — please try again."
    except Exception as exc:
        logger.error("OpenAI-compat chat error (%s): %s", base_url, exc)
        return f"Error: {exc}"


def _chat_claude(messages: list[dict], model: str, api_key: str) -> str:
    """Anthropic Claude via direct REST API (no SDK required)."""
    if not api_key:
        return "Error: Claude API key is not configured. Please add it in AI Settings."

    # Claude keeps system prompt as a top-level field, not a message role
    system_content = ""
    conv_messages: list[dict] = []
    for m in messages:
        if m["role"] == "system":
            system_content = m["content"]
        else:
            conv_messages.append({"role": m["role"], "content": m["content"]})

    if not conv_messages:
        return ""

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload: dict = {
        "model": model,
        "max_tokens": 4096,
        "messages": conv_messages,
    }
    if system_content:
        payload["system"] = system_content

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers=headers,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Anthropic API. Check your internet connection."
    except requests.exceptions.Timeout:
        return "Error: Anthropic API request timed out. Please try again."
    except Exception as exc:
        logger.error("Claude chat error: %s", exc)
        return f"Error communicating with Claude: {exc}"


# ── Public chat interface ─────────────────────────────────────────────────────

def chat(
    messages: list[dict],
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Send a chat request to the configured AI provider and return the reply."""
    provider = _config["provider"]
    m = model or _config["model"]

    full_messages = messages
    if system_prompt:
        full_messages = [{"role": "system", "content": system_prompt}] + messages

    if provider == "ollama":
        return _chat_ollama(full_messages, m)

    elif provider == "lmstudio":
        return _chat_openai_compat(full_messages, m, _config["lmstudio_base_url"])

    elif provider == "gemini":
        return _chat_openai_compat(
            full_messages, m,
            "https://generativelanguage.googleapis.com/v1beta/openai",
            _config["gemini_api_key"],
        )

    elif provider == "claude":
        return _chat_claude(full_messages, m, _config["claude_api_key"])

    else:
        return f"Error: Unknown AI provider '{provider}'. Please check AI Settings."


# ── Schema description shared by all prompts ─────────────────────────────────

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


def generate_sql_for_question(messages: list[dict]) -> str:
    """
    Use the code model to turn a natural-language portfolio question into
    a SQLite SELECT query.  Accepts the full conversation history so that
    follow-up questions (e.g. "and for AAPL?") resolve correctly.
    Returns raw text (may be fenced or bare SQL).
    """
    system = f"""You are a SQLite expert for an investment portfolio database.
Given a conversation, output ONLY the SQLite SELECT query that answers the LAST user message.
Use earlier messages in the conversation as context to resolve references like "it", "that symbol", "the same account", etc.

{SCHEMA_DESCRIPTION}

STRICT RULES:
- Output raw SQL only — no markdown fences, no explanation, no comments.
- Only SELECT is allowed (no INSERT/UPDATE/DELETE/DROP etc.).
- Always use MAX(timestamp) + GROUP BY to get the latest row from market_data and fx_rates.
- Column and table names must exactly match the schema above.
"""
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
