# Implementation Plan — QFI CLI Tools + A2UI App

## Overview

This plan covers two deliverables built on top of the existing investment tracker:

1. **QFI CLI Tools** — eight standalone command-line tools (`qfi-account`, `qfi-position`, etc.) that serve as the canonical data layer, callable by both humans and the A2UI agent.
2. **A2UI App** — a new Electron application with an AI-centred three-panel layout (surface history | on-demand UI | chat), implementing the full feature set of the existing app via Google's A2UI protocol.

The existing app (`backend/` + `frontend/`) is **not modified**.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Shared Database                          │
│                   SQLite: data/investments.db                   │
└──────────────┬──────────────────────────────┬───────────────────┘
               │                              │
   ┌───────────▼──────────┐      ┌────────────▼──────────────────┐
   │   Existing App        │      │       QFI CLI Tools           │
   │  FastAPI :8000        │      │  qfi-account, qfi-position,   │
   │  Electron (existing)  │      │  qfi-market, qfi-fx,          │
   └──────────────────────┘      │  qfi-history, qfi-summary,    │
                                  │  qfi-sector, qfi-report        │
                                  └────────────┬──────────────────┘
                                               │ subprocess --json
                                  ┌────────────▼──────────────────┐
                                  │       A2UI Backend             │
                                  │  New FastAPI :8001             │
                                  │  - LLM bridge (Ollama/Gemini/  │
                                  │    Claude, same config)        │
                                  │  - A2UI message generation     │
                                  │  - Data hydration via CLI      │
                                  └────────────┬──────────────────┘
                                               │
                                  ┌────────────▼──────────────────┐
                                  │       A2UI Frontend            │
                                  │  New Electron App              │
                                  │  ┌──────────┬────────┬───────┐│
                                  │  │ History  │  UI   │ Chat  ││
                                  │  │ (left)   │(centre)│(right)││
                                  │  └──────────┴────────┴───────┘│
                                  └───────────────────────────────┘
```

### Data Flow for Each Chat Interaction

```
1. User types message in Chat panel
2. A2UI Frontend sends message to A2UI Backend
3. A2UI Backend sends [message + schema + sample data] to LLM
4. LLM responds with A2UI messages (beginRendering + surfaceUpdate)
   - Components reference data via path bindings (e.g. /positions/rows)
   - LLM does NOT receive full portfolio data
