# A2UI: From User Prompt to Live UI

This document traces a complete example of how a user prompt in the chat panel becomes a rendered UI widget, and how subsequent prompts update that widget.

---

## System Overview

The app has three panels:

```
┌────────────────────────────────────────────────────────────┐
│  History Panel  │      Surface Panel (centre)    │  Chat   │
│  (past surfaces)│      Live A2UI widget lives here│  Panel  │
└────────────────────────────────────────────────────────────┘
```

The **Chat Panel** sends messages → **A2UI Backend** calls the LLM and hydrates data → **Surface Panel** renders the result.

---

## Example 1 — First Prompt: "Show me my portfolio"

### Step 1 — User types and presses Enter

`ChatPanel.tsx` collects the input and calls `streamChatV2()`:

```typescript
// ChatPanel.tsx — handleSend()
const apiMessages = [...messages, userMsg].map(m => ({ role: m.role, content: m.content }));
for await (const event of streamChatV2(apiMessages)) { ... }
```

The full conversation history is sent so the LLM has context for follow-up turns.

---

### Step 2 — Backend receives POST /chat

`chat.py` receives `{ messages: [...], surface_id: null }` and starts an SSE stream:

```
POST http://localhost:10201/chat
Content-Type: application/json

{
  "messages": [
    { "role": "user", "content": "Show me my portfolio" }
  ]
}
```

It immediately yields a thinking event:

```
event: thinking
data: {"status": "Thinking..."}
```

---

### Step 3 — LLM call (in thread executor)

The system prompt (`backend/skills/a2ui_components.md`) instructs the LLM to respond in A2UI JSON format. The LLM returns something like:

```
{"beginRendering": {"surfaceId": "overview-1", "catalogId": "qfi-catalog-v1", "root": "root", "styles": {"primaryColor": "#3b82f6"}}}
{"surfaceUpdate": {"surfaceId": "overview-1", "components": [
  {"id": "root", "component": {"Column": {"children": {"explicitList": ["kpi", "pie", "table"]}}}},
  {"id": "kpi",  "component": {"PortfolioKPI": {"dataBinding": "/portfolio/kpi"}}},
  {"id": "pie",  "component": {"PieChart": {"dataBinding": "/chart/slices/sector", "nameKey": "group_key", "valueKey": "total_mtm_reporting", "valuePrefix": "$"}}},
  {"id": "table","component": {"PositionsTable": {"dataBinding": "/positions/rows", "showPnl": true, "showSector": true}}}
]}}
{"dataModelUpdate": {"surfaceId": "overview-1", "contents": [
  {"key": "portfolio/kpi",       "valueString": "__hydrate__"},
  {"key": "chart/slices/sector", "valueString": "__hydrate__"},
  {"key": "positions/rows",      "valueString": "__hydrate__"}
]}}
```

`_parse_a2ui_lines()` extracts the three JSON objects. `_reassemble()` validates the structure (adds a Column wrapper if the LLM omitted the root, infers components from paths if surfaceUpdate is missing, etc.).

---

### Step 4 — Data hydration

`chat.py` collects all paths marked `"__hydrate__"` and calls `hydrate_all()`:

```python
# hydrator.py
all_paths = ["portfolio/kpi", "chart/slices/sector", "positions/rows"]
hydrated  = hydrate_all(all_paths)
# → runs: qfi-summary show --json
#         qfi-summary show --group-by sector --json
#         qfi-position list --json
```

Another SSE event fires while data loads:

```
event: thinking
data: {"status": "Fetching portfolio data..."}
```

---

### Step 5 — Backend streams A2UI messages

Three SSE events are sent in sequence, with `__hydrate__` replaced by real data:

