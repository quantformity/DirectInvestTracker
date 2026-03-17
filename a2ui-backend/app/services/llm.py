"""
LLM service for A2UI backend.
Reads provider config from the shared settings database and calls the appropriate API.
"""
import logging
import requests
from typing import Optional
from app.config import get_llm_config

logger = logging.getLogger(__name__)


def _active_model(cfg: dict) -> str:
    p = cfg["provider"]
    if p == "lmstudio":
        return cfg["lmstudio_model"] or "local-model"
    if p == "gemini":
        return cfg["gemini_model"]
    if p == "claude":
        return cfg["claude_model"]
    return cfg["ollama_model"]


def _chat_ollama(messages: list[dict], model: str, base_url: str) -> str:
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {"model": model, "stream": False, "messages": messages}
    try:
        r = requests.post(url, json=payload, timeout=180)
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Ollama. Make sure it is running."
    except requests.exceptions.Timeout:
        return "Error: Ollama request timed out."
    except Exception as exc:
        logger.error("Ollama error: %s", exc)
        return f"Error: {exc}"


def _chat_openai_compat(
    messages: list[dict], model: str, base_url: str, api_key: str = ""
) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "stream": False, "messages": messages}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=180)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except requests.exceptions.ConnectionError:
        return f"Error: Cannot connect to {base_url}."
    except requests.exceptions.Timeout:
        return "Error: Request timed out."
    except Exception as exc:
        logger.error("OpenAI-compat error: %s", exc)
        return f"Error: {exc}"


def _chat_claude(messages: list[dict], model: str, api_key: str) -> str:
    if not api_key:
        return "Error: Claude API key not configured."
    system_content = ""
    conv: list[dict] = []
    for m in messages:
        if m["role"] == "system":
            system_content = m["content"]
        else:
            conv.append({"role": m["role"], "content": m["content"]})
    if not conv:
        return ""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload: dict = {"model": model, "max_tokens": 8192, "messages": conv}
    if system_content:
        payload["system"] = system_content
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            json=payload, headers=headers, timeout=180,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Anthropic API."
    except requests.exceptions.Timeout:
        return "Error: Anthropic API timed out."
    except Exception as exc:
        logger.error("Claude error: %s", exc)
        return f"Error: {exc}"


def chat(
    messages: list[dict],
    system_prompt: Optional[str] = None,
) -> str:
    """Call the configured LLM and return the response text."""
    cfg = get_llm_config()
    provider = cfg["provider"]
    model = _active_model(cfg)

    full_messages = messages
    if system_prompt:
        full_messages = [{"role": "system", "content": system_prompt}] + messages

    if provider == "ollama":
        return _chat_ollama(full_messages, model, cfg["ollama_base_url"])
    elif provider == "lmstudio":
        return _chat_openai_compat(full_messages, model, cfg["lmstudio_base_url"])
    elif provider == "gemini":
        return _chat_openai_compat(
            full_messages, model,
            "https://generativelanguage.googleapis.com/v1beta/openai",
            cfg["gemini_api_key"],
        )
    elif provider == "claude":
        return _chat_claude(full_messages, model, cfg["claude_api_key"])
    else:
        return f"Error: Unknown AI provider '{provider}'."
