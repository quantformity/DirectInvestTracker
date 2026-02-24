import { useState, useEffect } from "react";
import { api, type OllamaSettings, type AIProvider } from "../api/client";

interface Props {
  onClose: () => void;
}

const PROVIDERS: { id: AIProvider; label: string; description: string }[] = [
  { id: "ollama",   label: "Ollama",    description: "Local / self-hosted" },
  { id: "lmstudio", label: "LM Studio", description: "OpenAI-compatible" },
  { id: "llamacpp", label: "llama.cpp", description: "Local server" },
  { id: "gemini",   label: "Gemini",    description: "Google AI" },
  { id: "claude",   label: "Claude",    description: "Anthropic" },
];

const GEMINI_MODELS = [
  "gemini-2.0-flash",
  "gemini-2.0-flash-thinking-exp",
  "gemini-1.5-flash",
  "gemini-1.5-pro",
];

const CLAUDE_MODELS = [
  "claude-3-5-haiku-20241022",
  "claude-3-5-sonnet-20241022",
  "claude-3-7-sonnet-20250219",
  "claude-haiku-4-5-20251001",
  "claude-sonnet-4-6",
  "claude-opus-4-6",
];

const EMPTY_SETTINGS: OllamaSettings = {
  ai_provider: "ollama",
  ollama_base_url: "",
  ollama_model: "",
  ollama_code_model: "",
  lmstudio_base_url: "http://localhost:1234/v1",
  lmstudio_model: "",
  lmstudio_code_model: "",
  gemini_api_key: "",
  gemini_model: "gemini-2.0-flash",
  gemini_code_model: "gemini-2.0-flash",
  claude_api_key: "",
  claude_model: "claude-3-5-haiku-20241022",
  claude_code_model: "claude-3-5-haiku-20241022",
  llamacpp_base_url: "http://localhost:8080/v1",
  llamacpp_model: "",
  llamacpp_code_model: "",
  history_cache_path: "",
};

// ── URL helpers ───────────────────────────────────────────────────────────────

function splitUrl(url: string): { host: string; port: string } {
  try {
    const u = new URL(url);
    return { host: `${u.protocol}//${u.hostname}`, port: u.port };
  } catch {
    return { host: url, port: "" };
  }
}

