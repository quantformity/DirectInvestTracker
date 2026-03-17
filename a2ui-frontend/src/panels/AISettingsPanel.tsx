import React, { useState, useEffect } from "react";
import { settingsApi, EMPTY_SETTINGS, type AISettings, type AIProvider } from "../api/settings";

const PROVIDERS: { id: AIProvider; label: string; sub: string }[] = [
  { id: "ollama",   label: "Ollama",    sub: "Local" },
  { id: "lmstudio", label: "LM Studio", sub: "Local" },
  { id: "llamacpp", label: "llama.cpp", sub: "Local" },
  { id: "gemini",   label: "Gemini",    sub: "Google" },
  { id: "claude",   label: "Claude",    sub: "Anthropic" },
];

const GEMINI_MODELS = [
  "gemini-2.0-flash", "gemini-2.0-flash-thinking-exp",
  "gemini-1.5-flash", "gemini-1.5-pro",
];

const CLAUDE_MODELS = [
  "claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022",
  "claude-3-7-sonnet-20250219", "claude-haiku-4-5-20251001",
  "claude-sonnet-4-6", "claude-opus-4-6",
];

function splitUrl(url: string) {
  try {
    const u = new URL(url);
    return { host: `${u.protocol}//${u.hostname}`, port: u.port };
  } catch {
    return { host: url, port: "" };
  }
}

function assembleUrl(host: string, port: string, suffix = "") {
  const h = host.replace(/\/+$/, "");
  return port ? `${h}:${port}${suffix}` : `${h}${suffix}`;
}

// ── Shared field components ────────────────────────────────────────────────────

function Field({
  label, value, onChange, placeholder = "", type = "text",
}: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: "text" | "password";
}) {
  return (
    <div>
      <label className="block text-xs text-slate-400 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-slate-700 text-slate-100 rounded px-2.5 py-1.5 text-xs border border-slate-600 focus:outline-none focus:border-blue-500 placeholder-slate-500"
      />
    </div>
  );
}

