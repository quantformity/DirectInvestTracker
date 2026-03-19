"""
LLM service for A2UI backend.
Reads provider config from the shared settings database and calls the appropriate API.

Two entry points:
  chat(messages, system_prompt)           — single turn, no tools (backward compat)
  chat_one_turn(messages, system_prompt,  — one turn, returns LLMResponse which may
                tools)                      contain tool_calls for the caller to handle
"""
import json
import logging
import requests
from dataclasses import dataclass, field
from typing import Optional
from app.config import get_llm_config

logger = logging.getLogger(__name__)


# ── Data transfer objects ─────────────────────────────────────────────────────

@dataclass
class ToolCall:
    """A single tool invocation requested by the LLM."""
    id: str
    name: str
    arguments: dict  # already parsed to dict (not a JSON string)


@dataclass
class LLMResponse:
    """
    Result of one LLM turn.

    If tool_calls is non-empty the caller should execute the tools, append the
    results to the conversation, and call chat_one_turn again.

    raw_assistant_message is the assistant turn in OpenAI-format, ready to
    append to the running messages list before adding tool results.
    """
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_assistant_message: dict = field(default_factory=dict)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _active_model(cfg: dict) -> str:
    p = cfg["provider"]
    if p == "lmstudio":
        return cfg["lmstudio_model"] or "local-model"
    if p == "gemini":
        return cfg["gemini_model"]
    if p == "claude":
        return cfg["claude_model"]
    return cfg["ollama_model"]


