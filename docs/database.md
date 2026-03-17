# Database Structure

SQLite database managed by SQLAlchemy. Default path: `backend/data/investments.db`.
Overridable via the `DATABASE_URL` environment variable.

---

## Tables

### `accounts`

Represents a brokerage or investment account.

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | INTEGER | PK, indexed | auto | Primary key |
| `name` | VARCHAR(100) | NOT NULL | — | Account display name |
| `base_currency` | VARCHAR(10) | NOT NULL | `CAD` | Account reporting currency |

**Relationships**: one-to-many with `positions` (cascade delete).

---

### `positions`

A holding within an account.

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | INTEGER | PK, indexed | auto | Primary key |
| `account_id` | INTEGER | FK → `accounts.id`, NOT NULL | — | Owning account |
| `symbol` | VARCHAR(20) | NOT NULL | — | Ticker symbol (e.g. `AAPL`) or cash label |
| `category` | ENUM | NOT NULL | — | `Equity`, `GIC`, `Cash`, `Dividend` |
| `quantity` | FLOAT | NOT NULL | — | Number of units / shares |
| `cost_per_share` | FLOAT | NOT NULL | — | Average cost per unit |
| `date_added` | DATE | NOT NULL | today | Date position was entered |
| `yield_rate` | FLOAT | nullable | `NULL` | Annual yield % (GIC / dividend positions) |
| `currency` | VARCHAR(10) | NOT NULL | `USD` | Position trading currency |

**Relationships**: many-to-one with `accounts`.

---

### `market_data`

Snapshot of market data fetched from Yahoo Finance. Each sync appends a new row; the latest row per symbol is selected via `MAX(timestamp)`.

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | INTEGER | PK, indexed | auto | Primary key |
| `symbol` | VARCHAR(20) | NOT NULL, indexed | — | Ticker symbol |
| `company_name` | VARCHAR(200) | nullable | `NULL` | Full company name |
| `last_price` | FLOAT | nullable | `NULL` | Most recent price |
| `pe_ratio` | FLOAT | nullable | `NULL` | Price-to-earnings ratio |
| `change_percent` | FLOAT | nullable | `NULL` | Day change % |
| `beta` | FLOAT | nullable | `NULL` | Beta vs market |
| `timestamp` | DATETIME (TZ) | NOT NULL | `now(UTC)` | UTC timestamp of the snapshot |

**Notes**: rows are never updated in-place; history is preserved. Synced every 5 minutes by APScheduler.

---

### `fx_rates`

FX rate snapshots. Same append-only pattern as `market_data`.

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | INTEGER | PK, indexed | auto | Primary key |
| `pair` | VARCHAR(20) | NOT NULL, indexed | — | Currency pair, e.g. `USD/CAD` |
| `rate` | FLOAT | NOT NULL | — | Exchange rate (1 unit of base → quote) |
| `timestamp` | DATETIME (TZ) | NOT NULL | `now(UTC)` | UTC timestamp of the snapshot |

---

### `sector_mappings`

Maps each equity symbol to a GICS sector for grouping and reporting.

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `symbol` | VARCHAR(20) | PK | — | Ticker symbol (matches `positions.symbol`) |
| `sector` | VARCHAR(100) | NOT NULL | `Unspecified` | Sector name (e.g. `Information Technology`) |

**Notes**: one row per symbol. Deleting a row resets the symbol to `Unspecified` in the UI.

---

### `settings`

Key-value store for persisted application configuration (AI provider settings).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `key` | VARCHAR(100) | PK | Setting name |
| `value` | VARCHAR(500) | NOT NULL | Setting value |

**Known keys**: `ai_provider`, `ollama_base_url`, `ollama_model`, `ollama_code_model`, `lmstudio_base_url`, `lmstudio_model`, `lmstudio_code_model`, `gemini_api_key`, `gemini_model`, `gemini_code_model`, `claude_api_key`, `claude_model`, `claude_code_model`.

---

## Entity Relationship Diagram

```
accounts
  │  id, name, base_currency
  │
  └──< positions
         id, account_id, symbol, category,
         quantity, cost_per_share, date_added,
         yield_rate, currency

market_data                    fx_rates
  id, symbol, company_name,     id, pair, rate, timestamp
  last_price, pe_ratio,
  change_percent, beta,
  timestamp

sector_mappings                settings
  symbol (PK), sector           key (PK), value
```

---

### `surface_history`

Stores the A2UI surface history for the A2UI app. Written by the A2UI backend (port 10201), not the existing backend.

| Column | Type | Constraints | Default | Description |
|---|---|---|---|---|
| `id` | VARCHAR(36) | PK | — | UUID surface ID |
| `title` | VARCHAR(200) | NOT NULL | — | Display title (derived from first Text component) |
| `snapshot` | TEXT | NOT NULL | — | Full A2UI surface JSON snapshot |
| `created_at` | DATETIME (TZ) | NOT NULL | `now(UTC)` | When the surface was created |

---

## Migrations

Schema changes are handled by `_migrate()` in `database.py`, which runs at startup after `create_all()`. It uses SQLite `PRAGMA table_info` to check for missing columns before altering.

| Migration | Description |
|---|---|
| Add `positions.currency` | Added `VARCHAR(10) DEFAULT 'USD'` to existing rows |
| Add `market_data.company_name` | Added nullable `VARCHAR(200)` column |
| `industry_mappings` → `sector_mappings` | Copies rows (renaming `industry` → `sector` column), then drops the old table |