5. A2UI Backend intercepts dataModelUpdate paths
6. Backend calls appropriate qfi-* CLI tool with --json to hydrate real data
7. dataModelUpdate messages sent to frontend with real data
8. Frontend A2UI renderer renders surface with live data
9. Surface added to history panel
10. User interactions (Button clicks) send userAction back to backend → LLM
```

---

## Repository Structure (additions only)

```
investments/
├── backend/                        # existing (unchanged)
├── frontend/                       # existing (unchanged)
│
├── cli/
│   ├── lib/
│   │   ├── __init__.py
│   │   ├── db.py                   # shared SQLAlchemy session
│   │   ├── yahoo.py                # shared Yahoo Finance wrapper
│   │   └── output.py              # JSON / human-readable formatter
│   ├── qfi_account.py
│   ├── qfi_position.py
│   ├── qfi_market.py
│   ├── qfi_fx.py
│   ├── qfi_history.py
│   ├── qfi_summary.py
│   ├── qfi_sector.py
│   └── qfi_report.py
│
├── skills/
│   ├── accounts.md
│   ├── positions.md
│   ├── market.md
│   ├── fx.md
│   ├── history.md
│   ├── summary.md
│   ├── sectors.md
│   └── report.md
│
├── tests/
│   └── cli/
│       ├── conftest.py             # in-memory SQLite fixtures, Yahoo mocks
│       ├── test_account.py
│       ├── test_position.py
│       ├── test_market.py
│       ├── test_fx.py
│       ├── test_history.py
│       ├── test_summary.py
│       ├── test_sector.py
│       └── test_report.py
│
├── a2ui-backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point (:8001)
│   │   ├── routers/
│   │   │   ├── chat.py             # POST /chat, SSE stream
│   │   │   ├── action.py           # POST /action (userAction handler)
│   │   │   └── surfaces.py        # GET /surfaces (history)
│   │   ├── services/
│   │   │   ├── llm.py              # Ollama / Gemini / Claude adapter
│   │   │   ├── a2ui.py             # A2UI message parser + builder
│   │   │   ├── hydrator.py         # calls qfi-* tools, fills data model
│   │   │   └── catalog.py         # custom catalog definition
│   │   ├── catalog/
│   │   │   ├── standard_extensions.json   # custom component definitions
│   │   │   └── skills_loader.py   # loads skills/*.md for LLM system prompt
│   │   └── config.py              # LLM + DB config (reads same settings DB)
│   ├── requirements.txt
│   └── .venv/
│
├── a2ui-frontend/
│   ├── electron/
│   │   └── main.cjs
│   ├── src/
│   │   ├── App.tsx                 # three-panel layout
│   │   ├── panels/
│   │   │   ├── ChatPanel.tsx       # right: chat input + message history
│   │   │   ├── SurfacePanel.tsx    # centre: active A2UI surface
│   │   │   └── HistoryPanel.tsx   # left: surface history thumbnails
│   │   ├── renderer/
│   │   │   ├── A2UIRenderer.tsx    # core renderer (walks component tree)
│   │   │   ├── DataModel.ts        # client-side data model store
│   │   │   └── components/
│   │   │       ├── standard/       # Text, Row, Column, Card, Button, etc.
│   │   │       └── custom/
│   │   │           ├── PositionsTable.tsx
│   │   │           ├── LineChart.tsx
│   │   │           ├── PieChart.tsx
│   │   │           └── MarketInsightWidget.tsx
│   │   ├── api/
│   │   │   └── client.ts          # calls a2ui-backend :8001
│   │   └── store/
│   │       └── surfaces.ts        # Zustand: surface list + active surface
│   ├── package.json
│   └── vite.config.ts
│
├── scripts/
│   ├── dev.sh                      # existing
│   └── dev-a2ui.sh                # starts a2ui-backend + a2ui-frontend
│
└── docs/
    ├── database.md
    └── implementation-plan.md      # this file
