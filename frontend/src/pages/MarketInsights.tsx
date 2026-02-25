import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from "recharts";
import { api, type MarketData, type EnrichedPosition, type SummaryOut } from "../api/client";

const today = new Date().toISOString().split("T")[0];

const fmt = (n: number | null | undefined, decimals = 2) =>
  n != null ? n.toLocaleString("en-CA", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : "—";

const shortFmt = (v: number) => {
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000)     return `${sign}$${(abs / 1_000).toFixed(0)}K`;
  return `${sign}$${abs.toFixed(0)}`;
};

// ── Bar chart ─────────────────────────────────────────────────────────────────

interface ChartPoint { symbol: string; value: number }

function InsightBarChart({
  title,
  data,
  currency,
  colorPositive = "#3b82f6",
  colorNegative = "#ef4444",
  colorMode = "sign",   // "sign" → green/red by value | "flat" → single color
}: {
  title: string;
  data: ChartPoint[];
  currency: string;
  colorPositive?: string;
  colorNegative?: string;
  colorMode?: "sign" | "flat";
}) {
  if (data.length === 0) return null;
  const hasNeg = data.some((d) => d.value < 0);

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-4">
      <div className="text-sm font-semibold text-gray-300 mb-3">
        {title} <span className="text-gray-500 font-normal">({currency})</span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 4, right: 16, left: 16, bottom: 4 }} barCategoryGap="30%">
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
          <XAxis
            dataKey="symbol"
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={shortFmt}
            tick={{ fill: "#6b7280", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={56}
          />
          {hasNeg && <ReferenceLine y={0} stroke="#4b5563" strokeWidth={1} />}
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }}
            labelStyle={{ color: "#f9fafb", fontSize: 12 }}
            itemStyle={{ color: "#d1d5db", fontSize: 12 }}
            formatter={(value: number | undefined) => [`$${fmt(value ?? 0)}`, currency]}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={
                  colorMode === "flat"
                    ? colorPositive
                    : entry.value >= 0
                    ? colorPositive
                    : colorNegative
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Market card ───────────────────────────────────────────────────────────────

function MarketCard({
  data,
  positions,
  reportingCurrency,
}: {
  data: MarketData;
  positions: EnrichedPosition[];
  reportingCurrency: string;
}) {
  const change = data.change_percent ?? 0;
  const totalMtm = positions.reduce((s, p) => s + p.mtm_reporting, 0);
  const eligibleMtm = positions
    .filter((p) => p.date_added !== today)
    .reduce((s, p) => s + p.mtm_reporting, 0);
  const oneDayPnl = data.change_percent != null ? (data.change_percent / 100) * eligibleMtm : null;

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 hover:border-gray-600 transition-colors">
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="font-bold text-white text-lg">{data.symbol}</div>
          {data.company_name && (
            <div className="text-gray-400 text-xs mt-0.5 leading-tight">{data.company_name}</div>
          )}
          <div className="text-gray-600 text-xs mt-0.5">
            {new Date(data.timestamp).toLocaleString()}
          </div>
        </div>
        <span
          className={`px-2 py-1 rounded text-sm font-semibold ${
            change >= 0 ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"
          }`}
        >
          {change >= 0 ? "+" : ""}{fmt(change, 2)}%
        </span>
      </div>

      <div className="text-3xl font-bold text-white mb-3">
        {data.last_price != null ? `$${fmt(data.last_price)}` : "—"}
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <div className="text-gray-500 text-xs">P/E Ratio</div>
          <div className="text-gray-200">{fmt(data.pe_ratio, 1)}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Beta</div>
          <div className="text-gray-200">{fmt(data.beta, 2)}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">MTM ({reportingCurrency})</div>
          <div className="text-gray-200 font-medium">{totalMtm ? `$${fmt(totalMtm)}` : "—"}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">1D PnL ({reportingCurrency})</div>
          {oneDayPnl != null ? (
            <div className={`font-semibold ${oneDayPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {oneDayPnl >= 0 ? "+" : ""}${fmt(Math.abs(oneDayPnl))}
            </div>
          ) : (
            <div className="text-gray-500">—</div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function MarketInsights() {
  const [marketData, setMarketData] = useState<MarketData[]>([]);
  const [summary, setSummary]       = useState<SummaryOut | null>(null);
  const [loading, setLoading]       = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]           = useState("");

  const fetchData = useCallback(async () => {
    try {
      const [md, sum] = await Promise.all([api.getMarketData(), api.getSummary()]);
      setMarketData(md);
      setSummary(sum);
      setError("");
    } catch {
      setError("Failed to load market data — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await api.refreshMarketData();
      await fetchData();
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const positions           = summary?.positions ?? [];
  const reportingCurrency   = summary?.reporting_currency ?? "CAD";

  const getPositions = (symbol: string) =>
    positions.filter((p) => p.symbol === symbol && p.category === "Equity");

  // ── Chart datasets ─────────────────────────────────────────────────────────

  // MTM by symbol — sorted descending
  const mtmData: ChartPoint[] = marketData
    .map((md) => ({
      symbol: md.symbol,
      value: getPositions(md.symbol).reduce((s, p) => s + p.mtm_reporting, 0),
    }))
    .filter((d) => d.value !== 0)
    .sort((a, b) => b.value - a.value);

  // 1-day PnL by symbol
  const oneDayData: ChartPoint[] = marketData
    .filter((md) => md.change_percent != null)
    .map((md) => {
      const eligibleMtm = getPositions(md.symbol)
        .filter((p) => p.date_added !== today)
        .reduce((s, p) => s + p.mtm_reporting, 0);
      return { symbol: md.symbol, value: (md.change_percent! / 100) * eligibleMtm };
    })
    .sort((a, b) => b.value - a.value);

  // Overall PnL by symbol — from enriched positions
  const overallPnlData: ChartPoint[] = [
    ...new Set(
      positions.filter((p) => p.category === "Equity").map((p) => p.symbol)
    ),
  ]
    .map((symbol) => ({
      symbol,
      value: positions
        .filter((p) => p.symbol === symbol)
        .reduce((s, p) => s + p.pnl_reporting, 0),
    }))
    .sort((a, b) => b.value - a.value);

  // Total 1-day PnL banner
  const total1dPnl = oneDayData.reduce((s, d) => s + d.value, 0);
  const has1dData  = oneDayData.length > 0;

  // Cash & GIC totals
  const totalCash = positions
    .filter((p) => p.category === "Cash")
    .reduce((s, p) => s + p.mtm_reporting, 0);
  const totalGic = positions
    .filter((p) => p.category === "GIC")
    .reduce((s, p) => s + p.mtm_reporting, 0);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Market Insights</h1>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <span className={refreshing ? "animate-spin" : ""}>↻</span>
          {refreshing ? "Refreshing…" : "Refresh Now"}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/40 border border-red-700 text-red-300 rounded">{error}</div>
      )}

      {/* Summary stat cards */}
      {!loading && summary && (
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 mb-6">
          {/* Total MTM */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <div className="text-xs text-gray-400 mb-1">Total MTM ({reportingCurrency})</div>
            <div className="text-2xl font-bold text-white">
              ${fmt(summary.total_mtm_reporting)}
            </div>
            <div className="text-xs text-gray-500 mt-1">All positions incl. Cash &amp; GIC</div>
          </div>

          {/* Total PnL */}
          <div className={`border rounded-xl p-4 ${
            summary.total_pnl_reporting >= 0
              ? "bg-green-900/20 border-green-700"
              : "bg-red-900/20 border-red-700"
          }`}>
            <div className="text-xs text-gray-400 mb-1">Total PnL ({reportingCurrency})</div>
            <div className={`text-2xl font-bold ${
              summary.total_pnl_reporting >= 0 ? "text-green-400" : "text-red-400"
            }`}>
              {summary.total_pnl_reporting >= 0 ? "+" : "−"}${fmt(Math.abs(summary.total_pnl_reporting))}
            </div>
            <div className="text-xs text-gray-500 mt-1">All positions incl. Cash &amp; GIC</div>
          </div>

          {/* Today's PnL */}
          {has1dData && (
            <div className={`border rounded-xl p-4 ${
              total1dPnl >= 0 ? "bg-green-900/20 border-green-700" : "bg-red-900/20 border-red-700"
            }`}>
              <div className="text-xs text-gray-400 mb-1">Today's PnL ({reportingCurrency})</div>
              <div className={`text-2xl font-bold ${total1dPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                {total1dPnl >= 0 ? "+" : "−"}${fmt(Math.abs(total1dPnl))}
              </div>
              <div className="text-xs text-gray-500 mt-1">Equity positions only</div>
            </div>
          )}

          {/* Total Cash */}
          {totalCash > 0 && (
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
              <div className="text-xs text-gray-400 mb-1">Total Cash ({reportingCurrency})</div>
              <div className="text-2xl font-bold text-cyan-400">
                ${fmt(totalCash)}
              </div>
              <div className="text-xs text-gray-500 mt-1">Cash positions</div>
            </div>
          )}

          {/* Total GIC */}
          {totalGic > 0 && (
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
              <div className="text-xs text-gray-400 mb-1">Total GIC ({reportingCurrency})</div>
              <div className="text-2xl font-bold text-purple-400">
                ${fmt(totalGic)}
              </div>
              <div className="text-xs text-gray-500 mt-1">GIC positions</div>
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">Loading market data…</div>
      ) : marketData.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 gap-4">
          <div className="text-gray-500 text-center">
            <div className="text-4xl mb-2">📊</div>
            <div>No market data yet</div>
            <div className="text-sm mt-1">Add equity positions and click Refresh Now</div>
          </div>
        </div>
      ) : (
        <>
          {/* ── Bar charts ── */}
          <div className="grid grid-cols-1 gap-4 mb-6">
            <InsightBarChart
              title="Mark-to-Market by Symbol"
              data={mtmData}
              currency={reportingCurrency}
              colorMode="flat"
              colorPositive="#3b82f6"
            />
            <InsightBarChart
              title="1-Day PnL by Symbol"
              data={oneDayData}
              currency={reportingCurrency}
              colorPositive="#22c55e"
              colorNegative="#ef4444"
            />
            <InsightBarChart
              title="Overall PnL by Symbol"
              data={overallPnlData}
              currency={reportingCurrency}
              colorPositive="#22c55e"
              colorNegative="#ef4444"
            />
          </div>

          {/* ── Market cards ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {marketData.map((md) => (
              <MarketCard
                key={md.symbol}
                data={md}
                positions={getPositions(md.symbol)}
                reportingCurrency={reportingCurrency}
              />
            ))}
          </div>
          <p className="mt-4 text-xs text-gray-600">Auto-refreshes every 60s · Backend syncs every 5 min</p>
        </>
      )}
    </div>
  );
}
