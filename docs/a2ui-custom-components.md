# A2UI Custom Component Specifications

Custom components extending the standard A2UI v0.8 catalog for the QFI investment tracker.
These are registered in `a2ui-backend/catalog/standard_extensions.json` and rendered
by the A2UI frontend using Recharts, TanStack Table, and custom React components.

---

## Standard A2UI Coverage (no custom needed)

The following UI elements are built entirely from the v0.8 standard catalog:

| UI Element | Standard Components Used |
|---|---|
| Navigation between views | `Tabs` |
| Add / Edit position form | `TextField`, `DateTimeInput`, `MultipleChoice`, `Button` |
| Sector assignment input | `TextField` + `Button` |
| Settings forms | `TextField`, `MultipleChoice`, `Button` |
| Simple KPI numbers | `Text` (h1/h2) inside `Card` + `Row` |
| Confirm / action dialogs | `Modal` + `Button` |
| Section headings | `Text` (h2/h3) |
| Sector display (read-only) | `List`, `Card`, `Text` with sector label styling |

---

## Custom Components

### 1. `PositionsTable`

**Purpose:** Sortable, filterable table of portfolio positions with enriched P&L columns.
Replaces the Position List page.

**Rendered by:** TanStack Table

**Properties:**

| Property | Type | Required | Description |
|---|---|---|---|
| `title` | `literalString \| path` | No | Optional table heading |
| `columns` | `string[]` | No | Subset of columns to show. Default: all |
| `showPnl` | `boolean` | No | Show P&L columns. Default: `true` |
| `showSector` | `boolean` | No | Show Sector column. Default: `true` |
| `dataBinding` | `string` | Yes | Path to data model, e.g. `/positions/rows` |

**Data shape:**
```json
[
  {
    "id": 1,
    "symbol": "AAPL",
    "category": "Equity",
    "account_name": "TFSA",
    "quantity": 10,
    "cost_per_share": 150.0,
    "currency": "USD",
    "date_added": "2024-01-01",
    "current_price": 180.0,
    "mtm": 2448.0,
    "pnl": 408.0,
    "pnl_pct": 20.0,
    "sector": "Information Technology"
  }
]
```

**Hydrator mapping:** `dataBinding: /positions/rows` → `qfi-position list --json`

**Example A2UI JSON:**
```json
{
  "id": "pos-table",
  "component": {
    "PositionsTable": {
      "title": { "literalString": "My Positions" },
      "showSector": true,
      "dataBinding": "/positions/rows"
    }
  }
}
```

---

### 2. `LineChart`

**Purpose:** Time-series line chart for portfolio value history, symbol price history,
and sector history. Supports an optional secondary Y axis. Replaces the History page charts.

**Rendered by:** Recharts `LineChart`

**Properties:**

| Property | Type | Required | Description |
|---|---|---|---|
| `title` | `literalString \| path` | No | Chart heading |
| `xKey` | `string` | Yes | Key in each data point for the X axis (e.g. `"date"`) |
| `series` | `SeriesDef[]` | Yes | Lines to plot (see below) |
| `xLabel` | `string` | No | X axis label |
| `yLabel` | `string` | No | Primary Y axis label |
| `y2Label` | `string` | No | Secondary Y axis label (right side). Only shown if at least one series has `yAxis: "right"` |
| `height` | `number` | No | Pixel height. Default: `300` |
| `dataBinding` | `string` | Yes | Path to data model |

**`SeriesDef` object:**

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | `string` | Yes | Data field name to plot |
| `label` | `string` | Yes | Legend label |
| `color` | `string` | No | Hex color. Auto-assigned if omitted |
| `yAxis` | `"left" \| "right"` | No | Which Y axis to use. Default: `"left"` |

**Data shape:**
```json
[
  { "date": "2024-01-02", "mtm": 45000.0, "pnl": 2000.0 },
  { "date": "2024-01-03", "mtm": 46200.0, "pnl": 3200.0 }
]
```

**Hydrator mapping:** `dataBinding: /chart/points` → `qfi-history portfolio --json`
(or `symbol`, `sector`, `account` variant depending on context)

**Example A2UI JSON (dual Y axis):**
```json
{
  "id": "history-chart",
  "component": {
    "LineChart": {
      "title": { "literalString": "Portfolio Value Over Time" },
      "xKey": "date",
      "series": [
        { "key": "mtm",  "label": "Market Value", "color": "#3b82f6", "yAxis": "left"  },
        { "key": "pnl",  "label": "P&L",          "color": "#10b981", "yAxis": "right" }
      ],
      "yLabel": "MTM (CAD)",
      "y2Label": "P&L (CAD)",
      "dataBinding": "/chart/points"
    }
  }
}
```

