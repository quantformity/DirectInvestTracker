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
import json
import logging
import re
import uuid
from datetime import datetime, timezone

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
    # Strip markdown fences if present
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


async def _stream_chat(request: ChatRequest, db: Session):
    """Generator that yields SSE events."""
    system_prompt = skills.get_system_prompt()
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Call LLM (blocking for now — streaming LLM output is a future enhancement)
    yield {"event": "thinking", "data": json.dumps({"status": "Thinking..."})}

    raw_response = llm.chat(messages, system_prompt=system_prompt)

    if raw_response.startswith("Error"):
        yield {
            "event": "error",
            "data": json.dumps({"message": raw_response}),
        }
        return

    # Check if response contains A2UI JSON
    a2ui_messages = _parse_a2ui_lines(raw_response)

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
