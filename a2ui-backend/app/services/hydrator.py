"""
Hydrator — maps A2UI dataModelUpdate paths to qfi-* CLI tool calls.

For each path the LLM declares in a dataModelUpdate, this service runs
the appropriate CLI command and returns the real data.
"""
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path to the backend directory (one level up from this app's root)
_BACKEND_DIR = Path(__file__).parent.parent.parent.parent / "backend"
_CLI_DIR = _BACKEND_DIR / "cli"
_VENV_PYTHON = _BACKEND_DIR / ".venv" / "bin" / "python"

# Fallback to system python if venv not available
_PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable


def _run_cli(module: str, args: list[str]) -> Any:
    """Run a qfi-* CLI command and return parsed JSON output."""
    cmd = [_PYTHON, "-m", module] + args + ["--json"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_BACKEND_DIR),
        )
        if result.returncode != 0:
            logger.warning("CLI %s failed: %s", module, result.stderr[:200])
            return None
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        logger.error("CLI %s timed out", module)
        return None
    except json.JSONDecodeError as exc:
        logger.error("CLI %s returned non-JSON: %s", module, exc)
        return None
    except Exception as exc:
        logger.error("CLI %s error: %s", module, exc)
        return None


# ── Path → CLI mapping ────────────────────────────────────────────────────────
#
# Keys are the data model paths used in components' dataBinding.
# Values are callables that return the hydrated data (or None on failure).

def _hydrate_positions_rows() -> Any:
    return _run_cli("cli.qfi_position", ["list"])


def _hydrate_portfolio_kpi() -> Any:
    data = _run_cli("cli.qfi_summary", ["show"])
    if data is None:
        return None
    # Transform summary totals into 4-KPI structure
    if isinstance(data, dict):
        return {
            "total_mtm": data.get("total_mtm_reporting", 0),
            "total_pnl": data.get("total_pnl_reporting", 0),
            "total_pnl_pct": data.get("total_pnl_pct", 0),
            "account_count": data.get("account_count", 0),
            "position_count": data.get("position_count", 0),
            "currency": data.get("reporting_currency", "CAD"),
        }
    return data


def _hydrate_chart_points() -> Any:
    return _run_cli("cli.qfi_history", ["portfolio"])


def _hydrate_chart_slices() -> Any:
    return _run_cli("cli.qfi_summary", ["show", "--group-by", "sector"])


def _hydrate_chart_bars() -> Any:
    return _run_cli("cli.qfi_summary", ["show", "--group-by", "sector"])


def _hydrate_market_quotes() -> Any:
    return _run_cli("cli.qfi_market", ["quote-list"])


def _hydrate_fx_rates() -> Any:
    return _run_cli("cli.qfi_fx", ["list"])


def _hydrate_sector_mappings() -> Any:
    return _run_cli("cli.qfi_sector", ["list"])


def _hydrate_accounts_list() -> Any:
    return _run_cli("cli.qfi_account", ["list"])


def _hydrate_accounts_mtm() -> Any:
    return _run_cli("cli.qfi_account", ["mtm"])


_PATH_MAP: dict[str, Any] = {
    "positions/rows":  _hydrate_positions_rows,
    "portfolio/kpi":   _hydrate_portfolio_kpi,
    "chart/points":    _hydrate_chart_points,
    "chart/slices":    _hydrate_chart_slices,
    "chart/bars":      _hydrate_chart_bars,
    "market/quotes":   _hydrate_market_quotes,
    "fx/rates":        _hydrate_fx_rates,
    "sector/mappings": _hydrate_sector_mappings,
    "accounts/list":   _hydrate_accounts_list,
    "accounts/mtm":    _hydrate_accounts_mtm,
}


def hydrate(path: str) -> Any:
    """
    Given a data model path (e.g. "positions/rows"), run the appropriate CLI
    command and return the real data.  Returns None if the path is unknown or
    the CLI call fails.
    """
    # Strip leading slash
    clean = path.lstrip("/")
    fn = _PATH_MAP.get(clean)
    if fn is None:
        logger.warning("No hydrator for path: %s", path)
        return None
    return fn()


def hydrate_all(paths: list[str]) -> dict[str, Any]:
    """Hydrate a list of paths and return a dict of path → data."""
    result: dict[str, Any] = {}
    for path in paths:
        data = hydrate(path)
        if data is not None:
            result[path.lstrip("/")] = data
        else:
            result[path.lstrip("/")] = []
    return result
