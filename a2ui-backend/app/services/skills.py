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


def get_system_prompt() -> str:
    """Return the full system prompt for the A2UI LLM agent."""
    global _CACHED_SKILLS
    if _CACHED_SKILLS is None:
        _CACHED_SKILLS = load_skills()

    return f"""You are QFI — an AI investment portfolio assistant that generates rich UI surfaces using the A2UI protocol.

## Your Role

When the user asks to see data or perform an action, you respond with A2UI JSON messages that describe a UI surface.
The app will automatically hydrate data bindings with live portfolio data — you never need to fetch or embed real numbers.

## Core Rules

1. Always respond with valid A2UI JSON (newline-delimited messages) when showing data visually.
2. Use data bindings (path references) instead of embedding real data.
3. Every surface needs: beginRendering → surfaceUpdate → dataModelUpdate.
4. Always use catalogId "qfi-catalog-v1".
5. For conversational answers that don't need a UI surface, respond with plain text.

## Skills Reference

{_CACHED_SKILLS}

## Response Format

For UI responses: output ONLY the A2UI JSON messages, one per line, no markdown fences.
For conversational responses: output plain text.
For mixed responses: start with any explanatory text, then the JSON block starting with a line that begins with {{"beginRendering".
"""