---

### 3. `PieChart`

**Purpose:** Proportional breakdown by sector, category, or account.
Replaces the Summary pie chart.

**Rendered by:** Recharts `PieChart`

**Properties:**

| Property | Type | Required | Description |
|---|---|---|---|
| `title` | `literalString \| path` | No | Chart heading |
| `nameKey` | `string` | Yes | Key for slice label (e.g. `"group_key"`) |
| `valueKey` | `string` | Yes | Key for slice value (e.g. `"total_mtm_reporting"`) |
| `height` | `number` | No | Pixel height. Default: `300` |
| `showLegend` | `boolean` | No | Default: `true` |
| `valuePrefix` | `string` | No | Prepended to tooltip values, e.g. `"$"` |
| `dataBinding` | `string` | Yes | Path to data model |

**Data shape:**
```json
[
  { "group_key": "Information Technology", "total_mtm_reporting": 24480.0, "proportion": 35.2 },
  { "group_key": "Financials",             "total_mtm_reporting": 18000.0, "proportion": 25.9 }
]
```

**Hydrator mapping:** `dataBinding: /chart/slices` → `qfi-summary show --group-by sector --json`
(or `category`, `account` variant)

**Example A2UI JSON:**
```json
{
  "id": "sector-pie",
  "component": {
    "PieChart": {
      "title": { "literalString": "Portfolio by Sector" },
      "nameKey": "group_key",
      "valueKey": "total_mtm_reporting",
      "valuePrefix": "$",
      "dataBinding": "/chart/slices"
    }
  }
}
```

---

### 4. `BarChart`

**Purpose:** Comparative bar chart for P&L by sector/period, account comparison.
Replaces the Report bar charts.

**Rendered by:** Recharts `BarChart`

**Properties:**

| Property | Type | Required | Description |
|---|---|---|---|
| `title` | `literalString \| path` | No | Chart heading |
| `xKey` | `string` | Yes | Key for X axis categories |
| `bars` | `BarDef[]` | Yes | Bars to render (see below) |
| `xLabel` | `string` | No | X axis label |
| `yLabel` | `string` | No | Y axis label |
| `height` | `number` | No | Pixel height. Default: `300` |
| `layout` | `"vertical" \| "horizontal"` | No | Default: `"vertical"` |
| `dataBinding` | `string` | Yes | Path to data model |

**`BarDef` object:**

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | `string` | Yes | Data field name |
| `label` | `string` | Yes | Legend label |
| `color` | `string` | No | Hex color. Auto-assigned if omitted |

**Data shape:**
```json
[
  { "group_key": "Information Technology", "pnl": 4080.0,  "mtm": 24480.0 },
  { "group_key": "Financials",             "pnl": -320.0, "mtm": 18000.0 }
]
```

**Hydrator mapping:** `dataBinding: /chart/bars` → `qfi-summary show --group-by sector --json`

**Example A2UI JSON:**
```json
{
  "id": "pnl-bar",
  "component": {
    "BarChart": {
      "title": { "literalString": "P&L by Sector" },
      "xKey": "group_key",
      "bars": [
        { "key": "pnl", "label": "Unrealised P&L", "color": "#10b981" }
      ],
      "yLabel": "CAD",
      "dataBinding": "/chart/bars"
    }
  }
}
```

---

### 5. `MarketQuoteCard`

**Purpose:** Grid or list of market quote cards showing live price, change %, P/E, beta,
and sector badge. Replaces the Market Insights page.

**Rendered by:** Custom React card grid (mirrors existing `MarketCard` component)

**Properties:**

| Property | Type | Required | Description |
|---|---|---|---|
| `layout` | `"grid" \| "list"` | No | Default: `"grid"` |
| `columns` | `number` | No | Grid columns. Default: `3` |
| `dataBinding` | `string` | Yes | Path to data model |

**Data shape:**
```json
[
  {
    "symbol": "AAPL",
    "company_name": "Apple Inc.",
    "last_price": 180.0,
    "change_percent": 0.5,
    "pe_ratio": 28.5,
    "beta": 1.2,
    "sector": "Information Technology",
    "timestamp": "2026-03-17T14:30:00+00:00"
  }
]
```

**Hydrator mapping:** `dataBinding: /market/quotes` → `qfi-market quote-list --json`