```
event: a2ui
data: {"beginRendering": {"surfaceId": "abc-123", "catalogId": "qfi-catalog-v1", "root": "root", ...}}

event: a2ui
data: {"surfaceUpdate": {"surfaceId": "abc-123", "components": [...]}}

event: a2ui
data: {"dataModelUpdate": {"surfaceId": "abc-123", "contents": [
  {"key": "portfolio/kpi",       "valueString": "{\"total_mtm\": 142500, \"total_pnl\": 8320, ...}"},
  {"key": "chart/slices/sector", "valueString": "[{\"group_key\": \"Technology\", \"total_mtm_reporting\": 65000}, ...]"},
  {"key": "positions/rows",      "valueString": "[{\"symbol\": \"AAPL\", \"quantity\": 50, ...}]"}
]}}

event: done
data: {"surface_id": "abc-123", "status": "complete"}
```

---

### Step 6 — Frontend assembles the surface

`ChatPanel.tsx` processes each SSE event as it arrives:

```typescript
if ("beginRendering" in msg) {
  surfaceId = msg.beginRendering.surfaceId;
  rootId    = msg.beginRendering.root;            // → "root"
} else if ("surfaceUpdate" in msg) {
  components.push(...msg.surfaceUpdate.components); // → 4 component objects
} else if ("dataModelUpdate" in msg) {
  for (const item of contents) {
    dataModel[item.key] = JSON.parse(item.valueString); // populate data store
  }
}
```

When `done` arrives, the completed surface is saved to Zustand:

```typescript
addOrUpdateSurface({
  id:        "abc-123",
  title:     "Portfolio Overview",
  rootId:    "root",
  components: [...],   // 4 components
  dataModel:  {        // hydrated data
    "portfolio/kpi":       { total_mtm: 142500, ... },
    "chart/slices/sector": [{ group_key: "Technology", ... }],
    "positions/rows":      [{ symbol: "AAPL", ... }],
  },
  createdAt: "2026-03-18T10:00:00Z",
});
```

`activeSurfaceId` is set to `"abc-123"` — the Surface Panel re-renders immediately.

---

### Step 7 — A2UIRenderer renders the tree

`SurfacePanel.tsx` passes the surface to `A2UIRenderer`:

```tsx
<A2UIRenderer
  rootId="root"
  components={[...]}
  dataModel={{ "portfolio/kpi": {...}, ... }}
  onAction={handleAction}
/>
```

`renderNode("root", ctx)` starts the traversal:

```
root (Column)
 ├── kpi  (PortfolioKPI)   → reads dataModel["portfolio/kpi"]
 ├── pie  (PieChart)       → reads dataModel["chart/slices/sector"]
 └── table (PositionsTable)→ reads dataModel["positions/rows"]
```

`resolveBinding()` unwraps data bindings and `{literalString: "..."}` wrappers recursively, so component props always receive plain JS values.

**Result on screen:**

```
┌─────────────────────────────────────────────────┐
│  MTM $142,500  │  P&L +$8,320  │  5 positions   │
├─────────────────────────────────────────────────┤
│         Pie chart: sector allocation            │
├─────────────────────────────────────────────────┤
│  AAPL  │  50  │  $185.20  │  Technology  │ +12% │
│  MSFT  │  30  │  $310.00  │  Technology  │  +8% │
│  ...                                            │
└─────────────────────────────────────────────────┘
```

---

## Example 2 — Follow-up Prompt: "Now show PnL by symbol as a bar chart"

The conversation history now includes the previous exchange. The backend sends the full history to the LLM on the next call.

### What changes vs. Example 1

**LLM output** — a new surface (different `surfaceId`) with a BarChart:

```
{"beginRendering": {"surfaceId": "bars-456", "root": "root", ...}}
{"surfaceUpdate": {"surfaceId": "bars-456", "components": [
  {"id": "root", "component": {"Column": {"children": {"explicitList": ["chart"]}}}},
  {"id": "chart", "component": {"BarChart": {
    "dataBinding": "/chart/bars/symbol",
    "xKey": "group_key",
    "bars": [{"key": "total_pnl_reporting", "label": "P&L", "color": "#10b981"}],
    "layout": "horizontal",
    "height": 400
  }}}
]}}
{"dataModelUpdate": {"surfaceId": "bars-456", "contents": [
  {"key": "chart/bars/symbol", "valueString": "__hydrate__"}
]}}
```