```

---

## Technology Choices

| Layer | Technology | Reason |
|---|---|---|
| CLI framework | Python + **Typer** | Reuses existing SQLAlchemy models, yfinance service; type-safe CLI |
| CLI tests | **pytest** + in-memory SQLite | Isolated, fast, no real DB needed |
| Yahoo Finance mock | `pytest-mock` / `unittest.mock` | Prevents network calls in tests |
| A2UI backend | **FastAPI** (new instance, port 10201) | Same stack as existing backend; SSE streaming built-in |
| LLM integration | Same Ollama/Gemini/Claude adapters | Reads from shared `settings` table in SQLite |
| A2UI frontend | **React + TypeScript + Vite + Electron** | Same stack as existing frontend |
| State management | **Zustand** | Already a dependency in existing frontend |
| Charts (custom components) | **Recharts** | React charting library; already in existing frontend |
| Tables (custom components) | **TanStack Table** | Headless table library; already in existing frontend |
| A2UI catalog version | **v0.8** | Current stable spec |

> **Recharts** is a React charting library (line charts, pie charts, bar charts).
> **TanStack Table** is a headless table library that handles sorting, filtering, and pagination.
> Both are already installed in the existing frontend — the new app will declare them as dependencies too.

---

## Phase 1 — Shared CLI Library

**Goal:** Foundation used by all 8 CLI tools.

### Files
- `cli/lib/db.py` — SQLAlchemy `SessionLocal` factory pointing to `data/investments.db` (configurable via `DATABASE_URL` env var, same as existing backend)
- `cli/lib/yahoo.py` — thin wrapper re-exporting `fetch_prices`, `fetch_fx_rates_batch` from `backend/app/services/yahoo_finance.py`
- `cli/lib/output.py` — `print_output(data, json_flag)` helper: JSON with `--json`, else pretty-printed table / CSV

### pyproject.toml additions
```toml
[project.scripts]
qfi-account  = "cli.qfi_account:app"
qfi-position = "cli.qfi_position:app"
qfi-market   = "cli.qfi_market:app"
qfi-fx       = "cli.qfi_fx:app"
qfi-history  = "cli.qfi_history:app"
qfi-summary  = "cli.qfi_summary:app"
qfi-sector   = "cli.qfi_sector:app"
qfi-report   = "cli.qfi_report:app"
```

---

## Phase 2 — CLI Tools

**Goal:** Eight standalone binaries, each a Typer app.

### `qfi-account`
```
qfi-account list                               List all accounts
qfi-account add <name> [--currency CAD]        Create account
qfi-account show <id>                          Details + MTM
qfi-account rename <id> <name>                 Rename
qfi-account delete <id>                        Delete + cascade positions
qfi-account mtm [--account-id <id>]            MTM per account
```

### `qfi-position`
```
qfi-position list [--account-id N] [--category equity|gic|cash|dividend]
qfi-position show <id>
qfi-position add <symbol> <qty> <cost>
              --account-id N --category <cat>
              [--currency USD] [--date YYYY-MM-DD] [--yield X]
qfi-position modify <id> [--qty X] [--cost X] [--currency X] [--yield X]
qfi-position delete <id>
qfi-position pnl [--account-id N] [--symbol X]
```

### `qfi-market`
```
qfi-market quote <symbol>
qfi-market quote-list
qfi-market refresh [--symbol X] [--full-history]
qfi-market add <symbol> --price X [--pe X] [--change X] [--beta X] [--name "..."]
qfi-market modify <symbol> [--price X] [--pe X] [--change X] [--beta X]
qfi-market history <symbol> [--from YYYY-MM-DD] [--to YYYY-MM-DD]
```

### `qfi-fx`
```
qfi-fx list
qfi-fx show <pair>
qfi-fx refresh
qfi-fx add <pair> <rate>
qfi-fx modify <pair> <rate>
```

### `qfi-history`
```
qfi-history portfolio [--account-id N] [--from YYYY-MM-DD] [--to YYYY-MM-DD]
qfi-history symbol <symbol> [--from X] [--to X]
qfi-history sector <sector> [--from X] [--to X]
qfi-history account <id> [--from X] [--to X]
```

### `qfi-summary`
```
qfi-summary show [--group-by category|account|symbol|sector|cash_gic]
qfi-summary account <id>
qfi-summary sector [<sector>]
qfi-summary category
```

### `qfi-sector`
```
qfi-sector list
qfi-sector add <symbol> <sector>
qfi-sector update <symbol> <sector>
qfi-sector delete <symbol>
qfi-sector show <sector>
qfi-sector summary
```

### `qfi-report`
```
qfi-report generate [--format json|csv|html]
                    [--account-id N]
                    [--from YYYY-MM-DD] [--to YYYY-MM-DD]
qfi-report positions [--account-id N]
qfi-report pnl [--period 1d|1w|1m|3m|1y|all]
qfi-report sector-breakdown
qfi-report account-breakdown
```

#### HTML Report & LLM Placeholder Strategy

`qfi-report generate --format html` outputs self-contained HTML with data pre-filled and clearly marked placeholder sections:

```html
<div class="llm-narrative"
     data-llm-section="portfolio_overview"
     data-context='{"total_value": 95420.12, "accounts": 3}'>
  <!-- Agent: insert portfolio overview narrative here -->
