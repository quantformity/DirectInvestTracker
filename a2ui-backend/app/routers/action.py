"""
POST /action — handles userAction events from the frontend.

When the user interacts with a surface (e.g. clicking a button in SectorMappingEditor),
the frontend sends a userAction. This router:
1. Handles well-known actions (sector.update, sector.reset) directly via CLI tools
2. Forwards unknown actions to the LLM with conversation context
"""
import json
import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas import UserActionRequest
from app.services import llm, skills

logger = logging.getLogger(__name__)
router = APIRouter()

_BACKEND_DIR = Path(__file__).parent.parent.parent.parent / "backend"
_VENV_PYTHON = _BACKEND_DIR / ".venv" / "bin" / "python"
_PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable


def _run_cli(module: str, args: list[str]) -> dict:
    """Run a qfi-* CLI command and return the JSON result."""
    cmd = [_PYTHON, "-m", module] + args + ["--json"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(_BACKEND_DIR),
        )
        if result.returncode == 0:
            return {"ok": True, "data": json.loads(result.stdout)}
        return {"ok": False, "error": result.stderr[:200]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/action")
async def handle_action(request: UserActionRequest):
    """Handle a userAction event from the A2UI frontend."""
    name = request.name
    ctx = request.context

    # ── Well-known direct actions ─────────────────────────────────────────────

    if name == "sector.update":
        symbol = ctx.get("symbol", "")
        sector = ctx.get("sector", "")
        if not symbol or not sector:
            return JSONResponse({"ok": False, "error": "symbol and sector are required"})
        result = _run_cli("cli.qfi_sector", ["update", symbol, sector])
        return JSONResponse(result)

    if name == "sector.reset":
        symbol = ctx.get("symbol", "")
        if not symbol:
            return JSONResponse({"ok": False, "error": "symbol is required"})
        result = _run_cli("cli.qfi_sector", ["delete", symbol])
        return JSONResponse(result)

    if name == "position.delete":
        pos_id = str(ctx.get("id", ""))
        if not pos_id:
            return JSONResponse({"ok": False, "error": "id is required"})
        result = _run_cli("cli.qfi_position", ["delete", pos_id])
        return JSONResponse(result)

    if name == "market.refresh":
        result = _run_cli("cli.qfi_market", ["refresh"])
        return JSONResponse(result)

    if name == "fx.refresh":
        result = _run_cli("cli.qfi_fx", ["refresh"])
        return JSONResponse(result)

    # ── Unknown action: forward to LLM for interpretation ────────────────────
    system_prompt = skills.get_system_prompt()
    messages = [m.model_dump() for m in request.conversation]
    messages.append({
        "role": "user",
        "content": (
            f"The user triggered an action: name='{name}', "
            f"context={json.dumps(ctx)}.\n"
            "Please handle this action and respond with either:\n"
            "- A2UI JSON messages to update the surface, OR\n"
            "- Plain text confirming what you did.\n"
            "If the action requires CLI tools, describe what you did."
        ),
    })

    response_text = llm.chat(messages, system_prompt=system_prompt)

    return JSONResponse({
        "ok": True,
        "action": name,
        "llm_response": response_text,
    })