function ModelSelect({
  label, value, onChange, options, placeholder = "",
}: {
  label: string; value: string; onChange: (v: string) => void;
  options: string[]; placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs text-slate-400 mb-1">{label}</label>
      {options.length > 0 ? (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-slate-700 text-slate-100 rounded px-2.5 py-1.5 text-xs border border-slate-600 focus:outline-none focus:border-blue-500"
        >
          {!options.includes(value) && value && <option value={value}>{value}</option>}
          {options.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full bg-slate-700 text-slate-100 rounded px-2.5 py-1.5 text-xs border border-slate-600 focus:outline-none focus:border-blue-500 placeholder-slate-500"
        />
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function AISettingsPanel() {
  const [form, setForm]           = useState<AISettings>(EMPTY_SETTINGS);
  const [localModels, setLocalModels] = useState<string[]>([]);
  const [probeError, setProbeError]   = useState<string | null>(null);
  const [probing, setProbing]         = useState(false);
  const [saving, setSaving]           = useState(false);
  const [saveState, setSaveState]     = useState<"idle" | "saved" | "error">("idle");
  const [loadError, setLoadError]     = useState("");

  const [ollamaHost, setOllamaHost]     = useState("");
  const [ollamaPort, setOllamaPort]     = useState("");
  const [lmHost, setLmHost]             = useState("");
  const [lmPort, setLmPort]             = useState("");
  const [llamacppHost, setLlamacppHost] = useState("");
  const [llamacppPort, setLlamacppPort] = useState("");

  const provider = form.ai_provider;

  useEffect(() => {
    settingsApi.getSettings()
      .then((s) => {
        const ollamaU = splitUrl(s.ollama_base_url);
        setOllamaHost(ollamaU.host);
        setOllamaPort(ollamaU.port);

        const lmRaw = s.lmstudio_base_url.replace(/\/v1\/?$/, "");
        const lmU = splitUrl(lmRaw);
        setLmHost(lmU.host);
        setLmPort(lmU.port);

        const llamacppRaw = s.llamacpp_base_url.replace(/\/v1\/?$/, "");
        const llamacppU = splitUrl(llamacppRaw);
        setLlamacppHost(llamacppU.host);
        setLlamacppPort(llamacppU.port);

        setForm(s);
      })
      .catch(() => setLoadError("Cannot reach A2UI backend on :10201 — run scripts/dev-a2ui.sh first."));
  }, []);

  const clearModels = () => { setLocalModels([]); setProbeError(null); };

  const updateOllamaHost = (v: string) => { setOllamaHost(v); setForm((f) => ({ ...f, ollama_base_url: assembleUrl(v, ollamaPort) })); clearModels(); };
  const updateOllamaPort = (v: string) => { setOllamaPort(v); setForm((f) => ({ ...f, ollama_base_url: assembleUrl(ollamaHost, v) })); clearModels(); };
  const updateLmHost     = (v: string) => { setLmHost(v);     setForm((f) => ({ ...f, lmstudio_base_url: assembleUrl(v, lmPort, "/v1") })); clearModels(); };
  const updateLmPort     = (v: string) => { setLmPort(v);     setForm((f) => ({ ...f, lmstudio_base_url: assembleUrl(lmHost, v, "/v1") })); clearModels(); };
  const updateLlHost     = (v: string) => { setLlamacppHost(v); setForm((f) => ({ ...f, llamacpp_base_url: assembleUrl(v, llamacppPort, "/v1") })); clearModels(); };
  const updateLlPort     = (v: string) => { setLlamacppPort(v); setForm((f) => ({ ...f, llamacpp_base_url: assembleUrl(llamacppHost, v, "/v1") })); clearModels(); };

  const handleProbe = async () => {
    setProbing(true); clearModels();
    try {
      const result = provider === "llamacpp"
        ? await settingsApi.getLlamaCppModels()
        : provider === "lmstudio"
          ? await settingsApi.getLmStudioModels()
          : await settingsApi.getOllamaModels();
      if (result.error) setProbeError(result.error);
      else setLocalModels(result.models);
    } catch {
      setProbeError("Connection failed — check host and port.");
    } finally {
      setProbing(false);
    }
  };

  const handleSave = async () => {
    setSaving(true); setSaveState("idle");
    try {
      await settingsApi.updateSettings(form);
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 2000);
    } catch {
      setSaveState("error");
    } finally {
      setSaving(false);
    }
  };

  const isValid = () => {
    if (provider === "ollama")   return !!(ollamaHost && form.ollama_model);
    if (provider === "lmstudio") return !!lmHost;
    if (provider === "llamacpp") return !!llamacppHost;
    if (provider === "gemini")   return !!(form.gemini_api_key && form.gemini_model);
    if (provider === "claude")   return !!(form.claude_api_key && form.claude_model);
    return false;
  };

  // ── URL row ────────────────────────────────────────────────────────────────

  const HostPortRow = ({
    host, onHost, port, onPort, hostPh, portPh, canProbe,
  }: {
    host: string; onHost: (v: string) => void;
    port: string; onPort: (v: string) => void;
    hostPh: string; portPh: string; canProbe: boolean;
  }) => (
    <div className="space-y-1.5">
      <div className="flex gap-1.5">
        <div className="flex-1">
          <label className="block text-xs text-slate-400 mb-1">Host / IP</label>
          <input type="text" value={host} onChange={(e) => onHost(e.target.value)}
            placeholder={hostPh}
            className="w-full bg-slate-700 text-slate-100 rounded px-2.5 py-1.5 text-xs border border-slate-600 focus:outline-none focus:border-blue-500 placeholder-slate-500" />
        </div>
        <div className="w-16">
          <label className="block text-xs text-slate-400 mb-1">Port</label>
          <input type="text" value={port} onChange={(e) => onPort(e.target.value)}
            placeholder={portPh}
            className="w-full bg-slate-700 text-slate-100 rounded px-2.5 py-1.5 text-xs border border-slate-600 focus:outline-none focus:border-blue-500 placeholder-slate-500" />
        </div>
      </div>
      <div className="flex items-center gap-1.5">
        <p className="flex-1 text-[10px] text-slate-500 font-mono truncate">
          {(provider === "lmstudio" || provider === "llamacpp")
            ? assembleUrl(host, port, "/v1")
            : assembleUrl(host, port)}
        </p>
        <button onClick={handleProbe} disabled={probing || !canProbe}
          className="px-2 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-slate-300 rounded text-[10px] border border-slate-600 whitespace-nowrap">
          {probing ? "…" : "Load Models"}
        </button>
      </div>
      {probeError && <p className="text-red-400 text-[10px]">{probeError}</p>}
      {localModels.length > 0 && <p className="text-emerald-400 text-[10px]">✓ {localModels.length} model(s) found</p>}
    </div>
  );

  return (
    <div className="flex flex-col h-full overflow-y-auto p-3 gap-4">
      <div className="flex items-center gap-2">
        <span>⚙️</span>
        <h3 className="text-sm font-semibold text-slate-200">AI Settings</h3>
      </div>

      {loadError && (
        <div className="p-2 bg-red-900/40 border border-red-700 rounded text-[10px] text-red-300">
          {loadError}
        </div>
      )}

      {/* Provider selector */}
      <div>
        <label className="block text-xs text-slate-400 mb-1.5">Provider</label>
        <div className="grid grid-cols-1 gap-1">
          {PROVIDERS.map((p) => (
            <button key={p.id}
              onClick={() => { setForm((f) => ({ ...f, ai_provider: p.id })); clearModels(); }}
              className={`flex items-center gap-2 px-2.5 py-1.5 rounded text-xs text-left transition-colors ${
                provider === p.id
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
              }`}
            >
              <span className="font-medium">{p.label}</span>
              <span className={`text-[10px] ${provider === p.id ? "text-blue-200" : "text-slate-500"}`}>{p.sub}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Provider-specific fields */}
      <div className="space-y-3">
        {provider === "ollama" && <>
          <HostPortRow host={ollamaHost} onHost={updateOllamaHost} port={ollamaPort} onPort={updateOllamaPort}
            hostPh="http://192.168.0.117" portPh="11434" canProbe={!!ollamaHost} />
          <ModelSelect label="Chat Model" value={form.ollama_model} onChange={(v) => setForm((f) => ({ ...f, ollama_model: v }))}
            options={localModels} placeholder="glm-4.7-flash:latest" />
          <ModelSelect label="Code Model" value={form.ollama_code_model} onChange={(v) => setForm((f) => ({ ...f, ollama_code_model: v }))}
            options={localModels} placeholder="qwen3-coder-next:latest" />
        </>}

        {provider === "lmstudio" && <>
          <p className="text-[10px] text-slate-500">OpenAI-compatible. <code>/v1</code> added automatically.</p>
          <HostPortRow host={lmHost} onHost={updateLmHost} port={lmPort} onPort={updateLmPort}
            hostPh="http://localhost" portPh="1234" canProbe={!!lmHost} />
          <ModelSelect label="Chat Model" value={form.lmstudio_model} onChange={(v) => setForm((f) => ({ ...f, lmstudio_model: v }))}
            options={localModels} placeholder="leave blank for loaded model" />
          <ModelSelect label="Code Model" value={form.lmstudio_code_model} onChange={(v) => setForm((f) => ({ ...f, lmstudio_code_model: v }))}
            options={localModels} placeholder="leave blank for loaded model" />
        </>}

        {provider === "llamacpp" && <>
          <p className="text-[10px] text-slate-500">llama-server. <code>/v1</code> added automatically.</p>
          <HostPortRow host={llamacppHost} onHost={updateLlHost} port={llamacppPort} onPort={updateLlPort}
            hostPh="http://localhost" portPh="8080" canProbe={!!llamacppHost} />
          <ModelSelect label="Chat Model" value={form.llamacpp_model} onChange={(v) => setForm((f) => ({ ...f, llamacpp_model: v }))}
            options={localModels} placeholder="leave blank for loaded model" />
          <ModelSelect label="Code Model" value={form.llamacpp_code_model} onChange={(v) => setForm((f) => ({ ...f, llamacpp_code_model: v }))}
            options={localModels} placeholder="leave blank for loaded model" />
        </>}

        {provider === "gemini" && <>
          <p className="text-[10px] text-slate-500">Get API key at aistudio.google.com</p>
          <Field label="API Key" value={form.gemini_api_key} onChange={(v) => setForm((f) => ({ ...f, gemini_api_key: v }))}
            placeholder="AIza…" type="password" />
          <ModelSelect label="Chat Model" value={form.gemini_model} onChange={(v) => setForm((f) => ({ ...f, gemini_model: v }))} options={GEMINI_MODELS} />
          <ModelSelect label="Code Model" value={form.gemini_code_model} onChange={(v) => setForm((f) => ({ ...f, gemini_code_model: v }))} options={GEMINI_MODELS} />
        </>}

        {provider === "claude" && <>
          <p className="text-[10px] text-slate-500">Get API key at console.anthropic.com</p>
          <Field label="API Key" value={form.claude_api_key} onChange={(v) => setForm((f) => ({ ...f, claude_api_key: v }))}
            placeholder="sk-ant-…" type="password" />
          <ModelSelect label="Chat Model" value={form.claude_model} onChange={(v) => setForm((f) => ({ ...f, claude_model: v }))} options={CLAUDE_MODELS} />
          <ModelSelect label="Code Model" value={form.claude_code_model} onChange={(v) => setForm((f) => ({ ...f, claude_code_model: v }))} options={CLAUDE_MODELS} />
        </>}
      </div>

      {/* Save button */}
      <button
        onClick={handleSave}
        disabled={saving || !isValid()}
        className="w-full py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded text-xs font-medium transition-colors"
      >
        {saveState === "saved" ? "✓ Saved" : saveState === "error" ? "Save failed" : saving ? "Saving…" : "Save Settings"}
      </button>

      <p className="text-[10px] text-slate-600 -mt-2 text-center">
        Saved to shared database · affects both apps
      </p>
    </div>
  );
}
