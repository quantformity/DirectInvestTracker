import { useState, useRef, useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import quantformityIcon from "/QuantformityIconNoText.png";
import { api, type ChatMessage, type ChartResponse, type ActionPlan } from "../api/client";
import { ChartRenderer } from "./ChartRenderer";
import { OllamaSettingsModal } from "./OllamaSettingsModal";

const NAV_ITEMS = [
  { to: "/", label: "Position Manager", icon: "📝", end: true },
  { to: "/positions", label: "Position List", icon: "📊" },
  { to: "/summary", label: "Summary", icon: "📈" },
  { to: "/market", label: "Market Insights", icon: "💹" },
  { to: "/history", label: "History", icon: "📅" },
  { to: "/sector", label: "Sector", icon: "🗂️" },
  { to: "/fx", label: "FX Rates", icon: "💱" },
  { to: "/report", label: "Report", icon: "📄" },
];

const CHART_KEYWORDS  = /\b(plot|chart|graph|show me|visuali[sz]e|draw)\b/i;
const ACTION_KEYWORDS = /\b(add|buy|purchase|sell|remove|delete|record|deposit|withdraw|dividend|create|update|rename|edit|modify|change|refresh|set)\b/i;

interface PendingSQL {
  sql: string;
  question: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  chart?: ChartResponse;
  action?: ActionPlan;
  pendingSql?: PendingSQL;
  loading?: boolean;
}

export function Layout() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hi! Ask me about your portfolio or say \"Add 100 AAPL at $200 to my TFSA\".",
    },
  ]);
  const [input, setInput]     = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Listen for File > Settings menu event (Electron only)
  useEffect(() => {
    const handler = () => setSettingsOpen(true);
    window.electronAPI?.app.onOpenSettings(handler);
    return () => window.electronAPI?.app.removeOpenSettingsListener(handler);
  }, []);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "", loading: true },
    ]);
    setInput("");
    setLoading(true);

    try {
      const history: ChatMessage[] = messages
        .filter((m) => !m.loading)
        .map((m) => ({ role: m.role, content: m.content }));
      history.push({ role: "user", content: text });

      // ── Action path ────────────────────────────────────────────────────────
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

      // ── Chart path ─────────────────────────────────────────────────────────
      if (CHART_KEYWORDS.test(text)) {
        const [chartResp, textResp] = await Promise.all([api.chart(text), api.chat(history)]);
        setMessages((prev) => [
          ...prev.slice(0, -1),
          { role: "assistant", content: textResp.reply, chart: chartResp },
        ]);
        return;
      }

      // ── Regular chat ───────────────────────────────────────────────────────
      const resp = await api.chat(history);
      if (resp.pending_sql) {
        setMessages((prev) => [
          ...prev.slice(0, -1),
          {
            role: "assistant",
            content: resp.reply,
            pendingSql: { sql: resp.pending_sql!, question: text },
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev.slice(0, -1),
          { role: "assistant", content: resp.reply },
        ]);
      }
    } catch (err: unknown) {
      const isTimeout =
        typeof err === "object" && err !== null && "code" in err && err.code === "ECONNABORTED";
      const msg = isTimeout
        ? "⏱ Request timed out — the model may be loading or overloaded. Try again in a moment."
        : "❌ Could not reach the AI service. Check the backend is running and verify AI Settings.";
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: "assistant", content: msg },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const confirmAction = async (msgIndex: number, plan: ActionPlan) => {
    setMessages((prev) =>
      prev.map((m, i) => (i === msgIndex ? { ...m, loading: true, action: undefined } : m))
    );
    try {
      const result = await api.executeAction(plan.action, plan.params);
      setMessages((prev) =>
        prev.map((m, i) =>
          i === msgIndex
            ? {
                ...m,
                loading: false,
                content: result.success ? `✅ ${result.message}` : `❌ ${result.message}`,
              }
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

  const runSQL = async (msgIndex: number, pending: PendingSQL) => {
    setMessages((prev) =>
      prev.map((m, i) => (i === msgIndex ? { ...m, loading: true, pendingSql: undefined } : m))
    );
    try {
      const result = await api.executeSQL(pending.sql, pending.question);
      setMessages((prev) =>
        prev.map((m, i) =>
          i === msgIndex ? { ...m, loading: false, content: result.reply } : m
        )
      );
    } catch {
      setMessages((prev) =>
        prev.map((m, i) =>
          i === msgIndex ? { ...m, loading: false, content: "❌ Failed to execute query." } : m
        )
      );
    }
  };

  const dismissSQL = (msgIndex: number) => {
    setMessages((prev) =>
      prev.map((m, i) =>
        i === msgIndex ? { ...m, pendingSql: undefined } : m
      )
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      {/* Sidebar */}
      <nav className="w-72 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
        {/* Logo */}
        <div className="p-4 border-b border-gray-800 shrink-0">
          <div className="flex flex-col items-center gap-1.5">
            <img src={quantformityIcon} alt="Direct Invest Tracker" className="w-12 h-12 object-contain" />
            <div className="text-white text-xs font-semibold text-center leading-tight">
              Direct Invest Tracker
            </div>
            <div className="text-gray-500 text-[10px]">v{__APP_VERSION__}</div>
          </div>
        </div>

        {/* Nav links */}
        <div className="p-3 space-y-1 shrink-0">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-blue-600 text-white font-medium"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`
              }
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}

          {/* Settings */}
          <div className="border-t border-gray-800 mt-1 pt-1">
            <button
              onClick={() => setSettingsOpen(true)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm w-full text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span>Settings</span>
            </button>
          </div>
        </div>

        {/* AI Chat — fills remaining sidebar height */}
        <div className="flex flex-col flex-1 min-h-0 border-t border-gray-800">
          {/* Chat header */}
          <div className="px-4 py-2.5 flex items-center gap-2 shrink-0 border-b border-gray-800">
            <span className="text-base">🤖</span>
            <span className="text-sm font-semibold text-white">AI Assistant</span>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[90%] rounded-lg px-2.5 py-1.5 text-xs leading-relaxed ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-800 text-gray-200"
                  }`}
                >
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

                      {msg.action && (
                        <div className="mt-2 border border-amber-600/50 bg-amber-900/20 rounded-lg p-2">
                          <div className="text-xs text-amber-400 font-semibold mb-1 flex items-center gap-1">
                            <span>⚡</span> Confirm Action
                          </div>
                          <p className="text-xs text-gray-300 mb-2">{msg.action.description}</p>
                          <div className="flex gap-1.5">
                            <button
                              onClick={() => confirmAction(i, msg.action!)}
                              className="flex-1 px-2 py-1 bg-green-700 hover:bg-green-600 text-white rounded text-xs font-medium transition-colors"
                            >
                              ✓ Confirm
                            </button>
                            <button
                              onClick={() => cancelAction(i)}
                              className="flex-1 px-2 py-1 bg-gray-700 hover:bg-gray-600 text-white rounded text-xs font-medium transition-colors"
                            >
                              ✗ Cancel
                            </button>
                          </div>
                        </div>
                      )}

                      {msg.pendingSql && (
                        <div className="mt-2 border border-blue-600/50 bg-blue-900/20 rounded-lg p-2">
                          <div className="text-xs text-blue-400 font-semibold mb-1 flex items-center gap-1">
                            <span>🔍</span> SQL Query
                          </div>
                          <pre className="text-xs text-gray-300 bg-gray-900/60 rounded p-2 overflow-x-auto whitespace-pre-wrap mb-2 font-mono leading-relaxed">
                            {msg.pendingSql.sql}
                          </pre>
                          <div className="flex gap-1.5">
                            <button
                              onClick={() => runSQL(i, msg.pendingSql!)}
                              className="flex-1 px-2 py-1 bg-blue-700 hover:bg-blue-600 text-white rounded text-xs font-medium transition-colors"
                            >
                              ▶ Run Query
                            </button>
                            <button
                              onClick={() => dismissSQL(i)}
                              className="flex-1 px-2 py-1 bg-gray-700 hover:bg-gray-600 text-white rounded text-xs font-medium transition-colors"
                            >
                              ✗ Dismiss
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
          <div className="p-3 border-t border-gray-800 shrink-0">
            <div className="flex gap-1.5">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask or instruct…"
                rows={2}
                className="flex-1 bg-gray-800 text-white rounded-lg px-2.5 py-1.5 text-xs resize-none border border-gray-700 focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white rounded-lg transition-colors text-xs font-medium self-end"
              >
                Send
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>

      {settingsOpen && <OllamaSettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