**Hydration** — the parameterised path `/chart/bars/symbol` maps to:

```python
# hydrator.py — hydrate("chart/bars/symbol")
_hydrate_summary_groups("symbol")
# → runs: qfi-summary show --group-by symbol --json
# → returns flat array: [{"group_key": "AAPL", "total_pnl_reporting": 4200, ...}, ...]
```

**Store update** — `addOrUpdateSurface` is called with `id: "bars-456"`. Because this is a new `id`, a new entry is prepended to the `surfaces` array and `activeSurfaceId` flips to `"bars-456"`. The previous portfolio surface (`abc-123`) is preserved in history.

**Surface Panel** swaps to the new surface immediately — the bar chart renders with the correct P&L values instead of MTM.

---

## Example 3 — Refinement: "Make it vertical instead"

The LLM sees the prior message "Now show PnL by symbol as a bar chart" and the assistant reply in context. It can either:

- **Reuse the same `surface_id`** — `addOrUpdateSurface` finds the existing entry by id and replaces it in-place. The Surface Panel re-renders the same slot with new props (`layout: "vertical"`).
- **Emit a new `surface_id`** — a new entry is added and becomes active, leaving the horizontal version in history.

The backend assigns `surface_id` from `request.surface_id` if provided by the client, otherwise generates a new UUID. The frontend always sends the current `surfaceId` back in follow-up calls (future enhancement).

---

## Data Flow Summary

```
User types prompt
       │
       ▼
ChatPanel.handleSend()
  │  Builds full conversation history
  │  Calls streamChatV2(messages)
  │
  ▼
POST /chat  ──SSE──►  event: thinking  →  ChatPanel shows "Thinking..."
  │
  ├─ llm.chat()  [thread executor]
  │    └─ Sends system prompt + history to LLM (Ollama / Claude / Gemini)
  │    └─ LLM returns A2UI JSON lines
  │
  ├─ _parse_a2ui_lines()   strips markdown fences, extracts JSON objects
  ├─ _reassemble()         tolerates malformed output (missing wrappers, bare components)
  │
  ├─ hydrate_all(paths)   ──SSE──►  event: thinking  →  "Fetching portfolio data..."
  │    └─ runs qfi-* CLI tools, returns real data
  │
  └─ stream messages ──SSE──►  event: a2ui  (3 messages: begin / surfaceUpdate / dataModelUpdate)
                    ──SSE──►  event: done

       │
       ▼
ChatPanel event loop
  │  Collects: surfaceId, rootId, components[], dataModel{}
  │  On done: calls addOrUpdateSurface(entry)
  │
  ▼
Zustand surface store
  │  Upserts entry, sets activeSurfaceId
  │
  ▼
SurfacePanel re-renders
  │  Passes rootId + components + dataModel to A2UIRenderer
  │
  ▼
A2UIRenderer.renderNode(rootId)
  │  Walks component tree recursively
  │  resolveBinding() unwraps dataBinding and {literalString} props
  │  Renders custom components (BarChart, PieChart, PositionsTable, …)
  │
  ▼
Live UI appears in the centre panel
```

---

## Key Files

| File | Role |
|---|---|
| `a2ui-frontend/src/panels/ChatPanel.tsx` | Input, SSE event loop, calls `addOrUpdateSurface` |
| `a2ui-frontend/src/panels/SurfacePanel.tsx` | Reads active surface from store, renders via A2UIRenderer |
| `a2ui-frontend/src/renderer/A2UIRenderer.tsx` | Walks component tree, resolves data bindings |
| `a2ui-frontend/src/store/surfaces.ts` | Zustand store — persists surfaces across reloads |
| `a2ui-backend/app/routers/chat.py` | SSE endpoint, LLM call, `_reassemble()`, hydration |
| `a2ui-backend/app/services/hydrator.py` | Maps data paths to CLI tool calls |
| `a2ui-backend/app/services/llm.py` | Dispatches to Ollama / Claude / Gemini / LM Studio |
| `backend/skills/a2ui_components.md` | System prompt — teaches the LLM the A2UI protocol |
