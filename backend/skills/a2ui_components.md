# A2UI UI Generation — Custom Components

This file tells you how to generate A2UI JSON messages that render rich investment
tracker UI in the QFI app. Read this alongside the other skills files to know what
data is available and how to request it.

## Important Rules

1. **Always respond with valid A2UI JSON messages** when asked to show data visually.
2. **Never embed real portfolio data** in your A2UI messages. Use `path` data bindings
   — the app will hydrate them with live data from the database automatically.
3. **Every surface needs a `beginRendering` message first**, then one or more
   `surfaceUpdate` messages, then a `dataModelUpdate` to trigger hydration.
4. **Use the `qfi-catalog-v1` catalogId** (not the default standard catalog) so
   custom components are available.
5. **Surface IDs must be unique** per conversation. Use descriptive kebab-case IDs,
   e.g. `"positions-view-1"`, `"sector-pie-2"`.
6. **One surface = one logical view**. Use `Tabs` to combine related views in one surface.

---

## A2UI Message Structure

Every UI response is a sequence of JSON messages, one per line (newline-delimited):

```
{"beginRendering": {...}}
{"surfaceUpdate": {...}}
{"dataModelUpdate": {...}}
```

### Step 1 — beginRendering
Declares the surface and its root component ID.

```json
{
  "beginRendering": {
    "surfaceId": "my-surface-1",
    "catalogId": "qfi-catalog-v1",
    "root": "root-col",
    "styles": {
      "primaryColor": "#3b82f6"
    }
  }
}
```

### Step 2 — surfaceUpdate
Sends the full flat component list (adjacency list model).
Every component has a unique `id` and a `component` object with exactly one key
(the component type name) containing its properties.

```json
{
  "surfaceUpdate": {
    "surfaceId": "my-surface-1",
    "components": [
      {
        "id": "root-col",
        "component": {
          "Column": {
            "children": { "explicitList": ["heading", "kpi", "table"] }
          }
        }
      },
      {
        "id": "heading",
        "component": {
          "Text": {
            "text": { "literalString": "My Positions" },
            "usageHint": "h2"
          }
        }
      },
      {
        "id": "kpi",
        "component": {
          "PortfolioKPI": {
            "dataBinding": "/portfolio/kpi"
          }
        }
      },
      {
        "id": "table",
        "component": {
          "PositionsTable": {
            "showSector": true,
            "dataBinding": "/positions/rows"
          }
        }
      }
    ]
  }
}
```

### Step 3 — dataModelUpdate
Declares which data paths the surface needs. The app intercepts these paths,
calls the appropriate CLI tool, and fills in the real data.
**You must emit a dataModelUpdate for every `dataBinding` path you used.**

```json
{
  "dataModelUpdate": {
    "surfaceId": "my-surface-1",
    "contents": [
      { "key": "positions/rows",  "valueString": "__hydrate__" },
      { "key": "portfolio/kpi",   "valueString": "__hydrate__" }
    ]
  }
}
```

> The value `"__hydrate__"` is a sentinel that tells the app to fetch real data.
> Never put actual data values here — leave hydration to the app.

---

## Custom Component Reference

### `PositionsTable`
Sortable, filterable table of all portfolio positions with P&L.

```json
{
  "id": "pos-table",
  "component": {
    "PositionsTable": {
      "title": { "literalString": "Positions" },
      "showPnl": true,
      "showSector": true,
      "dataBinding": "/positions/rows"
    }
  }
}
```

**Optional `columns` array** (show a subset):
`"symbol"`, `"category"`, `"account_name"`, `"quantity"`, `"cost_per_share"`,
`"currency"`, `"date_added"`, `"current_price"`, `"mtm"`, `"pnl"`, `"pnl_pct"`, `"sector"`

**Hydrated by:** `qfi-position list --json`

---

### `LineChart`
Time-series line chart. Supports a secondary Y axis on the right side.

```json
{
  "id": "line-chart",
  "component": {
    "LineChart": {
      "title": { "literalString": "Portfolio Value" },
      "xKey": "date",
      "series": [
        { "key": "mtm", "label": "Market Value", "color": "#3b82f6", "yAxis": "left"  },
        { "key": "pnl", "label": "P&L",          "color": "#10b981", "yAxis": "right" }
      ],
      "yLabel":  "MTM (CAD)",
      "y2Label": "P&L (CAD)",
      "height": 320,
      "dataBinding": "/chart/points"
    }
  }
}
```

**`series` fields:** `key` (required), `label` (required), `color` (optional hex),
`yAxis` (`"left"` or `"right"`, default `"left"`)

**Omit `y2Label`** if all series use the left axis.

**Hydrated by:** `qfi-history portfolio --json` / `qfi-history symbol SYMBOL --json` /
`qfi-history sector SECTOR --json` / `qfi-history account ID --json`

