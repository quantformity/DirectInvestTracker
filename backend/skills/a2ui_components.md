# A2UI UI Generation

Generate A2UI JSON when asked to show data visually. Use catalogId `qfi-catalog-v1`.

## Rules
1. Always respond with A2UI JSON for visual requests.
2. Never embed real data — use `path` data bindings; the app hydrates them automatically.
3. Every surface: `beginRendering` → `surfaceUpdate` → `dataModelUpdate`.
4. Surface IDs: unique kebab-case, e.g. `"positions-view-1"`.

## Message Format (one JSON per line)

```
{"beginRendering": {"surfaceId": "ID", "catalogId": "qfi-catalog-v1", "root": "ROOT_ID", "styles": {"primaryColor": "#3b82f6"}}}
{"surfaceUpdate": {"surfaceId": "ID", "components": [ COMPONENTS ]}}
{"dataModelUpdate": {"surfaceId": "ID", "contents": [{"key": "PATH", "valueString": "__hydrate__"}]}}
```

Each component: `{"id": "ID", "component": {"TypeName": {PROPS}}}`

Children: `"children": {"explicitList": ["id1", "id2"]}`

Data binding: `"dataBinding": "/path/key"`

Text values: `{"literalString": "text"}` or `{"path": "datakey"}`

## Standard Layout Components
- `Column` — vertical stack. Props: `children`, `gap`, `padding`
- `Row` — horizontal stack. Props: `children`, `distribution` (`spaceBetween`/`center`/`start`), `gap`
- `Card` — container with border. Props: `children`, `title`
- `Text` — text. Props: `text` (literalString), `usageHint` (`h1`/`h2`/`body`/`caption`)
- `Divider` — separator. Props: `axis` (`horizontal`/`vertical`)
- `Button` — action button. Props: `label` (literalString), `actionName` (string)

## Custom Components

**PortfolioKPI** — 4 KPI tiles (MTM, P&L, Accounts, Positions)
Props: `dataBinding: "/portfolio/kpi"`, optional `currency`
Hydrated by: `qfi-summary show --json`

**PositionsTable** — sortable positions table
Props: `dataBinding: "/positions/rows"`, `showPnl: true`, `showSector: true`
Optional `columns`: `["symbol","category","account_name","quantity","cost_per_share","currency","current_price","mtm","pnl","pnl_pct","sector"]`
Hydrated by: `qfi-position list --json`

**LineChart** — time-series chart
Props: `dataBinding`, `xKey: "date"`, `series: [{key, label, color, yAxis}]`, `yLabel`, `y2Label` (if right axis used), `height`
`yAxis`: `"left"` (default) or `"right"`
Hydrated by: `qfi-history portfolio/symbol/sector/account --json`

**PieChart** — proportional breakdown
Props: `dataBinding`, `nameKey: "group_key"`, `valueKey: "total_mtm_reporting"`, `valuePrefix: "$"`, `showLegend: true`, `height`
Use `/chart/slices/sector`, `/chart/slices/symbol`, `/chart/slices/account`, or `/chart/slices/category`

**BarChart** — comparative bars
Props: `dataBinding`, `xKey: "group_key"`, `bars: [{key, label, color}]`, `yLabel` (plain string), `layout` (plain string: `"vertical"` or `"horizontal"`), `height`
Use `/chart/bars/sector`, `/chart/bars/symbol`, `/chart/bars/account`, or `/chart/bars/category`
Note: `yLabel` and `layout` are plain strings, NOT `{literalString: ...}` objects

**MarketQuoteCard** — quote cards grid/list
Props: `dataBinding: "/market/quotes"`, `layout: "grid"|"list"`, `columns: 3`
Hydrated by: `qfi-market quote-list --json`

**FxRateTable** — FX rates table
Props: `dataBinding: "/fx/rates"`, `showTimestamp: true`
Hydrated by: `qfi-fx list --json`

**SectorMappingEditor** — sector assignment editor (only when user asks to manage/edit sectors)
Props: `dataBinding: "/sector/mappings"`
Hydrated by: `qfi-sector list --json`
Actions: `sector.update {symbol, sector}`, `sector.reset {symbol}`

**ReportFrame** — HTML report iframe
Props: `dataBinding: "/report/frame"`, `height: 700`
Flow: call `qfi-report generate --format html --json` → fill `<div data-llm-section>` placeholders → set `{html: "..."}` in data model

## Data Paths
| Path | Source |
|---|---|
| `/positions/rows` | qfi-position list |
| `/portfolio/kpi` | qfi-summary show |
| `/chart/points` | qfi-history portfolio/symbol/sector/account |
| `/chart/slices/sector` | qfi-summary show --group-by sector |
| `/chart/slices/symbol` | qfi-summary show --group-by symbol |
| `/chart/slices/account` | qfi-summary show --group-by account |
| `/chart/slices/category` | qfi-summary show --group-by category |
| `/chart/bars/sector` | qfi-summary show --group-by sector |
| `/chart/bars/symbol` | qfi-summary show --group-by symbol |
| `/chart/bars/account` | qfi-summary show --group-by account |
| `/chart/bars/category` | qfi-summary show --group-by category |
| `/market/quotes` | qfi-market quote-list |
| `/fx/rates` | qfi-fx list |
| `/sector/mappings` | qfi-sector list |
| `/accounts/list` | qfi-account list |
| `/accounts/mtm` | qfi-account mtm |

**Important:** Always use the specific path variant, e.g. `/chart/bars/symbol` for symbol PnL, `/chart/bars/sector` for sector breakdown. Plain `/chart/bars` defaults to sector.

## Component Selection
| User asks | Use |
|---|---|
| positions / holdings | PositionsTable |
| overview / summary | PortfolioKPI + PieChart + PositionsTable |
| portfolio history / performance | LineChart (portfolio) |
| history of SYMBOL | LineChart (symbol) |
| sector breakdown | PieChart + BarChart |
| market quotes / prices | MarketQuoteCard |
| FX rates | FxRateTable |
| manage / edit sectors | SectorMappingEditor |
| full report | ReportFrame |
| account breakdown | BarChart or PieChart |

## Example — Portfolio Overview

```
{"beginRendering": {"surfaceId": "overview-1", "catalogId": "qfi-catalog-v1", "root": "root", "styles": {"primaryColor": "#3b82f6"}}}
{"surfaceUpdate": {"surfaceId": "overview-1", "components": [
  {"id": "root", "component": {"Column": {"children": {"explicitList": ["kpi", "pie", "table"]}}}},
  {"id": "kpi", "component": {"PortfolioKPI": {"dataBinding": "/portfolio/kpi"}}},
  {"id": "pie", "component": {"PieChart": {"title": {"literalString": "By Sector"}, "nameKey": "group_key", "valueKey": "total_mtm_reporting", "valuePrefix": "$", "dataBinding": "/chart/slices"}}},
  {"id": "table", "component": {"PositionsTable": {"showSector": true, "dataBinding": "/positions/rows"}}}
]}}
{"dataModelUpdate": {"surfaceId": "overview-1", "contents": [
  {"key": "portfolio/kpi", "valueString": "__hydrate__"},
  {"key": "chart/slices", "valueString": "__hydrate__"},
  {"key": "positions/rows", "valueString": "__hydrate__"}
]}}
```
