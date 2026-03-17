const API_BASE = "http://localhost:10201";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface SurfaceRecord {
  id: string;
  title: string;
  snapshot: string;
  created_at: string;
}

// ── Chat (SSE) ────────────────────────────────────────────────────────────────

export type SSEEvent =
  | { type: "thinking"; status: string }
  | { type: "a2ui"; message: object }
  | { type: "text"; content: string }
  | { type: "error"; message: string }
  | { type: "done"; surface_id?: string };

export async function* streamChat(
  messages: ChatMessage[],
  surfaceId?: string
): AsyncGenerator<SSEEvent> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, surface_id: surfaceId }),
  });

  if (!response.ok || !response.body) {
    yield { type: "error", message: `HTTP ${response.status}` };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("event:")) {
        // handled by next data line — skip
      } else if (line.startsWith("data:")) {
        const raw = line.slice(5).trim();
        try {
          const parsed = JSON.parse(raw);
          // Determine event type from the previous "event:" line or infer from content
          if (parsed.status !== undefined && !parsed.surface_id) {
            yield { type: "thinking", status: parsed.status };
          } else if (parsed.surface_id !== undefined || parsed.status === "complete") {
            yield { type: "done", surface_id: parsed.surface_id };
          } else if (parsed.content !== undefined) {
            yield { type: "text", content: parsed.content };
          } else if (parsed.message !== undefined && typeof parsed.message === "string" && Object.keys(parsed).length <= 2) {
            yield { type: "error", message: parsed.message };
          } else {
            yield { type: "a2ui", message: parsed };
          }
        } catch {
          // not JSON, skip
        }
      }
    }
  }
}

// Better SSE parser that tracks event type
export async function* streamChatV2(
  messages: ChatMessage[],
  surfaceId?: string
): AsyncGenerator<SSEEvent> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, surface_id: surfaceId }),
  });

  if (!response.ok || !response.body) {
    yield { type: "error", message: `HTTP ${response.status}` };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("event:")) {
        currentEvent = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        const raw = line.slice(5).trim();
        try {
          const data = JSON.parse(raw);
          switch (currentEvent) {
            case "thinking":
              yield { type: "thinking", status: data.status ?? "" };
              break;
            case "a2ui":
              yield { type: "a2ui", message: data };
              break;
            case "text":
              yield { type: "text", content: data.content ?? "" };
              break;
            case "error":
              yield { type: "error", message: data.message ?? "" };
              break;
            case "done":
              yield { type: "done", surface_id: data.surface_id };
              break;
          }
          currentEvent = "";
        } catch {
          // skip
        }
      }
    }
  }
}

// ── Actions ───────────────────────────────────────────────────────────────────

export async function sendAction(
  surfaceId: string,
  name: string,
  context: Record<string, unknown>,
  conversation: ChatMessage[]
): Promise<{ ok: boolean; llm_response?: string; error?: string }> {
  const res = await fetch(`${API_BASE}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ surface_id: surfaceId, name, context, conversation }),
  });
  return res.json();
}

// ── Surface history ───────────────────────────────────────────────────────────

export async function getSurfaces(): Promise<SurfaceRecord[]> {
  const res = await fetch(`${API_BASE}/surfaces`);
  if (!res.ok) return [];
  return res.json();
}

export async function saveSurface(
  id: string,
  title: string,
  snapshot: string
): Promise<SurfaceRecord | null> {
  const res = await fetch(`${API_BASE}/surfaces`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, title, snapshot }),
  });
  return res.ok ? res.json() : null;
}

export async function deleteSurface(id: string): Promise<void> {
  await fetch(`${API_BASE}/surfaces/${id}`, { method: "DELETE" });
}