**Example A2UI JSON:**
```json
{
  "id": "market-quotes",
  "component": {
    "MarketQuoteCard": {
      "layout": "grid",
      "columns": 3,
      "dataBinding": "/market/quotes"
    }
  }
}
```

---

### 6. `FxRateTable`

**Purpose:** Compact table showing latest FX rates with timestamps.
Replaces the FX Rates page.

**Rendered by:** Styled table (no TanStack needed — small dataset)

**Properties:**

| Property | Type | Required | Description |
|---|---|---|---|
| `title` | `literalString \| path` | No | Table heading |
| `showTimestamp` | `boolean` | No | Show last-updated column. Default: `true` |
| `dataBinding` | `string` | Yes | Path to data model |

**Data shape:**
```json
[
  {
    "pair": "USD/CAD",
    "rate": 1.3612,
    "timestamp": "2026-03-17T14:30:00+00:00"
  }
]
```

**Hydrator mapping:** `dataBinding: /fx/rates` → `qfi-fx list --json`

**Example A2UI JSON:**
```json
{
  "id": "fx-table",
  "component": {
    "FxRateTable": {
      "title": { "literalString": "FX Rates" },
      "showTimestamp": true,
      "dataBinding": "/fx/rates"
    }
  }
}
```

---

### 7. `PortfolioKPI`

**Purpose:** Row of four key performance indicator tiles: total market value, total P&L,
account count, position count. Appears at the top of summary and report surfaces.

**Rendered by:** Styled tile grid

**Properties:**

| Property | Type | Required | Description |
|---|---|---|---|
| `currency` | `literalString \| path` | No | Currency label shown on monetary tiles. Default: `"CAD"` |
| `dataBinding` | `string` | Yes | Path to data model |

**Tiles (fixed set):**

| Tile | Field | Description |
|---|---|---|
| Total Market Value | `total_mtm` | Sum of all positions MTM in reporting currency |
| Total P&L | `total_pnl` + `total_pnl_pct` | Unrealised P&L with percentage |
| Accounts | `account_count` | Number of accounts |
| Positions | `position_count` | Number of open positions |

**Data shape:**
```json
{
  "total_mtm": 69610.0,
  "total_pnl": 4080.0,
  "total_pnl_pct": 6.23,
  "account_count": 2,
  "position_count": 3,
  "reporting_currency": "CAD"
}
```

**Hydrator mapping:** `dataBinding: /portfolio/kpi` → derived from `qfi-summary show --json`

**Example A2UI JSON:**
```json
{
  "id": "portfolio-kpi",
  "component": {
    "PortfolioKPI": {
      "currency": { "path": "/portfolio/kpi/reporting_currency" },
      "dataBinding": "/portfolio/kpi"
    }
  }
}
```

---

### 8. `SectorMappingEditor`

**Purpose:** Interactive table for assigning sectors to symbols. Each row has a symbol
label and a dropdown/autocomplete input pre-populated with existing sectors.
Only rendered when the user explicitly asks to manage or edit sector assignments.
For read-only sector display, use standard `List`, `Card`, or `Text` components instead.

**Rendered by:** Custom React table (mirrors existing `SectorMappingPage`)

**Properties:**

| Property | Type | Required | Description |
|---|---|---|---|
| `title` | `literalString \| path` | No | Heading. Default: `"Sector Mapping"` |
| `dataBinding` | `string` | Yes | Path to data model |

**Actions emitted (via standard A2UI `userAction`):**

| Action name | Context payload | Description |
|---|---|---|
| `sector.update` | `{ symbol, sector }` | User changed a symbol's sector and blurred |
| `sector.reset` | `{ symbol }` | User clicked Reset on a row |

**Data shape:**
```json
[
  { "symbol": "AAPL",   "sector": "Information Technology" },
  { "symbol": "VFV.TO", "sector": "Unspecified" }
]
```

**Hydrator mapping:** `dataBinding: /sector/mappings` → `qfi-sector list --json`

**Example A2UI JSON:**
```json
{
  "id": "sector-editor",
  "component": {
    "SectorMappingEditor": {
      "title": { "literalString": "Manage Sector Assignments" },
      "dataBinding": "/sector/mappings"
    }
  }
}
```

---

### 9. `ReportFrame`

**Purpose:** Renders the HTML report generated by `qfi-report generate --format html`
inside a sandboxed `<iframe>`. The A2UI agent is responsible for injecting LLM-generated
narrative into the `data-llm-section` placeholders before the HTML is passed to this component.

**Rendered by:** `<iframe srcdoc="...">` (sandboxed, no scripts from report allowed)