---

### `PieChart`
Proportional breakdown chart. Use for sector, category, or account distribution.

```json
{
  "id": "pie-chart",
  "component": {
    "PieChart": {
      "title": { "literalString": "By Sector" },
      "nameKey": "group_key",
      "valueKey": "total_mtm_reporting",
      "valuePrefix": "$",
      "showLegend": true,
      "height": 300,
      "dataBinding": "/chart/slices"
    }
  }
}
```

**`nameKey`** — the field used as slice label (e.g. `"group_key"`)
**`valueKey`** — the field used as slice value (e.g. `"total_mtm_reporting"`)

**Hydrated by:** `qfi-summary show --group-by sector --json`
(change `--group-by` to `category`, `account`, or `symbol` as needed)

---

### `BarChart`
Comparative bar chart. Use for P&L by sector, MTM by account, etc.

```json
{
  "id": "bar-chart",
  "component": {
    "BarChart": {
      "title": { "literalString": "P&L by Sector" },
      "xKey": "group_key",
      "bars": [
        { "key": "total_pnl_reporting", "label": "Unrealised P&L", "color": "#10b981" },
        { "key": "total_mtm_reporting", "label": "Market Value",   "color": "#3b82f6" }
      ],
      "yLabel": "CAD",
      "layout": "vertical",
      "height": 300,
      "dataBinding": "/chart/bars"
    }
  }
}
```

**`layout`:** `"vertical"` (bars rise upward, default) or `"horizontal"` (bars extend right,
better for many categories with long names)

**Hydrated by:** `qfi-summary show --group-by sector --json`

---

### `MarketQuoteCard`
Grid or list of market quote cards with price, change %, P/E, beta, and sector badge.

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

**`layout`:** `"grid"` (default) or `"list"`
**`columns`:** number of grid columns (default `3`)

**Hydrated by:** `qfi-market quote-list --json`

---

### `FxRateTable`
Compact table of latest FX rates and their timestamps.

```json
{
  "id": "fx-rates",
  "component": {
    "FxRateTable": {
      "title": { "literalString": "FX Rates" },
      "showTimestamp": true,
      "dataBinding": "/fx/rates"
    }
  }
}
```

**Hydrated by:** `qfi-fx list --json`

---

### `PortfolioKPI`
Four KPI tiles: Total Market Value, Total P&L (with %), Accounts, Positions.
Always place this at the top of summary or overview surfaces.

```json
{
  "id": "kpi",
  "component": {
    "PortfolioKPI": {
      "currency": { "literalString": "CAD" },
      "dataBinding": "/portfolio/kpi"
    }
  }
}
```

**Hydrated by:** `qfi-summary show --json` (the app derives KPI fields from summary totals)

---

### `SectorMappingEditor`
Interactive editor for assigning sectors to symbols. **Only use this when the user
explicitly asks to manage, edit, or update sector assignments.** For read-only sector
display, use standard `List`, `Card`, or `Text` components instead.

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

**Hydrated by:** `qfi-sector list --json`

**User actions emitted back to you:**

| `name` | `context` | Meaning |
|---|---|---|
| `sector.update` | `{ "symbol": "AAPL", "sector": "Financials" }` | User saved a new sector |
| `sector.reset`  | `{ "symbol": "AAPL" }` | User reset symbol to Unspecified |

When you receive a `sector.update` userAction, call `qfi-sector update SYMBOL SECTOR --json`
and confirm to the user. When you receive `sector.reset`, call `qfi-sector delete SYMBOL --json`.

---

### `ReportFrame`
Renders an HTML report inside a sandboxed iframe. You must assemble the final HTML
before populating the data binding — see flow below.

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

**Flow:**
1. Call `qfi-report generate --format html --json` to get the report HTML
2. Identify all `<div data-llm-section="...">` placeholder elements
3. For each placeholder, read its `data-context` attribute and generate a short narrative
4. Replace the placeholder `<!-- Agent: insert ... -->` comment with your narrative text
5. Populate `/report/frame` with `{ "html": "<complete html string>" }`

**Hydrated by:** agent-assembled (you build the final HTML, the app just renders it)

---

## Complete Example — Portfolio Overview Surface

User says: *"Show me a portfolio overview"*

