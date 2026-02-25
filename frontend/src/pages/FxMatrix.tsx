import { useEffect, useState, useCallback } from "react";
import { api, type FxMatrix } from "../api/client";

// Decimal precision: ≥10 uses 2 dp (e.g. USD/JPY ≈ 150), otherwise 4 dp
function fmtRate(rate: number): string {
  return rate.toFixed(rate >= 10 ? 2 : 4);
}

function fmtTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-CA", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

export function FxMatrixPage() {
  const [data,      setData]      = useState<FxMatrix | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState("");
  const [refreshed, setRefreshed] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const result = await api.getFxMatrix();
      setData(result);
      setRefreshed(new Date());
      setError("");
    } catch {
      setError("Failed to load FX data — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load]);

  const { currencies = [], matrix = {}, updated_at = null } = data ?? {};

  return (
    <div className="p-6 min-h-screen bg-gray-950">
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">FX Rate Matrix</h1>
          <p className="text-gray-500 text-xs mt-1 font-mono">
            1 ROW currency = N COLUMN currency
          </p>
        </div>
        <div className="text-right font-mono text-xs">
          {updated_at && (
            <div className="text-amber-400/70">
              Data as of {fmtTimestamp(updated_at)}
            </div>
          )}
          {refreshed && (
            <div className="text-gray-600">
              Refreshed {refreshed.toLocaleTimeString("en-CA")} · auto every 30s
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/40 border border-red-700 text-red-300 rounded font-mono text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64 text-gray-500 font-mono">
          Loading FX rates…
        </div>
      ) : currencies.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-gray-500 font-mono">
          No currencies found — add accounts and positions first.
        </div>
      ) : (
        <>
          {/* ── Bloomberg-style matrix table ────────────────────────────────── */}
          <div className="overflow-auto rounded-xl border border-gray-800">
            <table className="border-collapse text-xs font-mono w-full">
              <thead>
                <tr>
                  {/* Corner cell */}
                  <th className="sticky left-0 z-20 bg-gray-900 border-b border-r border-gray-700 px-4 py-3 text-left">
                    <span className="text-gray-600 text-[10px] uppercase tracking-widest">FROM ↓ / TO →</span>
                  </th>
                  {currencies.map((col) => (
                    <th
                      key={col}
                      className="bg-gray-900 border-b border-r border-gray-700 px-4 py-3 text-center text-amber-300 font-semibold tracking-widest"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {currencies.map((from, ri) => (
                  <tr key={from} className="group">
                    {/* Row header */}
                    <td className="sticky left-0 z-10 bg-gray-900 border-b border-r border-gray-700 px-4 py-3 text-amber-300 font-semibold tracking-widest text-center group-hover:bg-gray-800">
                      {from}
                    </td>
                    {currencies.map((to, ci) => {
                      const rate = matrix[from]?.[to];
                      const isDiag = ri === ci;

                      if (isDiag) {
                        return (
                          <td
                            key={to}
                            className="border-b border-r border-gray-700 px-4 py-3 text-center text-green-500 bg-gray-900/60 group-hover:bg-gray-800/60"
                          >
                            1.0000
                          </td>
                        );
                      }

                      if (rate == null) {
                        return (
                          <td
                            key={to}
                            className="border-b border-r border-gray-700 px-4 py-3 text-center text-gray-700 group-hover:bg-gray-900"
                          >
                            —
                          </td>
                        );
                      }

                      return (
                        <td
                          key={to}
                          className="border-b border-r border-gray-700 px-4 py-3 text-center text-amber-400 tabular-nums group-hover:bg-gray-900 hover:bg-amber-900/20 hover:text-amber-200 transition-colors cursor-default"
                          title={`1 ${from} = ${rate} ${to}`}
                        >
                          {fmtRate(rate)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ── Legend ──────────────────────────────────────────────────────── */}
          <div className="mt-4 flex items-center gap-6 font-mono text-xs text-gray-600">
            <div className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 rounded-sm bg-green-900/60 border border-green-700/40" />
              <span>diagonal (same currency = 1.0000)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 rounded-sm bg-amber-900/30 border border-amber-700/30" />
              <span>cross rate</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-700 font-bold">—</span>
              <span>rate unavailable</span>
            </div>
            <div className="ml-auto text-gray-700 italic">
              * cross rates are computed by inversion or triangulation via reporting currency
            </div>
          </div>
        </>
      )}
    </div>
  );
}