</div>
```

The A2UI agent:
1. Calls `qfi-report generate --format html`
2. Parses `data-llm-section` elements
3. For each, asks the LLM to write a short narrative using `data-context`
4. Injects the text and displays the final HTML in the A2UI surface

`qfi-report` itself never calls an LLM.

---

## Phase 3 — Skills Documentation

**Goal:** Eight `skills/*.md` files the LLM system prompt loads to understand available tools.

### Standard format per file

```markdown
# <Category> — `qfi-<name>`

## Purpose
One sentence.

## Important
Always use the `--json` flag. Output is JSON.

## Commands

### <command name>
**Usage:** `qfi-<name> <command> [args] --json`
**Returns:** `{ ... schema ... }`
**Example:**
  qfi-account list --json
  → [{"id": 1, "name": "TFSA", "base_currency": "CAD"}, ...]

**Error response:** `{"error": "message"}`
```

### Files to create
`skills/accounts.md`, `skills/positions.md`, `skills/market.md`, `skills/fx.md`,
`skills/history.md`, `skills/summary.md`, `skills/sectors.md`, `skills/report.md`

---

## Phase 4 — Unit Tests

**Goal:** Full pytest coverage for all CLI tools using in-memory SQLite.

### `tests/cli/conftest.py`
```python
@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()

@pytest.fixture
def mock_yahoo(mocker):
    return mocker.patch("cli.lib.yahoo.fetch_prices", return_value={...})
```

### Coverage targets per tool
Each tool must have tests for:
- Happy path (correct output JSON shape)
- Missing required argument (exit code 2)
- Record not found (exit code 1, JSON error)
- `--json` flag produces valid parseable JSON
- Without `--json` flag produces human-readable text

---

## Phase 5 — A2UI Custom Catalog

**Goal:** Define custom components the LLM can request that the frontend renders with Recharts/TanStack.

### `a2ui-backend/catalog/standard_extensions.json`

```json
{
  "catalogId": "qfi-catalog-v1",
  "extends": "a2ui.org/specification/v0_8/standard_catalog_definition.json",
  "components": {
    "PositionsTable": {
      "description": "Sortable table of portfolio positions with P&L columns",
      "dataBinding": "/positions/rows"
    },
    "LineChart": {
      "description": "Time-series line chart",
      "dataBinding": "/chart/series",
      "properties": { "title": {}, "xLabel": {}, "yLabel": {} }
    },
    "PieChart": {
      "description": "Proportional breakdown pie chart",
      "dataBinding": "/chart/slices",
      "properties": { "title": {} }
    },
    "MarketInsightWidget": {
      "description": "Quote card: price, change%, P/E, beta, sector badge",
      "dataBinding": "/market/quotes"
    }
  }
}
```

---

## Phase 6 — A2UI Backend

**Goal:** New FastAPI app (port 8001) that bridges LLM ↔ frontend via A2UI protocol.

### Key endpoints

| Endpoint | Method | Description |
|---|---|---|
| `POST /chat` | SSE stream | User message in → A2UI messages out (streamed) |
| `POST /action` | JSON | Receives `userAction` from frontend → sends to LLM → returns A2UI response |
| `GET /surfaces` | JSON | Returns surface history list |
| `GET /settings` | JSON | Returns current LLM config |
| `POST /settings` | JSON | Updates LLM config (same `settings` table) |

### LLM system prompt construction
```
1. Load all skills/*.md files
2. Load custom catalog definition
3. Load sample data (3 rows from each table)
4. Instruct: "Respond ONLY with A2UI JSON messages.
              Use data binding paths — do not embed real portfolio data.
              Available tools are listed in skills/*.md"
```

### Hydrator service (`services/hydrator.py`)
When the LLM emits a `dataModelUpdate` with a recognisable path (e.g. `/positions/rows`), the hydrator:
1. Maps the path to the appropriate `qfi-*` CLI command
2. Calls the CLI as a subprocess with `--json`
3. Transforms the output to A2UI `dataModelUpdate` contents format
4. Streams the real data to the frontend

### Data path → CLI tool mapping
```python
PATH_MAP = {
    "/positions/rows":     ["qfi-position", "list"],
    "/accounts/list":      ["qfi-account", "list"],
    "/market/quotes":      ["qfi-market", "quote-list"],
    "/summary/data":       ["qfi-summary", "show"],
    "/fx/rates":           ["qfi-fx", "list"],
    "/sector/mappings":    ["qfi-sector", "list"],
    "/history/portfolio":  ["qfi-history", "portfolio"],
    # etc.
}
```

---

## Phase 7 — A2UI Frontend

**Goal:** New Electron app with three-panel layout and A2UI renderer.

### Three-panel layout
```
┌──────────────┬───────────────────────────┬─────────────────┐
│ History      │ Active Surface            │ Chat            │
│ (240px)      │ (flex-1)                  │ (320px)         │
│              │                           │                 │
│ [thumbnail]  │  ┌──────────────────┐     │ [messages]      │
│ Summary      │  │  A2UI Surface    │     │                 │
│ 2 min ago    │  │  (rendered)      │     │ [input box]     │
│              │  └──────────────────┘     │                 │
│ [thumbnail]  │                           │                 │
│ Positions    │                           │                 │
│ 5 min ago    │                           │                 │
└──────────────┴───────────────────────────┴─────────────────┘
```

### A2UI Renderer
- Walks the component tree from the `root` component ID
- Resolves `path` data bindings against the local `DataModel` store
- Dispatches `userAction` events to the backend on button clicks
- Standard components: renders all 16 from v0.8 catalog
- Custom components: delegates to `custom/` folder by component name

### Custom component data flow
```
LLM emits: { "PositionsTable": { "dataBinding": "/positions/rows" } }
Hydrator:  calls qfi-position list --json → fills /positions/rows in data model
Renderer:  <PositionsTable data={dataModel["/positions/rows"]} />
           → renders TanStack Table with sort/filter
```

### Surface history
- Each completed surface stored in Zustand with: `{ id, title, timestamp, snapshot }`
- Clicking a history item re-renders the surface from snapshot (no new LLM call)
- Surfaces persist to `localStorage` in Electron for cross-session history

---

## Phase 8 — Integration & Dev Script

### `scripts/dev-a2ui.sh`
```bash
# Starts a2ui-backend (:10201) + a2ui-frontend (Vite + Electron)
```

### End-to-end smoke test checklist
- [ ] User asks "show my positions" → PositionsTable rendered with real data
- [ ] User asks "show portfolio pie chart" → PieChart rendered by sector
- [ ] User asks "add 10 AAPL at $200 to TFSA" → userAction → qfi-position add executed
- [ ] User asks "show history for AAPL" → LineChart rendered with price history
- [ ] Surface appears in history panel after each response
- [ ] Clicking history item re-renders surface

---

## Implementation Order & Dependencies

```
Phase 1 (Shared lib)
    └── Phase 2 (CLI tools)
            ├── Phase 3 (skills/*.md)
            ├── Phase 4 (unit tests)
            └── Phase 5 (custom catalog)
                    └── Phase 6 (A2UI backend)
                            └── Phase 7 (A2UI frontend)
                                    └── Phase 8 (integration)
```

Phases 3 and 4 can be worked on in parallel with Phase 2.
Phase 5 can be drafted during Phase 2.

---

## Resolved Decisions

| # | Question | Resolution |
|---|---|---|
| 1 | Report HTML rendering | `<iframe>` inside the A2UI surface (isolated styles) |
| 2 | Surface history persistence | `localStorage` in Electron (simple, per-machine) |
| 3 | A2UI backend port | **10201** (not a well-known protocol port) |
| 4 | Skills files packaging | Embedded at build time (self-contained binary) |
