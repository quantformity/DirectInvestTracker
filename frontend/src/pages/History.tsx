import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ReferenceLine, ReferenceDot, ResponsiveContainer,
} from "recharts";
import { api, type Account, type Position, type HistoryPoint } from "../api/client";

type ViewMode = "portfolio" | "account" | "symbol";

const fmt = (n: number) =>
  n.toLocaleString("en-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function History() {
  const [accounts, setAccounts]         = useState<Account[]>([]);
  const [positions, setPositions]       = useState<Position[]>([]);
  const [mode, setMode]                 = useState<ViewMode>("portfolio");
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [selectedAccount, setSelectedAccount] = useState<number>(0);
  const [points, setPoints]             = useState<HistoryPoint[]>([]);
  const [chartTitle, setChartTitle]     = useState("");
  const [loading, setLoading]           = useState(false);
  const [refreshing, setRefreshing]     = useState(false);
  const [error, setError]               = useState("");

  // Load accounts + positions once
  useEffect(() => {
    Promise.all([api.getAccounts(), api.getPositions()]).then(([accs, poss]) => {
      setAccounts(accs);
      const equitySymbols = [...new Set(
        poss.filter((p) => p.category === "Equity").map((p) => p.symbol)
      )];
      setPositions(poss.filter((p) => equitySymbols.includes(p.symbol)));
      if (equitySymbols.length > 0) setSelectedSymbol(equitySymbols[0]);
      if (accs.length > 0) setSelectedAccount(accs[0].id);
    });
  }, []);

  // Fetch chart data whenever mode / selection changes.
  // Two-phase loading:
  //   Phase 1 — read from local SQLite cache (fast, shown immediately)
  //   Phase 2 — fetch live from Yahoo Finance (slow, updates chart + writes cache)
  useEffect(() => {
    let cancelled = false;
    let hasCachedData = false;

    setPoints([]);
    setError("");
    setLoading(true);
    setRefreshing(false);

    if (mode === "symbol" && !selectedSymbol) { setLoading(false); return; }
    if (mode === "account" && !selectedAccount) { setLoading(false); return; }

    const makeCall = (useCache: boolean) =>
      mode === "portfolio" ? api.getAggregateHistory(undefined, useCache) :
      mode === "account"   ? api.getAggregateHistory(selectedAccount, useCache) :
                             api.getHistory(selectedSymbol, undefined, useCache);

    // ── Phase 1: cache (instant) ─────────────────────────────────────────────
    makeCall(true)
      .then((hist) => {
        if (!cancelled && hist.points.length > 0) {
          hasCachedData = true;
          setPoints(hist.points);
          setChartTitle(hist.symbol);
        }
      })
      .catch(() => {}) // cache miss is fine
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    // ── Phase 2: live Yahoo Finance (slow) ───────────────────────────────────
    setRefreshing(true);
    makeCall(false)
      .then((hist) => {
        if (!cancelled) {
          setLoading(false);
          setPoints(hist.points);
          setChartTitle(hist.symbol);
        }
      })
      .catch((e) => {
        if (!cancelled && !hasCachedData) {
          setError(e?.response?.data?.detail || "Failed to fetch history");
        }
      })
      .finally(() => {
        if (!cancelled) setRefreshing(false);
      });

    return () => { cancelled = true; };
  }, [mode, selectedSymbol, selectedAccount]);

  const equitySymbols = [...new Set(positions.filter((p) => p.category === "Equity").map((p) => p.symbol))];

  const chartData = points.map((p) => ({
    date: p.date,
    PnL:     Number(p.pnl.toFixed(2)),
    MTM:     Number(p.mtm.toFixed(2)),
    CashGIC: Number((p.cash_gic ?? 0).toFixed(2)),
  }));

  const latestPnl = points.length ? points[points.length - 1].pnl : null;

  const extremes = chartData.length > 1 ? {
    maxMtm: chartData.reduce((b, d) => d.MTM > b.MTM ? d : b, chartData[0]),
    minMtm: chartData.reduce((b, d) => d.MTM < b.MTM ? d : b, chartData[0]),
    maxPnl: chartData.reduce((b, d) => d.PnL > b.PnL ? d : b, chartData[0]),
    minPnl: chartData.reduce((b, d) => d.PnL < b.PnL ? d : b, chartData[0]),
  } : null;

  const shortFmt = (n: number) => {
    const abs = Math.abs(n);
    if (abs >= 1_000_000) return `${n < 0 ? "-" : ""}$${(abs / 1_000_000).toFixed(2)}M`;
    if (abs >= 1_000)     return `${n < 0 ? "-" : ""}$${(abs / 1_000).toFixed(1)}K`;
    return `${n < 0 ? "-$" : "$"}${abs.toFixed(0)}`;
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-white mb-6">Historical Performance</h1>

      {/* Mode selector */}
      <div className="mb-5 flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1">View</label>
          <div className="flex rounded-lg overflow-hidden border border-gray-700">
            {([
              { value: "portfolio", label: "Portfolio" },
              { value: "account",   label: "By Account" },
              { value: "symbol",    label: "By Symbol"  },
            ] as { value: ViewMode; label: string }[]).map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setMode(value)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  mode === value
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {mode === "account" && (
          <div>
            <label className="block text-xs text-gray-400 mb-1">Account</label>
            <select
              className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
              value={selectedAccount}
              onChange={(e) => setSelectedAccount(Number(e.target.value))}
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name} ({a.base_currency})</option>
              ))}
            </select>
          </div>
        )}

        {mode === "symbol" && (
          <div>
            <label className="block text-xs text-gray-400 mb-1">Symbol</label>
            <select
              className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
            >
              {equitySymbols.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
        )}

        {latestPnl != null && !loading && (
          <div>
            <div className="text-xs text-gray-400">Current PnL</div>
            <div className={`text-xl font-bold ${latestPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {latestPnl >= 0 ? "+" : ""}{fmt(latestPnl)}
            </div>
          </div>
        )}
      </div>

      {error && <div className="mb-4 p-3 bg-red-900/40 border border-red-700 text-red-300 rounded">{error}</div>}

      {equitySymbols.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 gap-4 text-gray-500">
          <div className="text-4xl">📅</div>
          <div>No equity positions found. Add some in Position Manager.</div>
        </div>
      ) : (loading || (refreshing && points.length === 0)) ? (
        <div className="flex items-center justify-center h-64 text-gray-500">
          Loading history from Yahoo Finance…
          {(mode === "portfolio" || mode === "account") && (
            <span className="ml-2 text-xs">(fetching {equitySymbols.length} symbols, may take a moment)</span>
          )}
        </div>
      ) : (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-4">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-3">
            <span>{chartTitle} — PnL &amp; MTM Since Purchase</span>
            {refreshing && (
              <span className="text-xs font-normal text-blue-400 animate-pulse">Refreshing…</span>
            )}
          </h2>
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData} margin={{ top: 28, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#9CA3AF", fontSize: 12 }}
                tickFormatter={(v) => v.slice(5)}
              />
              <YAxis tick={{ fill: "#9CA3AF", fontSize: 12 }} tickFormatter={(v) => `$${fmt(v)}`} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1F2937", border: "1px solid #374151", borderRadius: 8 }}
                labelStyle={{ color: "#E5E7EB" }}
                itemStyle={{ color: "#D1D5DB" }}
                formatter={(value: number | undefined, name: string | undefined) => [`$${fmt(value ?? 0)}`, name ?? ""]}
              />
              <Legend />
              <ReferenceLine y={0} stroke="#ef4444" strokeWidth={1.5} strokeDasharray="4 3" />
              <Line type="monotone" dataKey="PnL" stroke="#3B82F6" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="MTM" stroke="#10B981" dot={false} strokeWidth={2} />
              {mode !== "symbol" && (
                <Line type="monotone" dataKey="CashGIC" name="Cash+GIC" stroke="#f59e0b" dot={false} strokeWidth={1.5} strokeDasharray="6 3" />
              )}

              {extremes && (<>
                {/* MTM peak */}
                <ReferenceDot x={extremes.maxMtm.date} y={extremes.maxMtm.MTM}
                  r={5} fill="#10B981" stroke="#1F2937" strokeWidth={1.5}
                  label={{ value: `▲ ${extremes.maxMtm.date.slice(5)}`, position: "top", fill: "#10B981", fontSize: 10, fontWeight: "bold" }}
                />
                {/* MTM trough */}
                <ReferenceDot x={extremes.minMtm.date} y={extremes.minMtm.MTM}
                  r={5} fill="#ef4444" stroke="#1F2937" strokeWidth={1.5}
                  label={{ value: `▼ ${extremes.minMtm.date.slice(5)}`, position: "bottom", fill: "#ef4444", fontSize: 10, fontWeight: "bold" }}
                />
                {/* PnL peak */}
                <ReferenceDot x={extremes.maxPnl.date} y={extremes.maxPnl.PnL}
                  r={5} fill="#3B82F6" stroke="#1F2937" strokeWidth={1.5}
                  label={{ value: `▲ ${extremes.maxPnl.date.slice(5)}`, position: "top", fill: "#3B82F6", fontSize: 10, fontWeight: "bold" }}
                />
                {/* PnL trough */}
                <ReferenceDot x={extremes.minPnl.date} y={extremes.minPnl.PnL}
                  r={5} fill="#f97316" stroke="#1F2937" strokeWidth={1.5}
                  label={{ value: `▼ ${extremes.minPnl.date.slice(5)}`, position: "bottom", fill: "#f97316", fontSize: 10, fontWeight: "bold" }}
                />
              </>)}
            </LineChart>
          </ResponsiveContainer>

          {/* Extremes summary */}
          {extremes && (
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <div className="bg-emerald-900/20 border border-emerald-700/30 rounded-lg px-3 py-2">
                <div className="text-emerald-400 text-xs font-semibold">▲ Peak MTM</div>
                <div className="text-white text-sm font-bold">{shortFmt(extremes.maxMtm.MTM)}</div>
                <div className="text-gray-400 text-xs">{extremes.maxMtm.date}</div>
              </div>
              <div className="bg-red-900/20 border border-red-700/30 rounded-lg px-3 py-2">
                <div className="text-red-400 text-xs font-semibold">▼ Trough MTM</div>
                <div className="text-white text-sm font-bold">{shortFmt(extremes.minMtm.MTM)}</div>
                <div className="text-gray-400 text-xs">{extremes.minMtm.date}</div>
              </div>
              <div className="bg-blue-900/20 border border-blue-700/30 rounded-lg px-3 py-2">
                <div className="text-blue-400 text-xs font-semibold">▲ Peak PnL</div>
                <div className="text-white text-sm font-bold">{shortFmt(extremes.maxPnl.PnL)}</div>
                <div className="text-gray-400 text-xs">{extremes.maxPnl.date}</div>
              </div>
              <div className="bg-orange-900/20 border border-orange-700/30 rounded-lg px-3 py-2">
                <div className="text-orange-400 text-xs font-semibold">▼ Trough PnL</div>
                <div className="text-white text-sm font-bold">{shortFmt(extremes.minPnl.PnL)}</div>
                <div className="text-gray-400 text-xs">{extremes.minPnl.date}</div>
              </div>
            </div>
          )}

          <p className="text-xs text-gray-600 mt-2">
            Historical data cached locally · Refreshed from Yahoo Finance on each visit
            {(mode === "portfolio" || mode === "account") && " · MTM/PnL converted to reporting currency using historical FX rates"}
          </p>
        </div>
      )}
    </div>
  );
}