def _parse_args(raw) -> dict:
    """Parse tool arguments — may arrive as a JSON string or already as a dict."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


# ── OpenAI → Ollama message conversion ───────────────────────────────────────

def _to_ollama_messages(messages: list[dict]) -> list[dict]:
    """
    Convert an OpenAI-format message list to Ollama format.

    Differences:
    - Ollama tool results: {"role": "tool", "content": "..."} — no tool_call_id
    - Ollama tool calls in assistant messages: arguments must be dicts, not JSON strings
    """
    result = []
    for m in messages:
        role = m.get("role", "")
        if role == "tool":
            result.append({"role": "tool", "content": m.get("content", "")})
        elif role == "assistant" and m.get("tool_calls"):
            ollama_tc = []
            for tc in m["tool_calls"]:
                ollama_tc.append({
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": _parse_args(tc["function"]["arguments"]),
                    }
                })
            result.append({
                "role": "assistant",
                "content": m.get("content") or "",
                "tool_calls": ollama_tc,
            })
        else:
            result.append({"role": role, "content": m.get("content", "")})
    return result


# ── OpenAI → Claude message/tool conversion ───────────────────────────────────

def _to_claude_messages(messages: list[dict]) -> list[dict]:
    """
    Convert an OpenAI-format message list to Claude's content-block format.

    Key differences:
    - Claude tool results go inside a "user" message as tool_result content blocks
    - Claude tool calls in assistant messages are tool_use content blocks
    - Consecutive tool results are merged into a single user message
    """
    result = []
    pending_tool_results: list[dict] = []

    def _flush_tool_results():
        if pending_tool_results:
            result.append({"role": "user", "content": list(pending_tool_results)})
            pending_tool_results.clear()

    for m in messages:
        role = m.get("role", "")

        if role == "system":
            continue  # handled separately as payload["system"]

        if role == "tool":
            # Collect — will be flushed into a user message
            pending_tool_results.append({
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id", ""),
                "content": m.get("content", ""),
            })

        elif role == "assistant" and m.get("tool_calls"):
            _flush_tool_results()
            content_blocks = []
            if m.get("content"):
                content_blocks.append({"type": "text", "text": m["content"]})
            for tc in m["tool_calls"]:
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": _parse_args(tc["function"]["arguments"]),
                })
            result.append({"role": "assistant", "content": content_blocks})

        else:
            _flush_tool_results()
            result.append({"role": role, "content": m.get("content", "")})

    _flush_tool_results()
    return result


def _to_claude_tools(openai_tools: list[dict]) -> list[dict]:
    """Convert OpenAI-format tool definitions to Claude format."""
    claude_tools = []
    for t in openai_tools:
        fn = t["function"]
        claude_tools.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return claude_tools


# ── Provider one-turn implementations ────────────────────────────────────────

def _chat_ollama_one_turn(
    messages: list[dict], model: str, base_url: str, tools: Optional[list] = None
) -> LLMResponse:
    url = f"{base_url.rstrip('/')}/api/chat"
    ollama_messages = _to_ollama_messages(messages)
    payload: dict = {"model": model, "stream": True, "messages": ollama_messages}
    if tools:
        payload["tools"] = tools  # Ollama accepts the same OpenAI tool format

    try:
        r = requests.post(url, json=payload, stream=True, timeout=(10, None))
        r.raise_for_status()

        chunks: list[str] = []
        final_tool_calls: list[ToolCall] = []

        for raw_line in r.iter_lines():
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            msg = obj.get("message", {})
            content = msg.get("content", "")
            if content:
                chunks.append(content)

            if obj.get("done"):
                for i, tc in enumerate(msg.get("tool_calls", [])):
                    fn = tc.get("function", {})
                    final_tool_calls.append(ToolCall(
                        id=f"call_{i}",
                        name=fn.get("name", ""),
                        arguments=_parse_args(fn.get("arguments", {})),
                    ))
                break

        if final_tool_calls:
            raw_msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in final_tool_calls
                ],
            }
            return LLMResponse(text="", tool_calls=final_tool_calls, raw_assistant_message=raw_msg)

        text = "".join(chunks)
        return LLMResponse(
            text=text,
            raw_assistant_message={"role": "assistant", "content": text},
        )

    except requests.exceptions.ConnectionError:
        return LLMResponse(text="Error: Cannot connect to Ollama. Make sure it is running.")
    except requests.exceptions.Timeout:
        return LLMResponse(text="Error: Cannot reach Ollama — connection timed out.")
    except Exception as exc:
        logger.error("Ollama error: %s", exc)
        return LLMResponse(text=f"Error: {exc}")


def _chat_openai_compat_one_turn(
    messages: list[dict],
    model: str,
    base_url: str,
    api_key: str = "",
    tools: Optional[list] = None,
) -> LLMResponse:
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict = {"model": model, "stream": False, "messages": messages}
    if tools:
        payload["tools"] = tools

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=180)
        r.raise_for_status()

        choice = r.json()["choices"][0]
        msg = choice["message"]
        finish_reason = choice.get("finish_reason", "")

        if finish_reason == "tool_calls" or msg.get("tool_calls"):
            tool_calls = []
            for tc in msg.get("tool_calls", []):
                tool_calls.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=_parse_args(tc["function"]["arguments"]),
                ))
            # Keep the assistant message in original OpenAI format
            raw_msg = {
                "role": "assistant",
                "content": msg.get("content"),
                "tool_calls": msg["tool_calls"],
            }
            return LLMResponse(text="", tool_calls=tool_calls, raw_assistant_message=raw_msg)

        text = msg.get("content", "")
        return LLMResponse(
            text=text,
            raw_assistant_message={"role": "assistant", "content": text},
        )

    except requests.exceptions.ConnectionError:
        return LLMResponse(text=f"Error: Cannot connect to {base_url}.")
    except requests.exceptions.Timeout:
        return LLMResponse(text="Error: Request timed out.")
    except Exception as exc:
        logger.error("OpenAI-compat error: %s", exc)
        return LLMResponse(text=f"Error: {exc}")


def _chat_claude_one_turn(
    messages: list[dict],
    model: str,
    api_key: str,
    system_content: str = "",
    tools: Optional[list] = None,
) -> LLMResponse:
    if not api_key:
        return LLMResponse(text="Error: Claude API key not configured.")

    claude_messages = _to_claude_messages(messages)
    if not claude_messages:
        return LLMResponse(text="")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload: dict = {"model": model, "max_tokens": 8192, "messages": claude_messages}
    if system_content:
        payload["system"] = system_content
    if tools:
        payload["tools"] = _to_claude_tools(tools)

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            json=payload, headers=headers, timeout=180,
        )
        r.raise_for_status()
        data = r.json()

        stop_reason = data.get("stop_reason")
        content_blocks = data.get("content", [])

        if stop_reason == "tool_use":
            tool_calls = []
            for block in content_blocks:
                if block.get("type") == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block["id"],
                        name=block["name"],
                        arguments=block.get("input", {}),
                    ))
            raw_msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in tool_calls
                ],
            }
            return LLMResponse(text="", tool_calls=tool_calls, raw_assistant_message=raw_msg)

        text = next(
            (b["text"] for b in content_blocks if b.get("type") == "text"), ""
        )
        return LLMResponse(
            text=text,
            raw_assistant_message={"role": "assistant", "content": text},
        )

    except requests.exceptions.ConnectionError:
        return LLMResponse(text="Error: Cannot connect to Anthropic API.")
    except requests.exceptions.Timeout:
        return LLMResponse(text="Error: Anthropic API timed out.")
    except Exception as exc:
        logger.error("Claude error: %s", exc)
        return LLMResponse(text=f"Error: {exc}")


# ── Public API ────────────────────────────────────────────────────────────────

def chat_one_turn(
    messages: list[dict],
    system_prompt: Optional[str] = None,
    tools: Optional[list] = None,
) -> LLMResponse:
    """
    Make a single LLM call and return a structured LLMResponse.

    If the response contains tool_calls, the caller should:
      1. Append response.raw_assistant_message to messages
      2. Execute each tool call
      3. Append tool result messages (role="tool") to messages
      4. Call chat_one_turn again with the updated messages

    Messages should be in OpenAI format (role + content).
    Tool definitions should be in OpenAI function-calling format.
    """
    cfg = get_llm_config()
    provider = cfg["provider"]
    model = _active_model(cfg)

    # Prepend system message if not already present
    full_messages = list(messages)
    if system_prompt:
        if not full_messages or full_messages[0].get("role") != "system":
            full_messages = [{"role": "system", "content": system_prompt}] + full_messages

    if provider == "ollama":
        return _chat_ollama_one_turn(full_messages, model, cfg["ollama_base_url"], tools)

    if provider == "lmstudio":
        return _chat_openai_compat_one_turn(
            full_messages, model, cfg["lmstudio_base_url"], tools=tools
        )

    if provider == "gemini":
        return _chat_openai_compat_one_turn(
            full_messages, model,
            "https://generativelanguage.googleapis.com/v1beta/openai",
            cfg["gemini_api_key"], tools=tools,
        )

    if provider == "claude":
        # Extract system message — Claude takes it separately
        system = ""
        conv: list[dict] = []
        for m in full_messages:
            if m.get("role") == "system":
                system = m["content"]
            else:
                conv.append(m)
        return _chat_claude_one_turn(conv, model, cfg["claude_api_key"], system, tools)

    return LLMResponse(text=f"Error: Unknown AI provider '{provider}'.")


def chat(
    messages: list[dict],
    system_prompt: Optional[str] = None,
) -> str:
    """
    Single-turn convenience wrapper — returns the response text directly.
    Backward-compatible with the original API; does not support tool calling.
    """
    return chat_one_turn(messages, system_prompt=system_prompt, tools=None).text
