import React, { useState } from "react";
import { useSurfaceStore } from "../store/surfaces";
import { AISettingsPanel } from "./AISettingsPanel";

export function HistoryPanel() {
  const { surfaces, activeSurfaceId, setActiveSurface, deleteSurface } = useSurfaceStore();
  const [showSettings, setShowSettings] = useState(false);

  return (
    <div className="w-60 flex-shrink-0 bg-slate-900 border-r border-slate-700 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-3 py-3 border-b border-slate-700 flex items-center gap-2">
        <span className="text-sm font-semibold text-slate-300">
          {showSettings ? "AI Settings" : "Surfaces"}
        </span>
        {!showSettings && (
          <span className="ml-auto text-xs text-slate-500">{surfaces.length}</span>
        )}
      </div>

      {/* Content — surface list or settings panel */}
      <div className="flex-1 overflow-hidden">
        {showSettings ? (
          <AISettingsPanel />
        ) : (
          <div className="h-full overflow-y-auto py-1">
            {surfaces.length === 0 ? (
              <p className="px-3 py-4 text-xs text-slate-500 italic">
                No surfaces yet. Ask the AI something to create one.
              </p>
            ) : (
              surfaces.map((s) => (
                <div
                  key={s.id}
                  onClick={() => setActiveSurface(s.id)}
                  className={`group relative px-3 py-2 cursor-pointer transition-colors border-l-2 ${
                    s.id === activeSurfaceId
                      ? "bg-slate-800 border-blue-500 text-slate-100"
                      : "border-transparent hover:bg-slate-800/50 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <p className="text-xs font-medium truncate pr-5">{s.title || "Untitled"}</p>
                  <p className="text-xs text-slate-500 truncate">
                    {new Date(s.createdAt).toLocaleString()}
                  </p>
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteSurface(s.id); }}
                    className="absolute right-2 top-2 hidden group-hover:flex items-center justify-center w-4 h-4 rounded text-slate-500 hover:text-red-400 hover:bg-slate-700 text-xs"
                    title="Delete surface"
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Bottom toolbar */}
      <div className="border-t border-slate-700 px-3 py-2 flex items-center justify-end">
        <button
          onClick={() => setShowSettings((v) => !v)}
          title={showSettings ? "Back to surfaces" : "AI Settings"}
          className={`p-1.5 rounded transition-colors text-sm ${
            showSettings
              ? "bg-blue-600 text-white"
              : "text-slate-500 hover:text-slate-200 hover:bg-slate-800"
          }`}
        >
          {showSettings ? "✕" : "⚙️"}
        </button>
      </div>
    </div>
  );
}
