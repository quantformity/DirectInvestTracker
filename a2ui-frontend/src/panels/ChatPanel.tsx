import React, { useState, useRef, useEffect } from "react";
import { streamChatV2, type ChatMessage, type SSEEvent } from "../api/client";
import { useSurfaceStore } from "../store/surfaces";
import type { SurfaceEntry } from "../store/surfaces";
import type { A2UIComponent } from "../renderer/A2UIRenderer";

interface Message {
  role: "user" | "assistant";
  content: string;
  isThinking?: boolean;
}

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [thinkingStatus, setThinkingStatus] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const { addOrUpdateSurface } = useSurfaceStore();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    setThinkingStatus("Thinking...");

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);

    const apiMessages: ChatMessage[] = [...messages, userMsg].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    // Collect A2UI messages to build surface
    let surfaceId = "";
    let rootId = "";
    const components: A2UIComponent[] = [];
    const dataModel: Record<string, unknown> = {};
    let title = "New Surface";
    let surfaceCreated = false;
    let textResponse = "";

    try {
      for await (const event of streamChatV2(apiMessages)) {
        const e = event as SSEEvent;

        if (e.type === "thinking") {
          setThinkingStatus(e.status);
        } else if (e.type === "a2ui") {
          const msg = e.message as Record<string, unknown>;

          if ("beginRendering" in msg) {
            const br = msg.beginRendering as Record<string, unknown>;
            surfaceId = (br.surfaceId as string) || crypto.randomUUID();
            rootId = br.root as string;
          } else if ("surfaceUpdate" in msg) {
            const su = msg.surfaceUpdate as Record<string, unknown>;
            const comps = su.components as A2UIComponent[];
            components.push(...comps);
            // Extract title from first Text component
            for (const comp of comps) {
              const textComp = comp.component?.["Text"];
              if (textComp) {
                const literal = (textComp as Record<string, unknown>)?.text as Record<string, unknown>;
                if (literal?.literalString) {
                  title = String(literal.literalString);
                  break;
                }
              }
            }
          } else if ("dataModelUpdate" in msg) {
            const dmu = msg.dataModelUpdate as Record<string, unknown>;
            const contents = dmu.contents as { key: string; valueString: string }[];
            for (const item of contents) {
              if (item.valueString && item.valueString !== "__hydrate__") {
                try {
                  dataModel[item.key] = JSON.parse(item.valueString);
                } catch {
                  dataModel[item.key] = item.valueString;
                }
              }
            }
          }
        } else if (e.type === "text") {
          textResponse += e.content;
        } else if (e.type === "error") {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `⚠️ ${e.message}` },
          ]);
        } else if (e.type === "done") {
          if (e.surface_id) surfaceId = e.surface_id;
        }
      }

      // If we got a surface, save it
      if (components.length > 0 && surfaceId) {
        const entry: SurfaceEntry = {
          id: surfaceId,
          title,
          rootId,
          components,
          dataModel,
          createdAt: new Date().toISOString(),
        };
        addOrUpdateSurface(entry);
        surfaceCreated = true;
      }

      const assistantContent = textResponse || (surfaceCreated ? `Created surface: **${title}**` : "Done.");
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: assistantContent },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${String(err)}` },
      ]);
    } finally {
      setSending(false);
      setThinkingStatus("");
    }
  };

  return (
    <div className="w-80 flex-shrink-0 bg-slate-900 border-l border-slate-700 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-3 py-3 border-b border-slate-700">
        <h2 className="text-sm font-semibold text-slate-300">QFI AI Advisor</h2>
        <p className="text-xs text-slate-500">Ask about your portfolio</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
        {messages.length === 0 && (
          <div className="text-xs text-slate-600 italic text-center mt-4">
            <p>Try asking:</p>
            <p className="mt-1">"Show my portfolio overview"</p>
            <p>"Show market quotes"</p>
            <p>"Show my positions"</p>
            <p>"Show portfolio history"</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex flex-col gap-0.5 ${m.role === "user" ? "items-end" : "items-start"}`}
          >
            <div
              className={`max-w-[90%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap leading-relaxed ${
                m.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-200 border border-slate-700"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {sending && thinkingStatus && (
          <div className="flex items-start">
            <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-400 animate-pulse">
              {thinkingStatus}
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-slate-700">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask the AI..."
            rows={2}
            disabled={sending}
            className="flex-1 bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 resize-none disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={sending || !input.trim()}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded text-sm font-medium self-end transition-colors"
          >
            {sending ? "..." : "Send"}
          </button>
        </div>
        <p className="text-xs text-slate-600 mt-1">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  );
}