/** Combine host + port (+ optional fixed suffix) into a full URL. */
function assembleUrl(host: string, port: string, suffix = ""): string {
  const h = host.replace(/\/+$/, "");
  return port ? `${h}:${port}${suffix}` : `${h}${suffix}`;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function OllamaSettingsModal({ onClose }: Props) {
  const [form, setForm]             = useState<OllamaSettings>(EMPTY_SETTINGS);
  const [localModels, setLocalModels] = useState<string[]>([]);
  const [probeError, setProbeError] = useState<string | null>(null);
  const [probing, setProbing]       = useState(false);
  const [saving, setSaving]         = useState(false);
  const [saved, setSaved]           = useState(false);
  const [loadError, setLoadError]   = useState("");

  // Split host / port state for local providers
  const [ollamaHost, setOllamaHost] = useState("http://192.168.0.117");
  const [ollamaPort, setOllamaPort] = useState("11434");
  const [lmHost, setLmHost]         = useState("http://localhost");
  const [lmPort, setLmPort]         = useState("1234");
  const [llamacppHost, setLlamacppHost] = useState("http://localhost");
  const [llamacppPort, setLlamacppPort] = useState("8080");

  const provider = form.ai_provider;

  // Database path (Electron only)
  const hasElectron = !!window.electronAPI?.db;
  const [dbPath, setDbPath]               = useState("");
  const [pendingDbPath, setPendingDbPath] = useState<string | null>(null);
  const [relaunching, setRelaunching]     = useState(false);

  useEffect(() => {
    api.getSettings()
      .then((s) => {
        // Parse stored URLs into host + port
        const ollama = splitUrl(s.ollama_base_url || "http://192.168.0.117:11434");
        setOllamaHost(ollama.host);
        setOllamaPort(ollama.port || "11434");

        // LM Studio: strip the /v1 suffix before splitting
        const lmRaw = (s.lmstudio_base_url || "http://localhost:1234/v1").replace(/\/v1\/?$/, "");
        const lm = splitUrl(lmRaw);
        setLmHost(lm.host);
        setLmPort(lm.port || "1234");

        // llama.cpp: strip the /v1 suffix before splitting
        const llamacppRaw = (s.llamacpp_base_url || "http://localhost:8080/v1").replace(/\/v1\/?$/, "");
        const llamacpp = splitUrl(llamacppRaw);
        setLlamacppHost(llamacpp.host);
        setLlamacppPort(llamacpp.port || "8080");

        setForm(s);
      })
      .catch(() => setLoadError("Could not load settings from backend."));

    if (hasElectron) {
      window.electronAPI!.db.getPath().then(setDbPath);
    }
  }, [hasElectron]);

  const clearModels = () => { setLocalModels([]); setProbeError(null); };

  // Keep form.ollama_base_url in sync when host/port fields change
  const updateOllamaHost = (v: string) => {
    setOllamaHost(v);
    setForm((f) => ({ ...f, ollama_base_url: assembleUrl(v, ollamaPort) }));
    clearModels();
  };
  const updateOllamaPort = (v: string) => {
    setOllamaPort(v);
    setForm((f) => ({ ...f, ollama_base_url: assembleUrl(ollamaHost, v) }));
    clearModels();
  };

  // Keep form.lmstudio_base_url in sync (always appends /v1)
  const updateLmHost = (v: string) => {
    setLmHost(v);
    setForm((f) => ({ ...f, lmstudio_base_url: assembleUrl(v, lmPort, "/v1") }));
    clearModels();
  };
  const updateLmPort = (v: string) => {
    setLmPort(v);
    setForm((f) => ({ ...f, lmstudio_base_url: assembleUrl(lmHost, v, "/v1") }));
    clearModels();
  };

  // Keep form.llamacpp_base_url in sync (always appends /v1)
  const updateLlamacppHost = (v: string) => {
    setLlamacppHost(v);
    setForm((f) => ({ ...f, llamacpp_base_url: assembleUrl(v, llamacppPort, "/v1") }));
    clearModels();
  };
  const updateLlamacppPort = (v: string) => {
    setLlamacppPort(v);
    setForm((f) => ({ ...f, llamacpp_base_url: assembleUrl(llamacppHost, v, "/v1") }));
    clearModels();
  };

  const handleProbe = async () => {
    setProbing(true);
    clearModels();
    try {
      const result = provider === "llamacpp"
        ? await api.getLlamaCppModels()
        : provider === "lmstudio"
          ? await api.getLmStudioModels()
          : await api.getOllamaModels();
      if (result.error) {
        setProbeError(result.error);
      } else {
        setLocalModels(result.models);
      }
    } catch {
      setProbeError("Request failed — check the address and port, then try again.");
    } finally {
      setProbing(false);
    }
  };

  const handleBrowseDb = async () => {
    const chosen = await window.electronAPI!.db.selectFile();
    if (chosen) setPendingDbPath(chosen);
  };

  const handleApplyDb = async () => {
    if (!pendingDbPath) return;
    setRelaunching(true);
    await window.electronAPI!.db.setPath(pendingDbPath);
    await window.electronAPI!.app.relaunch();
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await api.updateSettings(form);
      setSaved(true);
      setTimeout(() => { setSaved(false); onClose(); }, 800);
    } catch {
      setProbeError("Failed to save settings.");
    } finally {
      setSaving(false);
    }
  };

  const isSaveValid = () => {
    if (provider === "ollama")   return !!(ollamaHost && form.ollama_model && form.ollama_code_model);
    if (provider === "lmstudio") return !!lmHost;
    if (provider === "llamacpp") return !!llamacppHost;
    if (provider === "gemini")   return !!(form.gemini_api_key && form.gemini_model && form.gemini_code_model);
    if (provider === "claude")   return !!(form.claude_api_key && form.claude_model && form.claude_code_model);
    return false;
  };

  // ── Shared field renderers ────────────────────────────────────────────────────

  const textField = (
    label: string,
    value: string,
    onChange: (v: string) => void,
    placeholder = "",
    type: "text" | "password" = "text",
  ) => (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500 placeholder-gray-500"
      />
    </div>
  );

  // Model field — dropdown when models discovered, text otherwise
  const localModelField = (
    label: string,
    value: string,
    onChange: (v: string) => void,
    placeholder = "",
  ) => (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      {localModels.length > 0 ? (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500"
        >
          {!localModels.includes(value) && value && (
            <option value={value}>{value}</option>
          )}
          {localModels.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500 placeholder-gray-500"
        />
      )}
    </div>
  );

  const cloudModelField = (
    label: string,
    value: string,
    onChange: (v: string) => void,
    knownModels: string[],
  ) => (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500"
      >
        {!knownModels.includes(value) && value && (
          <option value={value}>{value}</option>
        )}
        {knownModels.map((m) => <option key={m} value={m}>{m}</option>)}
      </select>
    </div>
  );

  // ── Host + Port + probe row (for local providers) ─────────────────────────────

  const hostPortRow = (
    host: string,
    onHostChange: (v: string) => void,
    port: string,
    onPortChange: (v: string) => void,
    hostPlaceholder: string,
    portPlaceholder: string,
    canProbe: boolean,
  ) => (
    <div className="space-y-2">
      <div className="flex gap-2">
        {/* Host / IP */}
        <div className="flex-1">
          <label className="block text-xs text-gray-400 mb-1">Host / IP</label>
          <input
            type="text"
            value={host}
            onChange={(e) => onHostChange(e.target.value)}
            placeholder={hostPlaceholder}
            className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500 placeholder-gray-500"
          />
        </div>
        {/* Port */}
        <div className="w-24">
          <label className="block text-xs text-gray-400 mb-1">Port</label>
          <input
            type="text"
            value={port}
            onChange={(e) => onPortChange(e.target.value)}
            placeholder={portPlaceholder}
            className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500 placeholder-gray-500"
          />
        </div>
      </div>
      {/* Assembled URL preview + probe button */}
      <div className="flex items-center gap-2">
        <p className="flex-1 text-[11px] text-gray-500 font-mono truncate">
          {(provider === "lmstudio" || provider === "llamacpp")
            ? assembleUrl(host, port, "/v1")
            : assembleUrl(host, port)}
        </p>
        <button
          onClick={handleProbe}
          disabled={probing || !canProbe}
          className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-white rounded-lg text-xs font-medium transition-colors whitespace-nowrap border border-gray-600"
        >
          {probing ? "…" : "Load Models"}
        </button>
      </div>
      {probeError && <p className="text-red-400 text-xs">{probeError}</p>}
      {localModels.length > 0 && (
        <p className="text-green-400 text-xs">✓ {localModels.length} model(s) found — select below</p>
      )}
    </div>
  );

  // ── Provider panels ───────────────────────────────────────────────────────────

  const ollamaPanel = () => (
    <div className="space-y-3">
      {hostPortRow(
        ollamaHost, updateOllamaHost,
        ollamaPort, updateOllamaPort,
        "http://192.168.0.117", "11434",
        !!(ollamaHost),
      )}
      {localModelField("Chat Model", form.ollama_model,
        (v) => setForm((f) => ({ ...f, ollama_model: v })), "glm-4.7-flash:latest")}
      {localModelField("Code / SQL Model", form.ollama_code_model,
        (v) => setForm((f) => ({ ...f, ollama_code_model: v })), "qwen3-coder-next:latest")}
    </div>
  );

  const lmstudioPanel = () => (
    <div className="space-y-3">
      <p className="text-xs text-gray-400">
        Connect to a running LM Studio server with an OpenAI-compatible API.
        The <span className="text-gray-300 font-mono">/v1</span> path is added automatically.
      </p>
      {hostPortRow(
        lmHost, updateLmHost,
        lmPort, updateLmPort,
        "http://localhost", "1234",
        !!(lmHost),
      )}
      {localModelField("Chat Model", form.lmstudio_model,
        (v) => setForm((f) => ({ ...f, lmstudio_model: v })), "Leave blank to use loaded model")}
      {localModelField("Code / SQL Model", form.lmstudio_code_model,
        (v) => setForm((f) => ({ ...f, lmstudio_code_model: v })), "Leave blank to use loaded model")}
    </div>
  );

  const llamacppPanel = () => (
    <div className="space-y-3">
      <p className="text-xs text-gray-400">
        Connect to a running llama.cpp server (<code className="text-gray-300">llama-server</code>).
        The <span className="text-gray-300 font-mono">/v1</span> path is added automatically.
      </p>
      {hostPortRow(
        llamacppHost, updateLlamacppHost,
        llamacppPort, updateLlamacppPort,
        "http://localhost", "8080",
        !!(llamacppHost),
      )}
      {localModelField("Chat Model", form.llamacpp_model,
        (v) => setForm((f) => ({ ...f, llamacpp_model: v })), "Leave blank to use loaded model")}
      {localModelField("Code / SQL Model", form.llamacpp_code_model,
        (v) => setForm((f) => ({ ...f, llamacpp_code_model: v })), "Leave blank to use loaded model")}
    </div>
  );

  const geminiPanel = () => (
    <div className="space-y-3">
      <p className="text-xs text-gray-400">
        Get a free API key at{" "}
        <span className="text-blue-400">aistudio.google.com</span>.
        Uses Google's OpenAI-compatible endpoint — no extra SDK needed.
      </p>
      {textField("API Key", form.gemini_api_key,
        (v) => setForm((f) => ({ ...f, gemini_api_key: v })), "AIza…", "password")}
      {cloudModelField("Chat Model", form.gemini_model,
        (v) => setForm((f) => ({ ...f, gemini_model: v })), GEMINI_MODELS)}
      {cloudModelField("Code / SQL Model", form.gemini_code_model,
        (v) => setForm((f) => ({ ...f, gemini_code_model: v })), GEMINI_MODELS)}
    </div>
  );

  const claudePanel = () => (
    <div className="space-y-3">
      <p className="text-xs text-gray-400">
        Get an API key at{" "}
        <span className="text-blue-400">console.anthropic.com</span>.
        Works with any Claude plan that has API access.
      </p>
      {textField("API Key", form.claude_api_key,
        (v) => setForm((f) => ({ ...f, claude_api_key: v })), "sk-ant-…", "password")}
      {cloudModelField("Chat Model", form.claude_model,
        (v) => setForm((f) => ({ ...f, claude_model: v })), CLAUDE_MODELS)}
      {cloudModelField("Code / SQL Model", form.claude_code_model,
        (v) => setForm((f) => ({ ...f, claude_code_model: v })), CLAUDE_MODELS)}
    </div>
  );

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6">

        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <span className="text-xl">⚙️</span>
            <h2 className="text-white font-semibold text-lg">AI Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {loadError && (
          <div className="mb-4 p-3 bg-red-900/40 border border-red-700 text-red-300 rounded text-sm">
            {loadError}
          </div>
        )}

        {/* Provider tabs */}
        <div className="mb-4">
          <label className="block text-xs text-gray-400 mb-2">AI Provider</label>
          <div className="grid grid-cols-5 gap-1 bg-gray-800 p-1 rounded-lg">
            {PROVIDERS.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setForm((f) => ({ ...f, ai_provider: p.id }));
                  clearModels();
                }}
                className={`py-1.5 rounded-md text-xs font-medium transition-colors text-center ${
                  provider === p.id
                    ? "bg-blue-600 text-white"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                <div>{p.label}</div>
                <div className={`text-[10px] ${provider === p.id ? "text-blue-200" : "text-gray-500"}`}>
                  {p.description}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Provider-specific fields */}
        {provider === "ollama"   && ollamaPanel()}
        {provider === "lmstudio" && lmstudioPanel()}
        {provider === "llamacpp" && llamacppPanel()}
        {provider === "gemini"   && geminiPanel()}
        {provider === "claude"   && claudePanel()}

        {/* Database path (Electron packaged app only) */}
        {hasElectron && (
          <>
            <div className="my-5 border-t border-gray-700" />
            <div className="space-y-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-base">🗄️</span>
                <h3 className="text-white font-semibold text-sm">Database</h3>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1">Current database file</label>
                <p className="text-xs text-gray-300 font-mono bg-gray-800 rounded-lg px-3 py-2 border border-gray-700 break-all">
                  {dbPath || "Loading…"}
                </p>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1">Change location</label>
                <div className="flex gap-2">
                  <p className={`flex-1 text-xs font-mono rounded-lg px-3 py-2 border break-all ${
                    pendingDbPath
                      ? "bg-gray-700 border-blue-500 text-white"
                      : "bg-gray-800 border-gray-700 text-gray-500"
                  }`}>
                    {pendingDbPath ?? "No new location selected"}
                  </p>
                  <button
                    onClick={handleBrowseDb}
                    className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-xs font-medium transition-colors border border-gray-600 whitespace-nowrap"
                  >
                    Browse…
                  </button>
                </div>
              </div>

              {pendingDbPath && pendingDbPath !== dbPath && (
                <button
                  onClick={handleApplyDb}
                  disabled={relaunching}
                  className="w-full px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  {relaunching ? "Restarting…" : "Apply & Restart App"}
                </button>
              )}

              <p className="text-xs text-gray-500">
                The app will restart to load data from the new location. The existing file is not moved or deleted.
              </p>
            </div>
          </>
        )}

        {/* History Cache path */}
        <div className="my-5 border-t border-gray-700" />
        <div className="space-y-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-base">📈</span>
            <h3 className="text-white font-semibold text-sm">History Cache</h3>
          </div>
          {textField(
            "Cache database path (leave blank for default)",
            form.history_cache_path,
            (v) => setForm((f) => ({ ...f, history_cache_path: v })),
            "/path/to/history_cache.db",
          )}
          <p className="text-xs text-gray-500">
            Historical price data is cached locally for instant chart loading. Default location is the same
            directory as the main database. Changes take effect after saving.
          </p>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-white text-sm transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !isSaveValid()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {saved ? "✓ Saved" : saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
