"""
POST /chat — streams A2UI messages from the LLM to the client via SSE.

Flow:
1. Build system prompt from skills files
2. Call LLM with full conversation history
3. Parse LLM output line by line:
   - JSON lines are streamed as A2UI messages
   - dataModelUpdate lines are intercepted: paths are hydrated via CLI tools,
     then the hydrated version is streamed
   - Plain text lines are streamed as a2ui_text events
4. Save completed surface to history
"""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from functools import partial

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db, SurfaceHistory
from app.schemas import ChatRequest
from app.services import llm, skills
from app.services.hydrator import hydrate_all

logger = logging.getLogger(__name__)
router = APIRouter()


def _extract_title(surface_update: dict) -> str:
    """Try to find the title text from a surfaceUpdate message."""
    try:
        components = surface_update.get("surfaceUpdate", {}).get("components", [])
        for comp in components:
            c = comp.get("component", {})
            text_comp = c.get("Text")
            if text_comp:
                literal = text_comp.get("text", {}).get("literalString", "")
                if literal:
                    return literal
    except Exception:
        pass
    return "Untitled Surface"


def _parse_a2ui_lines(raw: str) -> list[dict]:
    """Extract valid JSON objects from LLM output (handles markdown fences)."""
    raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
    messages: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return messages


def _infer_components(paths: list[str], root_id: str) -> list[dict]:
    """
    When the LLM omits surfaceUpdate entirely, infer components from the
    data binding paths declared in dataModelUpdate.
    """
    children: list[dict] = []
    for i, path in enumerate(paths):
        cid = f"inferred-{i}"
        p = path.lstrip("/")
        if p.startswith("chart/bars"):
            children.append({"id": cid, "component": {"BarChart": {
                "dataBinding": f"/{p}", "xKey": "group_key",
                "bars": [{"key": "total_pnl_reporting", "label": "P&L", "color": "#10b981"},
                         {"key": "total_mtm_reporting", "label": "MTM", "color": "#3b82f6"}],
                "layout": "horizontal", "height": 350,
            }}})
        elif p.startswith("chart/slices"):
            children.append({"id": cid, "component": {"PieChart": {
                "dataBinding": f"/{p}", "nameKey": "group_key",
                "valueKey": "total_mtm_reporting", "valuePrefix": "$",
                "showLegend": True, "height": 320,
            }}})
        elif p == "chart/points":
            children.append({"id": cid, "component": {"LineChart": {
                "dataBinding": "/chart/points", "xKey": "date",
                "series": [{"key": "mtm", "label": "MTM", "color": "#3b82f6"}],
                "height": 320,
            }}})
        elif p == "positions/rows":
            children.append({"id": cid, "component": {"PositionsTable": {
                "dataBinding": "/positions/rows", "showPnl": True, "showSector": True,
            }}})
        elif p == "market/quotes":
            children.append({"id": cid, "component": {"MarketQuoteCard": {
                "dataBinding": "/market/quotes", "layout": "grid", "columns": 3,
            }}})
        elif p == "fx/rates":
            children.append({"id": cid, "component": {"FxRateTable": {
                "dataBinding": "/fx/rates", "showTimestamp": True,
            }}})
        elif p == "portfolio/kpi":
            children.append({"id": cid, "component": {"PortfolioKPI": {
                "dataBinding": "/portfolio/kpi",
            }}})

    if not children:
        return []

    root = {
        "id": root_id,
        "component": {"Column": {"children": {"explicitList": [c["id"] for c in children]}}},
    }
    return [root] + children


def _reassemble(messages: list[dict]) -> list[dict]:
    """
    Tolerates malformed LLM output:
    - bare component/content objects not wrapped in surfaceUpdate/dataModelUpdate
    - surfaceUpdate missing entirely (infers components from dataModelUpdate paths)
    - root component ID missing from component list
    """
    has_su  = any("surfaceUpdate"    in m for m in messages)
    has_dmu = any("dataModelUpdate"  in m for m in messages)
    if has_su and has_dmu:
        return messages  # already well-formed

    begin = next((m for m in messages if "beginRendering" in m), None)
    if not begin:
        return messages

    surface_id    = begin["beginRendering"].get("surfaceId", "")
    declared_root = begin["beginRendering"].get("root", "root")

    # bare component: has "id" and "component" keys, no protocol wrapper
    bare_comps    = [m for m in messages if "id" in m and "component" in m
                     and not {"surfaceUpdate","dataModelUpdate","beginRendering"} & m.keys()]
    # bare content item: has "key" and "valueString"
    bare_contents = [m for m in messages if "key" in m and "valueString" in m
                     and "dataModelUpdate" not in m]

    result: list[dict] = [begin]

    # ── surfaceUpdate ──────────────────────────────────────────────────────────
    if has_su:
        result.extend(m for m in messages if "surfaceUpdate" in m)
    elif bare_comps:
        # Wrap loose components
        comp_ids = {c["id"] for c in bare_comps}
        if declared_root not in comp_ids:
            wrapper = {
                "id": declared_root,
                "component": {"Column": {"children": {"explicitList": [c["id"] for c in bare_comps]}}},
            }
            components = [wrapper] + bare_comps
        else:
            components = bare_comps
        result.append({"surfaceUpdate": {"surfaceId": surface_id, "components": components}})
    else:
        # No components at all — infer from dataModelUpdate paths
        dmu = next((m for m in messages if "dataModelUpdate" in m), None)
        paths = []
        if dmu:
            paths = [item["key"] for item in dmu["dataModelUpdate"].get("contents", [])]
        inferred = _infer_components(paths, declared_root)
        if inferred:
            logger.warning("LLM omitted surfaceUpdate — inferred %d component(s) from paths: %s",
                           len(inferred) - 1, paths)
            result.append({"surfaceUpdate": {"surfaceId": surface_id, "components": inferred}})

    # ── dataModelUpdate ────────────────────────────────────────────────────────
    if has_dmu:
        result.extend(m for m in messages if "dataModelUpdate" in m)
    elif bare_contents:
        result.append({"dataModelUpdate": {"surfaceId": surface_id, "contents": bare_contents}})

    return result


