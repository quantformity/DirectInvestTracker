# Qf Direct Invest Tracker

A self-hosted desktop application for tracking a multi-account, multi-currency investment portfolio — equities, GICs, and cash — with real-time market data, AI-powered chat, and historical performance analysis.

Built with a **Python/FastAPI** backend and an **Electron/React** frontend. Runs entirely on your machine with no cloud services required (except Yahoo Finance for market data and an optional local Ollama LLM for AI features).

---

## Features

- **Multi-account portfolio** — TFSA, RRSP, taxable, or any custom account with its own base currency
- **Multi-currency positions** — each position has its own trading currency; MTM and PnL are converted through a two-hop FX chain (position → account → reporting currency)
- **Position categories** — Equities, GICs (with yield accrual), Cash, Dividends
- **Real-time market data** — prices, P/E ratios, beta, and 1-day % change via Yahoo Finance; auto-refreshes every 5 minutes
- **Historical performance** — on-the-fly PnL reconstruction for any date range using Yahoo Finance price history
- **AI chat assistant** — natural language portfolio queries and action planning via a local [Ollama](https://ollama.ai) LLM
- **Chart generation** — ask the AI to plot charts; it generates and executes SQL/Python and returns Plotly figures
- **Market Insights dashboard** — portfolio totals (MTM, PnL, Cash, GIC), per-symbol bars, and individual market cards
- **Configurable SQLite path** — choose where your database file lives from the app settings
- **Packaged desktop app** — single DMG/NSIS/AppImage with the backend binary bundled; no separate install required

---

## Screenshots

| Position Manager | Market Insights | AI Chat |
|:-:|:-:|:-:|
| _(Add positions with account, symbol, currency, quantity, cost)_ | _(Total MTM/PnL stat cards + bar charts by symbol)_ | _(Natural language queries and action confirmation)_ |

---

## Architecture

```
┌─────────────────────────────┐     HTTP/REST      ┌──────────────────────────────┐
│        Electron App         │ ◄────────────────► │      FastAPI Backend         │
│  React + TypeScript + Vite  │    localhost:8000   │  Python 3.12 + SQLAlchemy    │
│                             │                     │  SQLite · APScheduler        │
│  Pages:                     │                     │                              │
│  • Position Manager         │                     │  Routers:                    │
│  • Position List            │                     │  • /accounts                 │
│  • Summary                  │                     │  • /positions                │
│  • Market Insights          │                     │  • /summary                  │
│  • History                  │                     │  • /market-data              │
│                             │                     │  • /history                  │
│  Sidebar AI Chat            │                     │  • /ai   (Ollama)            │
└─────────────────────────────┘                     │  • /settings                 │
                                                     └──────────────────────────────┘
                                                               │          │
                                                     Yahoo Finance    Ollama (local)
```

In the **packaged desktop app**, the FastAPI binary is bundled inside `Resources/backend/` and launched automatically when the app starts. The SQLite database is stored in your OS user-data directory and survives app updates.

---

## Getting Started

### Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12+ | For running or building the backend |
| Node.js | 18+ | For running or building the frontend |
| [Ollama](https://ollama.ai) | any | Optional — required for AI chat features |

### Option A — Run with Docker (backend only)

```bash
# Start the backend
docker-compose up --build

# Then start the frontend dev server
cd frontend
npm install
npm run dev          # Web browser at http://localhost:5173
# or
npm run electron:dev # Electron desktop window
```

### Option B — Run without Docker

```bash
# 1. Backend
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload    # API at http://127.0.0.1:8000

# 2. Frontend (separate terminal)
cd frontend
npm install
npm run electron:dev             # Opens Electron with live reload
```

### Option C — Use the packaged app (macOS)

Download or build the DMG (see [Building the Desktop App](#building-the-desktop-app)), open it, drag to Applications, and launch. The backend starts automatically.

---

## Configuration

### AI Settings (Ollama)

Open **File → Settings…** (or `Cmd+,`) in the app and set:

| Field | Example | Description |
|-------|---------|-------------|
| Ollama Base URL | `http://localhost:11434` | URL where Ollama is running |
| Chat Model | `llama3.2` | Model for general chat and portfolio queries |
| Code / SQL Model | `qwen2.5-coder:7b` | Model for chart generation and SQL queries |

Click **Load Models** to fetch available models from your Ollama instance and choose from dropdowns.

### Environment Variables

For Docker or server deployments, set these in `.env` or your environment:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_CODE_MODEL=qwen2.5-coder:7b
REPORTING_CURRENCY=CAD
DATABASE_URL=sqlite:///data/investments.db
PORT=8000
```

### Database Location

The SQLite file is stored at:

| Platform | Default Path |
|----------|-------------|
| macOS | `~/Library/Application Support/Qf Direct Invest Tracker/investments.db` |
| Windows | `%APPDATA%\Qf Direct Invest Tracker\investments.db` |
| Linux | `~/.config/Qf Direct Invest Tracker/investments.db` |

You can change the path in **File → Settings… → Database → Browse…** and click **Apply & Restart App**.

---

## Building the Desktop App

### First-time setup

```bash
# Backend venv (required for PyInstaller)
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pyinstaller

# Frontend dependencies
cd ../frontend
npm install
```

### Full build (backend binary + Electron app)

```bash
./scripts/build-desktop.sh
```

### Frontend only (skip PyInstaller — useful after UI-only changes)

```bash
./scripts/build-desktop.sh --frontend
```

Build output:

| Platform | Output |
|----------|--------|
| macOS | `frontend/release/Qf Direct Invest Tracker-x.x.x-arm64.dmg` |
| Windows | `frontend/release/Qf Direct Invest Tracker Setup x.x.x.exe` |
| Linux | `frontend/release/Qf Direct Invest Tracker-x.x.x.AppImage` |

> **Note:** You must build on the target platform. macOS → DMG, Windows → NSIS installer, Linux → AppImage.

---

## Project Structure

```
investments/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, middleware, router registration
│   │   ├── database.py          # SQLAlchemy engine, session, schema migration
│   │   ├── models.py            # ORM models: Account, Position, MarketData, FxRate, Setting
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── accounts.py
│   │   │   ├── positions.py
│   │   │   ├── summary.py       # MTM/PnL calculations, FX conversion
│   │   │   ├── market_data.py
│   │   │   ├── history.py       # On-the-fly historical PnL
│   │   │   ├── ai.py            # Ollama chat, SQL execution, chart generation
│   │   │   ├── fx_rates.py
│   │   │   └── settings.py
│   │   └── services/
│   │       ├── yahoo_finance.py # Price/metadata fetching with TLS impersonation
│   │       ├── ollama.py        # LLM integration + portfolio context builder
│   │       └── scheduler.py     # APScheduler: market sync every 5 min
│   ├── backend_main.py          # PyInstaller entry point
│   ├── backend.spec             # PyInstaller build spec
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── electron/
│   │   ├── main.cjs             # Electron main process (backend spawning, IPC, native menu)
│   │   └── preload.cjs          # Context bridge (db path, settings, relaunch)
│   ├── src/
│   │   ├── api/client.ts        # Axios API client + TypeScript types
│   │   ├── components/
│   │   │   ├── Layout.tsx       # Sidebar nav + AI chat panel
│   │   │   ├── OllamaSettingsModal.tsx
│   │   │   ├── ChartRenderer.tsx
│   │   │   └── DataTable.tsx
│   │   ├── pages/
│   │   │   ├── PositionManager.tsx
│   │   │   ├── PositionList.tsx
│   │   │   ├── Summary.tsx
│   │   │   ├── MarketInsights.tsx
│   │   │   └── History.tsx
│   │   ├── store/settings.ts    # Zustand store (reporting currency, API URL)
│   │   ├── electron.d.ts        # Window.electronAPI type declarations
│   │   └── App.tsx              # Router setup
│   ├── build/
│   │   └── icon.icns            # macOS app icon
│   ├── public/
│   │   └── QuantformityIconNoText.png
│   ├── vite.config.ts
│   └── package.json
│
├── scripts/
│   └── build-desktop.sh         # Full build orchestration script
│
├── docker-compose.yml
└── README.md
```

---

## Data Model

```
Account
  id · name · base_currency

Position
  id · account_id · symbol · category (Equity|GIC|Cash|Dividend)
  quantity · cost_per_share · currency · date_added · yield_rate

MarketData
  symbol · last_price · pe_ratio · change_percent · beta · timestamp

FxRate
  pair (e.g. "USDCAD") · rate · timestamp

Setting
  key · value
```

### Currency conversion

MTM and PnL go through a two-hop FX chain:

```
position.currency  →[fx_stock_to_account]→  account.base_currency
                   →[fx_account_to_reporting]→  reporting_currency
```

FX rates are fetched from Yahoo Finance (e.g. `USDCAD=X`) with inverse-pair fallback and refreshed every 5 minutes alongside market data.

---

## AI Chat

The sidebar AI assistant can:

- Answer questions about your portfolio in natural language
- Plan and execute actions with confirmation ("Add 100 AAPL at $180 to my TFSA")
- Generate charts by writing and executing Python/SQL code
- Query the portfolio database with SELECT-only SQL (shown for review before running)

The LLM receives a system prompt containing your full database schema and current portfolio state on every request.

**Supported action intents:** add position, record dividend, sell/remove position, deposit/withdraw cash, rename account, update position details.

---

## API Reference

The backend exposes a REST API at `http://localhost:8000`. Interactive docs are available at `http://localhost:8000/docs` when running in development.

| Method | Path | Description |
|--------|------|-------------|
| GET/POST/PUT/DELETE | `/accounts/` | Account management |
| GET/POST/PUT/DELETE | `/positions/` | Position management |
| GET | `/summary/` | Portfolio summary with MTM/PnL |
| GET | `/market-data/` | Latest market data |
| POST | `/market-data/refresh` | Trigger immediate market data sync |
| GET | `/history/` | Historical PnL for a date range |
| POST | `/ai/chat` | Chat with the AI assistant |
| POST | `/ai/plan-action` | Parse an action intent |
| POST | `/ai/execute-action` | Execute a planned action |
| POST | `/ai/chart` | Generate a chart from a prompt |
| GET/PUT | `/settings/` | Ollama configuration |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend language | Python 3.12 |
| Web framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite |
| Task scheduling | APScheduler |
| Market data | Yahoo Finance via `curl_cffi` (TLS impersonation) |
| AI inference | Ollama (local LLM) |
| Desktop shell | Electron 40 |
| Frontend framework | React 19 + TypeScript 5.9 |
| Build tool | Vite 7 |
| Styling | Tailwind CSS 4 |
| Charts | Recharts + Plotly.js |
| State management | Zustand |
| Desktop packaging | PyInstaller (backend) + electron-builder (frontend) |

---

## License

Private / personal use.
