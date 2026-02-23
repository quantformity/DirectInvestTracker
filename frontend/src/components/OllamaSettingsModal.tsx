import { useState, useEffect } from "react";
import { api, type OllamaSettings } from "../api/client";

interface Props {
  onClose: () => void;
}

export function OllamaSettingsModal({ onClose }: Props) {
  const [form, setForm]         = useState<OllamaSettings>({
    ollama_base_url: "",
    ollama_model: "",
    ollama_code_model: "",
  });
  const [models, setModels]     = useState<string[]>([]);
  const [probeError, setProbeError] = useState<string | null>(null);
  const [probing, setProbing]   = useState(false);
  const [saving, setSaving]     = useState(false);
  const [saved, setSaved]       = useState(false);
  const [loadError, setLoadError] = useState("");

  // Database path (Electron only)
  const hasElectron = !!window.electronAPI?.db;
  const [dbPath, setDbPath]         = useState("");
  const [pendingDbPath, setPendingDbPath] = useState<string | null>(null);
  const [relaunching, setRelaunching]     = useState(false);

  // Load current settings on mount
  useEffect(() => {
    api.getSettings()
      .then((s) => setForm(s))
      .catch(() => setLoadError("Could not load settings from backend."));

    if (hasElectron) {
      window.electronAPI!.db.getPath().then(setDbPath);
    }
  }, [hasElectron]);

  const handleProbe = async () => {
    setProbing(true);
    setProbeError(null);
    setModels([]);
    try {
      const result = await api.getOllamaModels();
      if (result.error) {
        setProbeError(result.error);
      } else {
        setModels(result.models);
      }
    } catch {
      setProbeError("Request failed — check the URL and try again.");
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

  const modelField = (
    label: string,
    key: keyof OllamaSettings,
    hint: string,
  ) => (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      {models.length > 0 ? (
        <select
          value={form[key]}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
          className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500"
        >
          {/* Keep current value even if not in list */}
          {!models.includes(form[key]) && form[key] && (
            <option value={form[key]}>{form[key]}</option>
          )}
          {models.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      ) : (
        <input
          type="text"
          value={form[key]}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
          placeholder={hint}
          className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500 placeholder-gray-500"
        />
      )}
    </div>
  );

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

        <div className="space-y-4">
          {/* Base URL + probe button */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Ollama Base URL</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={form.ollama_base_url}
                onChange={(e) => {
                  setForm((f) => ({ ...f, ollama_base_url: e.target.value }));
                  setModels([]);
                  setProbeError(null);
                }}
                placeholder="http://192.168.0.117:11434"
                className="flex-1 bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500 placeholder-gray-500"
              />
              <button
                onClick={handleProbe}
                disabled={probing || !form.ollama_base_url}
                className="px-3 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-white rounded-lg text-xs font-medium transition-colors whitespace-nowrap border border-gray-600"
              >
                {probing ? "…" : "Load Models"}
              </button>
            </div>
            {probeError && (
              <p className="text-red-400 text-xs mt-1">{probeError}</p>
            )}
            {models.length > 0 && (
              <p className="text-green-400 text-xs mt-1">✓ {models.length} models found — select below</p>
            )}
          </div>

          {modelField("Chat Model", "ollama_model", "glm-4.7-flash:latest")}
          {modelField("Code / SQL Model", "ollama_code_model", "qwen3-coder-next:latest")}
        </div>

        {/* Database path (Electron packaged app only) */}
        {hasElectron && (
          <>
            <div className="my-5 border-t border-gray-700" />
            <div className="space-y-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-base">🗄️</span>
                <h3 className="text-white font-semibold text-sm">Database</h3>
              </div>

              {/* Current path */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Current database file</label>
                <p className="text-xs text-gray-300 font-mono bg-gray-800 rounded-lg px-3 py-2 border border-gray-700 break-all">
                  {dbPath || "Loading…"}
                </p>
              </div>

              {/* New path picker */}
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
            disabled={saving || !form.ollama_base_url || !form.ollama_model || !form.ollama_code_model}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {saved ? "✓ Saved" : saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