async def _stream_chat(request: ChatRequest, db: Session):
    """Generator that yields SSE events."""
    system_prompt = skills.get_system_prompt()
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Call LLM in a thread so the event loop stays unblocked for SSE
    yield {"event": "thinking", "data": json.dumps({"status": "Thinking..."})}

    loop = asyncio.get_event_loop()
    raw_response = await loop.run_in_executor(
        None, partial(llm.chat, messages, system_prompt=system_prompt)
    )

    # ── Debug logging ──────────────────────────────────────────────────────────
    user_msg = messages[-1]["content"] if messages else ""
    logger.info("=== USER ===\n%s", user_msg)
    logger.info("=== LLM RESPONSE ===\n%s", raw_response)
    # ──────────────────────────────────────────────────────────────────────────

    if raw_response.startswith("Error"):
        yield {
            "event": "error",
            "data": json.dumps({"message": raw_response}),
        }
        return

    # Check if response contains A2UI JSON
    a2ui_messages = _reassemble(_parse_a2ui_lines(raw_response))

    if not a2ui_messages:
        # Plain-text conversational response
        yield {
            "event": "text",
            "data": json.dumps({"content": raw_response}),
        }
        yield {"event": "done", "data": json.dumps({"status": "complete"})}
        return

    # Stream A2UI messages, intercepting dataModelUpdate for hydration
    surface_id = request.surface_id or str(uuid.uuid4())
    title = "Untitled Surface"
    surface_update_msg: dict | None = None

    # Collect paths from dataModelUpdate messages
    all_paths: list[str] = []
    for msg in a2ui_messages:
        if "dataModelUpdate" in msg:
            for item in msg["dataModelUpdate"].get("contents", []):
                if item.get("valueString") == "__hydrate__":
                    all_paths.append(item["key"])

    # Hydrate all paths in one pass
    hydrated: dict = {}
    if all_paths:
        yield {"event": "thinking", "data": json.dumps({"status": "Fetching portfolio data..."})}
        hydrated = hydrate_all(all_paths)

    # Stream messages
    for msg in a2ui_messages:
        if "beginRendering" in msg:
            # Ensure surface_id is consistent
            msg["beginRendering"]["surfaceId"] = surface_id
            yield {"event": "a2ui", "data": json.dumps(msg)}

        elif "surfaceUpdate" in msg:
            msg["surfaceUpdate"]["surfaceId"] = surface_id
            surface_update_msg = msg
            title = _extract_title(msg)
            yield {"event": "a2ui", "data": json.dumps(msg)}

        elif "dataModelUpdate" in msg:
            msg["dataModelUpdate"]["surfaceId"] = surface_id
            # Replace __hydrate__ sentinels with real data
            new_contents = []
            for item in msg["dataModelUpdate"].get("contents", []):
                key = item["key"]
                if item.get("valueString") == "__hydrate__" and key in hydrated:
                    new_contents.append({
                        "key": key,
                        "valueString": json.dumps(hydrated[key]),
                    })
                else:
                    new_contents.append(item)
            msg["dataModelUpdate"]["contents"] = new_contents
            yield {"event": "a2ui", "data": json.dumps(msg)}

        else:
            yield {"event": "a2ui", "data": json.dumps(msg)}

    # Save surface to history
    if surface_update_msg is not None:
        snapshot = json.dumps({
            "surfaceId": surface_id,
            "messages": a2ui_messages,
        })
        try:
            existing = db.query(SurfaceHistory).filter(SurfaceHistory.id == surface_id).first()
            if existing:
                existing.title = title
                existing.snapshot = snapshot
            else:
                db.add(SurfaceHistory(
                    id=surface_id,
                    title=title,
                    snapshot=snapshot,
                    created_at=datetime.now(timezone.utc),
                ))
            db.commit()
        except Exception as exc:
            logger.warning("Could not save surface to history: %s", exc)

    yield {"event": "done", "data": json.dumps({"surface_id": surface_id, "status": "complete"})}


@router.post("/chat")
async def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    """Stream A2UI messages from the LLM."""
    return EventSourceResponse(_stream_chat(request, db))
