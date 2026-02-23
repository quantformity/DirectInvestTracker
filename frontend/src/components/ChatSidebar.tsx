import { useState, useRef, useEffect } from "react";
import { api, type ChatMessage, type ChartResponse, type ActionPlan } from "../api/client";
import { ChartRenderer } from "./ChartRenderer";

const CHART_KEYWORDS  = /\b(plot|chart|graph|show me|visuali[sz]e|draw)\b/i;
const ACTION_KEYWORDS = /\b(add|buy|purchase|sell|remove|delete|record|deposit|withdraw|dividend)\b/i;

interface Message {
  role: "user" | "assistant";
  content: string;
  chart?: ChartResponse;
  action?: ActionPlan;           // pending action waiting for confirmation
  actionResult?: string;         // final result after execute
  loading?: boolean;
}

interface ChatSidebarProps {
  open: boolean;
  onClose: () => void;
}

export function ChatSidebar({ open, onClose }: ChatSidebarProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hi! I'm your portfolio AI assistant. Ask me anything about your investments, or ask me to make changes — e.g. \"Add 100 AAPL at $200 to my TFSA\" or \"Record a $250 dividend from MSFT in my RRSP\".",
    },
  ]);
  const [input, setInput]     = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef  = useRef<HTMLDivElement>(null);
  const inputRef   = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg, { role: "assistant", content: "", loading: true }]);
    setInput("");
    setLoading(true);

    try {
      const history: ChatMessage[] = messages
        .filter((m) => !m.loading)
        .map((m) => ({ role: m.role, content: m.content }));
      history.push({ role: "user", content: text });

      // ── Action path ───────────────────────────────────────────────────────
      if (ACTION_KEYWORDS.test(text)) {
        const plan = await api.planAction(text);
        if (plan.action !== "none" && plan.description) {
          setMessages((prev) => [
            ...prev.slice(0, -1),
            { role: "assistant", content: plan.description, action: plan },
          ]);
          return;
        }
      }

      // ── Chart path ────────────────────────────────────────────────────────
      if (CHART_KEYWORDS.test(text)) {
        const [chartResp, textResp] = await Promise.all([api.chart(text), api.chat(history)]);
        setMessages((prev) => [
          ...prev.slice(0, -1),
          { role: "assistant", content: textResp.reply, chart: chartResp },
        ]);
        return;
      }

      // ── Regular chat ──────────────────────────────────────────────────────
      const resp = await api.chat(history);
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: "assistant", content: resp.reply },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: "assistant", content: "Error: Could not connect to AI service." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const confirmAction = async (msgIndex: number, plan: ActionPlan) => {
    setMessages((prev) =>
      prev.map((m, i) => i === msgIndex ? { ...m, loading: true, action: undefined } : m)
    );
    try {
      const result = await api.executeAction(plan.action, plan.params);
      setMessages((prev) =>
        prev.map((m, i) =>
          i === msgIndex
            ? { ...m, loading: false, content: result.success ? `✅ ${result.message}` : `❌ ${result.message}`, actionResult: result.message }
            : m
        )
      );
    } catch {
      setMessages((prev) =>
        prev.map((m, i) =>
          i === msgIndex ? { ...m, loading: false, content: "❌ Failed to execute action." } : m
        )
      );
    }
  };

  const cancelAction = (msgIndex: number) => {
    setMessages((prev) =>
      prev.map((m, i) =>
        i === msgIndex ? { ...m, content: "Action cancelled.", action: undefined } : m
      )
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  return (
    <>
      {open && <div className="fixed inset-0 bg-black/40 z-40 lg:hidden" onClick={onClose} />}

      <div className={`fixed right-0 top-0 h-full w-96 bg-gray-900 border-l border-gray-700 z-50 flex flex-col transition-transform duration-300 ${open ? "translate-x-0" : "translate-x-full"}`}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <span className="text-xl">🤖</span>
            <h2 className="font-semibold text-white">AI Assistant</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-1">✕</button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${msg.role === "user" ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-200"}`}>
                {msg.loading ? (
                  <span className="inline-flex gap-1">
                    <span className="animate-bounce">●</span>
                    <span className="animate-bounce" style={{ animationDelay: "0.1s" }}>●</span>
                    <span className="animate-bounce" style={{ animationDelay: "0.2s" }}>●</span>
                  </span>
                ) : (
                  <>
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                    {msg.chart && <ChartRenderer response={msg.chart} />}

                    {/* Action confirmation card */}
                    {msg.action && (
                      <div className="mt-3 border border-amber-600/50 bg-amber-900/20 rounded-lg p-3">
                        <div className="text-xs text-amber-400 font-semibold mb-2 flex items-center gap-1">
                          <span>⚡</span> Confirm Action
                        </div>
                        <p className="text-xs text-gray-300 mb-3">{msg.action.description}</p>
                        <div className="flex gap-2">
                          <button
                            onClick={() => confirmAction(i, msg.action!)}
                            className="flex-1 px-3 py-1.5 bg-green-700 hover:bg-green-600 text-white rounded text-xs font-medium transition-colors"
                          >
                            ✓ Confirm
                          </button>
                          <button
                            onClick={() => cancelAction(i)}
                            className="flex-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded text-xs font-medium transition-colors"
                          >
                            ✗ Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-gray-700">
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask or instruct… (Enter to send)"
              rows={2}
              className="flex-1 bg-gray-800 text-white rounded-lg px-3 py-2 text-sm resize-none border border-gray-600 focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white rounded-lg transition-colors text-sm font-medium"
            >
              Send
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Try: "Add 50 NVDA at $180 to my TFSA" · "Plot my portfolio by category"
          </p>
        </div>
      </div>
    </>
  );
}