**Properties:**

| Property | Type | Required | Description |
|---|---|---|---|
| `height` | `number` | No | Iframe height in pixels. Default: `600` |
| `dataBinding` | `string` | Yes | Path to data model — must contain the final HTML string |

**Data shape at the bound path:**
```json
{
  "html": "<html>...</html>"
}
```

**Flow:**
1. Agent calls `qfi-report generate --format html --json`
2. Agent receives HTML with `data-llm-section` placeholder divs
3. Agent asks LLM to generate narrative for each placeholder using its `data-context`
4. Agent injects narratives into placeholders
5. Agent populates `/report/frame` data model with the final HTML string
6. `ReportFrame` renders it inside a sandboxed iframe

**Hydrator mapping:** `dataBinding: /report/frame` → agent-assembled (not a direct CLI call)

**Example A2UI JSON:**
```json
{
  "id": "report-iframe",
  "component": {
    "ReportFrame": {
      "height": 700,
      "dataBinding": "/report/frame"
    }
  }
}
```

**HTML placeholder format** (produced by `qfi-report --format html`):
```html
<div class="llm-narrative"
     data-llm-section="portfolio_overview"
     data-context='{"total_mtm": 69610.0, "total_pnl": 4080.0, "currency": "CAD"}'>
  <!-- Agent: insert portfolio overview narrative here -->
</div>
```

---

## Component Summary

| # | Component | Replaces | Renderer | Data Path | Hydrator CLI |
|---|---|---|---|---|---|
| 1 | `PositionsTable` | Position List page | TanStack Table | `/positions/rows` | `qfi-position list` |
| 2 | `LineChart` | History charts | Recharts | `/chart/points` | `qfi-history *` |
| 3 | `PieChart` | Summary pie | Recharts | `/chart/slices` | `qfi-summary show` |
| 4 | `BarChart` | Report bar charts | Recharts | `/chart/bars` | `qfi-summary show` |
| 5 | `MarketQuoteCard` | Market Insights | Custom React | `/market/quotes` | `qfi-market quote-list` |
| 6 | `FxRateTable` | FX Rates page | Styled table | `/fx/rates` | `qfi-fx list` |
| 7 | `PortfolioKPI` | Summary KPI row | Tile grid | `/portfolio/kpi` | `qfi-summary show` |
| 8 | `SectorMappingEditor` | Sector Mapping page | Custom React | `/sector/mappings` | `qfi-sector list` |
| 9 | `ReportFrame` | Report page | `<iframe>` | `/report/frame` | agent-assembled |

---

## Catalog Definition File

These components are declared in `a2ui-backend/catalog/standard_extensions.json`:

```json
{
  "catalogId": "qfi-catalog-v1",
  "extends": "https://a2ui.org/specification/v0_8/standard_catalog_definition.json",
  "components": {
    "PositionsTable":      { "dataBinding": "/positions/rows" },
    "LineChart":           { "dataBinding": "/chart/points" },
    "PieChart":            { "dataBinding": "/chart/slices" },
    "BarChart":            { "dataBinding": "/chart/bars" },
    "MarketQuoteCard":     { "dataBinding": "/market/quotes" },
    "FxRateTable":         { "dataBinding": "/fx/rates" },
    "PortfolioKPI":        { "dataBinding": "/portfolio/kpi" },
    "SectorMappingEditor": { "dataBinding": "/sector/mappings" },
    "ReportFrame":         { "dataBinding": "/report/frame" }
  }
}
```

---

## Data Model Path Registry

The hydrator service in the A2UI backend uses this mapping to know which CLI tool
to call when the LLM references a data binding path:

| Path | CLI Command | Notes |
|---|---|---|
| `/positions/rows` | `qfi-position list --json` | All positions, enriched |
| `/chart/points` | `qfi-history portfolio --json` | Default; overridden by context |
| `/chart/slices` | `qfi-summary show --group-by sector --json` | `group-by` set by agent |
| `/chart/bars` | `qfi-summary show --group-by sector --json` | `group-by` set by agent |
| `/market/quotes` | `qfi-market quote-list --json` | |
| `/fx/rates` | `qfi-fx list --json` | |
| `/portfolio/kpi` | `qfi-summary show --json` | Derived from summary totals |
| `/sector/mappings` | `qfi-sector list --json` | |
| `/report/frame` | agent-assembled | Agent injects LLM narratives before hydration |
| `/accounts/list` | `qfi-account list --json` | |
| `/accounts/mtm` | `qfi-account mtm --json` | |