```json
{"beginRendering": {"surfaceId": "overview-1", "catalogId": "qfi-catalog-v1", "root": "root", "styles": {"primaryColor": "#3b82f6"}}}
{"surfaceUpdate": {"surfaceId": "overview-1", "components": [
  {"id": "root", "component": {"Column": {"children": {"explicitList": ["title", "kpi", "divider1", "charts-row", "divider2", "pos-table"]}}}},
  {"id": "title", "component": {"Text": {"text": {"literalString": "Portfolio Overview"}, "usageHint": "h1"}}},
  {"id": "kpi", "component": {"PortfolioKPI": {"dataBinding": "/portfolio/kpi"}}},
  {"id": "divider1", "component": {"Divider": {"axis": "horizontal"}}},
  {"id": "charts-row", "component": {"Row": {"children": {"explicitList": ["pie", "bar"]}, "distribution": "spaceBetween"}}},
  {"id": "pie", "weight": 1, "component": {"PieChart": {"title": {"literalString": "By Sector"}, "nameKey": "group_key", "valueKey": "total_mtm_reporting", "valuePrefix": "$", "dataBinding": "/chart/slices"}}},
  {"id": "bar", "weight": 1, "component": {"BarChart": {"title": {"literalString": "P&L by Sector"}, "xKey": "group_key", "bars": [{"key": "total_pnl_reporting", "label": "P&L", "color": "#10b981"}], "yLabel": "CAD", "dataBinding": "/chart/bars"}}},
  {"id": "divider2", "component": {"Divider": {"axis": "horizontal"}}},
  {"id": "pos-table", "component": {"PositionsTable": {"showSector": true, "dataBinding": "/positions/rows"}}}
]}}
{"dataModelUpdate": {"surfaceId": "overview-1", "contents": [
  {"key": "portfolio/kpi",  "valueString": "__hydrate__"},
  {"key": "chart/slices",   "valueString": "__hydrate__"},
  {"key": "chart/bars",     "valueString": "__hydrate__"},
  {"key": "positions/rows", "valueString": "__hydrate__"}
]}}
```

---

## Complete Example — History Chart Surface

User says: *"Show me portfolio history"*

```json
{"beginRendering": {"surfaceId": "history-1", "catalogId": "qfi-catalog-v1", "root": "root", "styles": {"primaryColor": "#3b82f6"}}}
{"surfaceUpdate": {"surfaceId": "history-1", "components": [
  {"id": "root", "component": {"Column": {"children": {"explicitList": ["title", "chart"]}}}},
  {"id": "title", "component": {"Text": {"text": {"literalString": "Portfolio History"}, "usageHint": "h2"}}},
  {"id": "chart", "component": {"LineChart": {
    "xKey": "date",
    "series": [
      {"key": "mtm", "label": "Market Value", "color": "#3b82f6", "yAxis": "left"},
      {"key": "pnl", "label": "P&L",          "color": "#10b981", "yAxis": "right"}
    ],
    "yLabel": "MTM (CAD)",
    "y2Label": "P&L (CAD)",
    "height": 380,
    "dataBinding": "/chart/points"
  }}}
]}}
{"dataModelUpdate": {"surfaceId": "history-1", "contents": [
  {"key": "chart/points", "valueString": "__hydrate__"}
]}}
```

---

## Choosing the Right Component

| User asks about | Component(s) to use |
|---|---|
| "show my positions" / "list holdings" | `PositionsTable` |
| "portfolio summary" / "overview" | `PortfolioKPI` + `PieChart` + `PositionsTable` |
| "portfolio history" / "performance over time" | `LineChart` (portfolio) |
| "history of AAPL" / "price chart for X" | `LineChart` (symbol) |
| "sector breakdown" / "by sector" | `PieChart` + `BarChart` |
| "market quotes" / "current prices" | `MarketQuoteCard` |
| "FX rates" / "exchange rates" | `FxRateTable` |
| "sector performance over time" | `LineChart` (sector) |
| "account breakdown" / "by account" | `BarChart` or `PieChart` |
| "manage sectors" / "edit sector" / "assign sector" | `SectorMappingEditor` |
| "show sectors" / "what sector is X" | Standard `List` / `Text` (no custom needed) |
| "generate report" / "full report" | `ReportFrame` (with LLM narrative injection) |
| "account MTM" / "account value" | `PortfolioKPI` filtered + `BarChart` |

---

## Data Model Path Reference

| Path | Hydrated by | Content |
|---|---|---|
| `/positions/rows` | `qfi-position list --json` | All enriched positions |
| `/portfolio/kpi` | `qfi-summary show --json` | 4 KPI fields |
| `/chart/points` | `qfi-history portfolio/symbol/sector/account --json` | Time series |
| `/chart/slices` | `qfi-summary show --group-by X --json` | Pie slice data |
| `/chart/bars` | `qfi-summary show --group-by X --json` | Bar chart data |
| `/market/quotes` | `qfi-market quote-list --json` | All latest quotes |
| `/fx/rates` | `qfi-fx list --json` | All latest FX rates |
| `/sector/mappings` | `qfi-sector list --json` | Symbol → sector pairs |
| `/report/frame` | agent-assembled | Final HTML string |
| `/accounts/list` | `qfi-account list --json` | Account list |
| `/accounts/mtm` | `qfi-account mtm --json` | MTM per account |
