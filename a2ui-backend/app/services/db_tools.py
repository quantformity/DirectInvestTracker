"""
Database tools for the agentic LLM loop.

Exposes read-only access to the investments SQLite database via three tools:
  - get_db_schema       — table definitions (column names, types, PKs)
  - get_sample_data     — 1-2 sample rows from a table
  - execute_query       — run a SELECT-only SQL query

All connections use SQLite URI mode with ?mode=ro to prevent any writes.
"""
import json
import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Reuse the same DB path resolution as config.py
_DB_PATH = os.getenv(
    "DATABASE_URL",
    str(Path(__file__).parent.parent.parent.parent / "backend" / "data" / "investments.db"),
)
if _DB_PATH.startswith("sqlite:///"):
    _DB_PATH = _DB_PATH[len("sqlite:///"):]

# Tables to hide from the LLM (internal / no user value)
_EXCLUDED_TABLES = {"surface_history", "sqlite_sequence", "settings"}

# Maximum rows execute_query may return
_MAX_ROWS = 500


def _connect() -> sqlite3.Connection:
    """Open a read-only connection to the investments database."""
    conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ── Tool implementations ──────────────────────────────────────────────────────

def get_db_schema() -> dict[str, Any]:
    """
    Return schema for all user-facing tables: column names, types, nullable,
    and primary key flags. Call this first to understand what data is available
    before writing queries.
    """
    try:
        conn = _connect()
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            if row[0] not in _EXCLUDED_TABLES
        ]
        schema: dict[str, list[dict]] = {}
        for table in tables:
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            schema[table] = [
                {
                    "name": row[1],
                    "type": row[2],
                    "not_null": bool(row[3]),
                    "pk": bool(row[5]),
                }
                for row in cols
            ]
        conn.close()
        return {"tables": schema}
    except Exception as exc:
        logger.error("get_db_schema error: %s", exc)
        return {"error": str(exc)}


def get_sample_data(table_name: str, limit: int = 2) -> dict[str, Any]:
    """
    Return up to `limit` sample rows from a table so the LLM can see real
    field names and value formats before building a query.
    """
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
        return {"error": f"Invalid table name: {table_name!r}"}
    if table_name in _EXCLUDED_TABLES:
        return {"error": f"Table not accessible: {table_name!r}"}

    limit = max(1, min(limit, 5))
    try:
        conn = _connect()
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        if not exists:
            conn.close()
            return {"error": f"Table not found: {table_name!r}"}

        rows = conn.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,)).fetchall()
        conn.close()
        return {"table": table_name, "rows": [dict(r) for r in rows]}
    except Exception as exc:
        logger.error("get_sample_data error: %s", exc)
        return {"error": str(exc)}


def execute_query(sql: str) -> dict[str, Any]:
    """
    Execute a read-only SELECT query against the portfolio database and return
    the result rows as a list of dicts.  Only SELECT is allowed.
    """
    clean = sql.strip()

    # Must start with SELECT
    if not re.match(r"(?i)^SELECT\b", clean):
        return {"error": "Only SELECT queries are permitted."}

    # Reject DDL / DML keywords as an extra guard
    _FORBIDDEN = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|DETACH|PRAGMA|VACUUM)\b",
        re.IGNORECASE,
    )
    if _FORBIDDEN.search(clean):
        return {"error": "Query contains forbidden keywords."}

    try:
        conn = _connect()
        cursor = conn.execute(clean)
        cols = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(_MAX_ROWS)
        conn.close()
        return {
            "columns": cols,
            "rows": [dict(zip(cols, row)) for row in rows],
            "count": len(rows),
        }
    except Exception as exc:
        logger.error("execute_query error: %s", exc)
        return {"error": str(exc)}


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def execute_tool(name: str, arguments: dict) -> Any:
    """Dispatch a tool call by name and return the result."""
    if name == "get_db_schema":
        return get_db_schema()
    if name == "get_sample_data":
        return get_sample_data(
            table_name=arguments.get("table_name", ""),
            limit=int(arguments.get("limit", 2)),
        )
    if name == "execute_query":
        return execute_query(sql=arguments.get("sql", ""))
    return {"error": f"Unknown tool: {name!r}"}


# ── Tool definitions (OpenAI function-calling format) ─────────────────────────
#
# Used when calling any LLM provider that supports tool/function calling.
# Claude adapter converts these to its own format at call time.

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_db_schema",
            "description": (
                "Returns the schema of all tables in the portfolio database — "
                "column names, types, nullability, and primary keys. "
                "Call this first to understand what data is available before "
                "writing SQL queries."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sample_data",
            "description": (
                "Returns 1–5 sample rows from a named table so you can see "
                "real field names and value formats before building a query."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table, e.g. 'positions', 'accounts'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of rows to return (1–5, default 2)",
                        "default": 2,
                    },
                },
                "required": ["table_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_query",
            "description": (
                "Execute a read-only SQL SELECT query against the portfolio database "
                "and return the result as a list of row objects. "
                "Only SELECT statements are allowed — no INSERT, UPDATE, DELETE, or DDL. "
                "Use this to fetch exact data to embed in an A2UI dataModelUpdate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A valid SQLite SELECT statement",
                    }
                },
                "required": ["sql"],
            },
        },
    },
]
