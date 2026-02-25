import { useEffect, useState, useRef } from "react";
import { api, type IndustryMapping } from "../api/client";

const COMMON_INDUSTRIES = [
  "Communication Services",
  "Consumer Discretionary",
  "Consumer Staples",
  "Energy",
  "Financials",
  "Health Care",
  "Industrials",
  "Information Technology",
  "Materials",
  "Real Estate",
  "Utilities",
  "Unspecified",
];

export function IndustryMappingPage() {
  const [mappings, setMappings] = useState<IndustryMapping[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState("");
  const [saving, setSaving]     = useState<Record<string, boolean>>({});
  // Track local edits before blur-to-save
  const [edits, setEdits]       = useState<Record<string, string>>({});
  const debounceRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    api.getIndustryMappings()
      .then((data) => {
        setMappings(data);
        // Seed edits state
        const init: Record<string, string> = {};
        data.forEach((m) => { init[m.symbol] = m.industry; });
        setEdits(init);
      })
      .catch(() => setError("Failed to load industry mappings — is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (symbol: string, value: string) => {
    setEdits((prev) => ({ ...prev, [symbol]: value }));
  };

  const handleSave = async (symbol: string) => {
    const industry = edits[symbol] ?? "Unspecified";
    // Skip if unchanged
    const current = mappings.find((m) => m.symbol === symbol);
    if (current?.industry === industry) return;

    setSaving((prev) => ({ ...prev, [symbol]: true }));
    try {
      const updated = await api.upsertIndustryMapping(symbol, industry);
      setMappings((prev) =>
        prev.map((m) => (m.symbol === symbol ? updated : m))
      );
    } catch {
      setError(`Failed to save industry for ${symbol}.`);
    } finally {
      setSaving((prev) => ({ ...prev, [symbol]: false }));
    }
  };

  const handleReset = async (symbol: string) => {
    setSaving((prev) => ({ ...prev, [symbol]: true }));
    try {
      await api.deleteIndustryMapping(symbol);
      setMappings((prev) =>
        prev.map((m) => (m.symbol === symbol ? { ...m, industry: "Unspecified" } : m))
      );
      setEdits((prev) => ({ ...prev, [symbol]: "Unspecified" }));
    } catch {
      setError(`Failed to reset industry for ${symbol}.`);
    } finally {
      setSaving((prev) => ({ ...prev, [symbol]: false }));
    }
  };

  // Keyboard: save on Enter, revert on Escape
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>, symbol: string) => {
    if (e.key === "Enter") {
      e.currentTarget.blur();
    } else if (e.key === "Escape") {
      const current = mappings.find((m) => m.symbol === symbol);
      setEdits((prev) => ({ ...prev, [symbol]: current?.industry ?? "Unspecified" }));
      e.currentTarget.blur();
    }
  };

  // Group mappings by industry for the summary panel
  const byIndustry = mappings.reduce<Record<string, string[]>>((acc, m) => {
    const ind = edits[m.symbol] ?? m.industry;
    if (!acc[ind]) acc[ind] = [];
    acc[ind].push(m.symbol);
    return acc;
  }, {});

  const industriesSet = new Set(mappings.map((m) => edits[m.symbol] ?? m.industry));
  const assignedCount = mappings.filter((m) => (edits[m.symbol] ?? m.industry) !== "Unspecified").length;

  // Clear debounce timers on unmount
  useEffect(() => {
    return () => {
      Object.values(debounceRef.current).forEach(clearTimeout);
    };
  }, []);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Industry Mapping</h1>
          <p className="text-sm text-gray-400 mt-1">
            Assign an industry to each symbol. Changes are saved automatically on blur.
          </p>
        </div>
        <div className="flex gap-4 text-sm text-right">
          <div>
            <div className="text-gray-400">Symbols</div>
            <div className="text-white font-semibold text-lg">{mappings.length}</div>
          </div>
          <div>
            <div className="text-gray-400">Assigned</div>
            <div className="text-white font-semibold text-lg">{assignedCount}</div>
          </div>
          <div>
            <div className="text-gray-400">Industries</div>
            <div className="text-white font-semibold text-lg">
              {[...industriesSet].filter((i) => i !== "Unspecified").length}
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/40 border border-red-700 text-red-300 rounded text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">
          Loading mappings…
        </div>
      ) : mappings.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-500">
          <div className="text-4xl">🏭</div>
          <div>No positions found. Add positions in the Position Manager first.</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Main mapping table */}
          <div className="xl:col-span-2">
            <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="text-gray-400 text-xs uppercase bg-gray-700/30">
                  <tr>
                    <th className="px-4 py-3 text-left">Symbol</th>
                    <th className="px-4 py-3 text-left">Industry</th>
                    <th className="px-4 py-3 text-center w-20">Reset</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700/50">
                  {mappings.map((m) => {
                    const currentEdit = edits[m.symbol] ?? m.industry;
                    const isDirty = currentEdit !== m.industry;
                    const isSaving = saving[m.symbol];

                    return (
                      <tr key={m.symbol} className="hover:bg-gray-700/20">
                        <td className="px-4 py-2.5 font-semibold text-white">
                          {m.symbol}
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={currentEdit}
                              onChange={(e) => handleChange(m.symbol, e.target.value)}
                              onBlur={() => handleSave(m.symbol)}
                              onKeyDown={(e) => handleKeyDown(e, m.symbol)}
                              list={`industry-list-${m.symbol}`}
                              className={`bg-gray-900 border rounded px-2 py-1 text-white text-sm w-full max-w-xs focus:outline-none focus:ring-1 focus:ring-blue-500 ${
                                isDirty
                                  ? "border-yellow-500/60"
                                  : "border-gray-600"
                              }`}
                              placeholder="Unspecified"
                            />
                            <datalist id={`industry-list-${m.symbol}`}>
                              {COMMON_INDUSTRIES.map((ind) => (
                                <option key={ind} value={ind} />
                              ))}
                            </datalist>
                            {isSaving && (
                              <span className="text-xs text-blue-400 animate-pulse whitespace-nowrap">
                                Saving…
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          {m.industry !== "Unspecified" ? (
                            <button
                              onClick={() => handleReset(m.symbol)}
                              disabled={isSaving}
                              className="text-xs text-gray-400 hover:text-red-400 disabled:opacity-40 transition-colors px-2 py-1 rounded hover:bg-gray-700"
                              title="Reset to Unspecified"
                            >
                              Reset
                            </button>
                          ) : (
                            <span className="text-gray-600 text-xs">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-gray-600">
              Click an industry cell to edit · Press Enter or click away to save · Press Esc to cancel
            </p>
          </div>

          {/* Industry summary panel */}
          <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden self-start">
            <div className="px-4 py-3 border-b border-gray-700 bg-gray-700/30">
              <h3 className="font-semibold text-gray-200 text-sm">Industry Summary</h3>
            </div>
            <div className="p-4 space-y-3">
              {Object.entries(byIndustry)
                .sort(([a], [b]) => {
                  if (a === "Unspecified") return 1;
                  if (b === "Unspecified") return -1;
                  return a.localeCompare(b);
                })
                .map(([industry, symbols]) => (
                  <div key={industry}>
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-sm font-medium ${industry === "Unspecified" ? "text-gray-500" : "text-gray-200"}`}>
                        {industry}
                      </span>
                      <span className="text-xs text-gray-500 bg-gray-700 px-1.5 py-0.5 rounded">
                        {symbols.length}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {symbols.map((sym) => (
                        <span
                          key={sym}
                          className={`text-xs px-1.5 py-0.5 rounded ${
                            industry === "Unspecified"
                              ? "bg-gray-700 text-gray-500"
                              : "bg-blue-900/50 text-blue-300"
                          }`}
                        >
                          {sym}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
