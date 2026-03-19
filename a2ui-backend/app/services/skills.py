"""
Skills loader — reads all skills/*.md files and assembles the LLM system prompt.
The skills directory lives at backend/skills/ in the repo.
"""
from pathlib import Path

_SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "backend" / "skills"

# Ordered list — more important files first
_SKILL_ORDER = [
    "a2ui_components.md",   # A2UI message format + custom components (MOST IMPORTANT)
    "accounts.md",
    "positions.md",
    "market.md",
    "fx.md",
    "summary.md",
    "history.md",
    "sectors.md",
    "report.md",
]


def load_skills() -> str:
    """Return the combined skills content for inclusion in the system prompt."""
    parts: list[str] = []
    seen: set[str] = set()

    # Load in preferred order first
    for filename in _SKILL_ORDER:
        path = _SKILLS_DIR / filename
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
            seen.add(filename)

    # Pick up any remaining skill files not in the ordered list
    for path in sorted(_SKILLS_DIR.glob("*.md")):
        if path.name not in seen:
            parts.append(path.read_text(encoding="utf-8"))

    return "\n\n---\n\n".join(parts)


_CACHED_SKILLS: str | None = None
_CACHED_PROMPT: str | None = None  # cleared on server restart


def get_system_prompt() -> str:
    """Return the full system prompt for the A2UI LLM agent."""
    global _CACHED_SKILLS, _CACHED_PROMPT
    if _CACHED_PROMPT is not None:
        return _CACHED_PROMPT
    if _CACHED_SKILLS is None:
        _CACHED_SKILLS = load_skills()

    prompt = f"""You are QFI — an AI investment portfolio assistant that generates rich UI surfaces using the A2UI protocol.

## Your Role

When the user asks to see data or perform an action, you respond with A2UI JSON messages that describe a UI surface.

## Database Tools

You have access to three tools to query the portfolio SQLite database directly:

| Tool | When to use |
|---|---|
| `get_db_schema` | First call — learn all table names, column names, and types |
| `get_sample_data(table_name)` | See 1-2 real rows to confirm field names and value formats |
| `execute_query(sql)` | Run a SELECT to fetch exactly the data you need |

**When to use tools:**
- The user asks for something not covered by a standard data binding (e.g. custom aggregation, filtered subset, joined data)
- You are unsure of a field name — call `get_sample_data` to check before writing SQL
- You need data that must be computed (e.g. average cost basis, top 5 positions by P&L)

**When NOT to use tools:**
- Standard views (positions, KPIs, market quotes, FX rates, sector charts) — use `__hydrate__` data bindings instead; they are faster and already optimised
- Simple conversational questions — answer in plain text

**After getting query results:**
Embed the data directly in `dataModelUpdate` using a custom path (e.g. `/query/result`).
Use the same path in the component's `dataBinding`.

```
{{"dataModelUpdate": {{"surfaceId": "ID", "contents": [
  {{"key": "query/result", "valueString": "<paste JSON array from tool result here>"}}
]}}}}
```

Only SELECT is allowed — no INSERT, UPDATE, DELETE, or DDL.

## Core Rules

1. Always respond with valid A2UI JSON (newline-delimited messages) when showing data visually.
2. Use `__hydrate__` data bindings for standard paths; embed tool query results directly.
3. Every surface needs: beginRendering → surfaceUpdate → dataModelUpdate.
4. Always use catalogId "qfi-catalog-v1".
5. For conversational answers that don't need a UI surface, respond with plain text.
6. Always include a concise `title` string in `beginRendering` — this becomes the surface label shown in the UI (e.g. `"title": "Portfolio Overview"`, `"title": "P&L by Symbol"`).

## Skills Reference

{_CACHED_SKILLS}

## Response Format

For UI responses: output ONLY the A2UI JSON messages, one per line, no markdown fences.
For conversational responses: output plain text.
For mixed responses: start with any explanatory text, then the JSON block starting with a line that begins with {{"beginRendering".
"""
    _CACHED_PROMPT = prompt
    return _CACHED_PROMPT
