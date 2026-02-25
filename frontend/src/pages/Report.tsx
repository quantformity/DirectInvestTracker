import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  LineChart, Line,
  BarChart, Bar, Cell, ReferenceLine,
  PieChart, Pie,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";
import { api, type SummaryOut, type HistoryPoint, type MarketData, type ReportSummaryResponse } from "../api/client";

// ── Period helpers ────────────────────────────────────────────────────────────

type Period = "wtd" | "mtd" | "qtd" | "ytd" | "full";

const PERIOD_LABELS: Record<Period, string> = {
  wtd:  "Week to Date",
  mtd:  "Month to Date",
  qtd:  "Quarter to Date",
  ytd:  "Year to Date",
  full: "Full History",
};

function getPeriodStart(period: Period): string | null {
  if (period === "full") return null;
  const now   = new Date();
  const y     = now.getFullYear();
  const m     = now.getMonth();      // 0-indexed
  const d     = now.getDate();
  const pad   = (n: number) => String(n).padStart(2, "0");

  switch (period) {
    case "ytd": return `${y}-01-01`;
    case "qtd": {
      const qStart = Math.floor(m / 3) * 3;
      return `${y}-${pad(qStart + 1)}-01`;
    }
    case "mtd": return `${y}-${pad(m + 1)}-01`;
    case "wtd": {
      const dow   = now.getDay();                    // 0 = Sun
      const diff  = dow === 0 ? 6 : dow - 1;        // days back to Monday
      const mon   = new Date(y, m, d - diff);
      return mon.toISOString().split("T")[0];
    }
  }
}

function periodDateRange(period: Period, allPoints: HistoryPoint[], today: string): string {
  if (period === "full") {
    const earliest = allPoints[0]?.date ?? today;
    return `${earliest} – ${today}`;
  }
  const start = getPeriodStart(period)!;
  return `${start} – ${today}`;
}

// ── Shared utilities ──────────────────────────────────────────────────────────

const TODAY = new Date().toLocaleDateString("en-CA");

const fmt = (n: number, decimals = 2) =>
  n.toLocaleString("en-CA", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

const shortFmt = (v: number) => {
  const abs  = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000)     return `${sign}$${(abs / 1_000).toFixed(0)}K`;
  return `${sign}$${abs.toFixed(0)}`;
};

const PIE_COLORS = [
  "#60a5fa", "#34d399", "#f59e0b", "#f87171", "#a78bfa",
  "#fb923c", "#2dd4bf", "#e879f9", "#4ade80", "#facc15",
];

// ── Reusable chart components ─────────────────────────────────────────────────

function ReportPieChart({
  title,
  groups,
  currency,
}: {
  title: string;
  groups: SummaryOut["groups"];
  currency: string;
}) {
  const pieData = groups
    .filter((g) => g.total_mtm_reporting > 0)
    .map((g) => ({ name: g.group_key, value: g.total_mtm_reporting }));
  if (pieData.length === 0) return null;

  return (
    <div className="border border-gray-200 rounded-xl p-4">
      <div className="text-sm font-semibold text-gray-700 mb-2">{title}</div>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={pieData}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={78}
            paddingAngle={2}
            dataKey="value"
          >
            {pieData.map((_, i) => (
              <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} stroke="transparent" />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: number | undefined, name: string | undefined) => [`$${fmt(value ?? 0)} ${currency}`, name ?? ""]}
            contentStyle={{ fontSize: 11, borderRadius: 8 }}
          />
          <Legend
            wrapperStyle={{ fontSize: 11 }}
            formatter={(value) => <span style={{ color: "#374151" }}>{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

interface ChartPoint { symbol: string; value: number }

function ReportBarChart({
  title,
  data,
  currency,
  colorPositive = "#3b82f6",
  colorNegative = "#ef4444",
  colorMode = "sign",
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
    <div className="border border-gray-200 rounded-xl p-4">
      <div className="text-sm font-semibold text-gray-700 mb-3">
        {title} <span className="text-gray-400 font-normal">({currency})</span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 4, right: 16, left: 16, bottom: 4 }} barCategoryGap="30%">
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
          <XAxis
            dataKey="symbol"
            tick={{ fill: "#6b7280", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={shortFmt}
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={56}
          />
          {hasNeg && <ReferenceLine y={0} stroke="#d1d5db" strokeWidth={1} />}
          <Tooltip
            contentStyle={{ fontSize: 11, borderRadius: 8 }}
            formatter={(value: number | undefined) => [`$${fmt(value ?? 0)}`, currency]}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={colorMode === "flat" ? colorPositive : entry.value >= 0 ? colorPositive : colorNegative}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Main report page ──────────────────────────────────────────────────────────

export function Report() {
  const navigate = useNavigate();

  const [period,         setPeriod]         = useState<Period>("ytd");
  const [summaryCat,     setSummaryCat]     = useState<SummaryOut | null>(null);
  const [summaryAcct,    setSummaryAcct]    = useState<SummaryOut | null>(null);
  const [summarySym,     setSummarySym]     = useState<SummaryOut | null>(null);
  const [summaryCashGic, setSummaryCashGic] = useState<SummaryOut | null>(null);
  const [marketData,     setMarketData]     = useState<MarketData[]>([]);
  const [allHistory,      setAllHistory]      = useState<HistoryPoint[]>([]);
  const [symbolHistories, setSymbolHistories] = useState<Map<string, HistoryPoint[]>>(new Map());
  const [loading,         setLoading]         = useState(true);
  const [error,           setError]           = useState("");
  const [saving,          setSaving]          = useState(false);

  // AI summary state
  const [aiResult,  setAiResult]  = useState<ReportSummaryResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const aiReqRef = useRef(0); // incremented on each call; stale responses are ignored

  useEffect(() => {
    async function load() {
      try {
        const [cat, acct, sym, cashGic, md, hist] = await Promise.all([
          api.getSummary("category"),
          api.getSummary("account"),
          api.getSummary("symbol"),
          api.getSummary("cash_gic"),
          api.getMarketData(),
          api.getAggregateHistory(undefined, false),
        ]);
        setSummaryCat(cat);
        setSummaryAcct(acct);
        setSummarySym(sym);
        setSummaryCashGic(cashGic);
        setMarketData(md);
        setAllHistory(hist.points);

        // Fetch per-equity-symbol history (cached) for period PnL computation
        const equitySymbols = [...new Set(
          sym.positions.filter((p) => p.category === "Equity").map((p) => p.symbol)
        )];
        if (equitySymbols.length > 0) {
          const symHists = await Promise.all(
            equitySymbols.map((s) => api.getHistory(s, undefined, true))
          );
          const histMap = new Map<string, HistoryPoint[]>();
          symHists.forEach((h, i) => histMap.set(equitySymbols[i], h.points));
          setSymbolHistories(histMap);
        }
      } catch {
        setError("Failed to load report data — is the backend running?");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Clear AI result when the period changes so the user sees a fresh prompt
  useEffect(() => {
    setAiResult(null);
  }, [period]);

  // Stable function to call the AI endpoint; request-ID guard prevents stale overwrites
  const generateAiSummary = useCallback(() => {
    if (!summaryCat || !summaryAcct || aiLoading) return;
    const id = ++aiReqRef.current;

    const start   = getPeriodStart(period);
    const pts     = start ? allHistory.filter((p) => p.date >= start) : allHistory;
    const firstPt = pts[0];
    const lastPt  = pts[pts.length - 1];
    const gain    = lastPt && firstPt ? lastPt.mtm - firstPt.mtm : null;
    const pct     = gain != null && firstPt && firstPt.mtm > 0 ? (gain / firstPt.mtm) * 100 : null;

    setAiResult(null);
    setAiLoading(true);
    api.getReportSummary({
      period_label:        PERIOD_LABELS[period],
      date_range:          periodDateRange(period, allHistory, TODAY),
      reporting_currency:  summaryCat.reporting_currency,
      total_mtm:           summaryCat.total_mtm_reporting,
      total_pnl:           summaryCat.total_pnl_reporting,
      period_gain:         gain,
      period_pct:          pct,
      positions:           summaryCat.positions,
      market_data:         marketData,
      summary_by_category: summaryCat.groups,
      summary_by_account:  summaryAcct.groups,
    })
      .then((res) => { if (aiReqRef.current === id) setAiResult(res); })
      .catch(() => { if (aiReqRef.current === id) setAiResult({ summary: "", error: "Failed to reach the AI service." }); })
      .finally(() => { if (aiReqRef.current === id) setAiLoading(false); });
  }, [summaryCat, summaryAcct, allHistory, period, marketData, aiLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  // Filter history to the selected period
  const historyPoints = useMemo<HistoryPoint[]>(() => {
    const start = getPeriodStart(period);
    return start ? allHistory.filter((p) => p.date >= start) : allHistory;
  }, [period, allHistory]);

  // Per-symbol period PnL: delta of pnl field between start and end of period window
  const symbolPeriodPnl = useMemo<Map<string, number>>(() => {
    const start  = getPeriodStart(period);
    const result = new Map<string, number>();
    symbolHistories.forEach((points, sym) => {
      const pts   = start ? points.filter((p) => p.date >= start) : points;
      const first = pts[0];
      const last  = pts[pts.length - 1];
      if (first && last) result.set(sym, last.pnl - first.pnl);
    });
    return result;
  }, [symbolHistories, period]);

  // Derived from summaryCat — must be declared before the memos that use them
  const currency    = summaryCat?.reporting_currency ?? "CAD";
  const positions   = summaryCat?.positions ?? [];
  const periodUpper = period.toUpperCase();

  // Per-position period PnL: proportional share of symbol's period PnL by quantity
  const positionPeriodPnl = useMemo<Map<number, number>>(() => {
    const totalQty = new Map<string, number>();
    positions.forEach((p) => {
      if (symbolPeriodPnl.has(p.symbol))
        totalQty.set(p.symbol, (totalQty.get(p.symbol) ?? 0) + p.quantity);
    });
    const result = new Map<number, number>();
    positions.forEach((p) => {
      const total  = totalQty.get(p.symbol);
      const symPnl = symbolPeriodPnl.get(p.symbol);
      if (total && symPnl !== undefined)
        result.set(p.id, symPnl * (p.quantity / total));
    });
    return result;
  }, [positions, symbolPeriodPnl]);

  // Aggregate period PnL by category and account (equity only — others lack history)
  const categoryPeriodPnl = useMemo<Map<string, number>>(() => {
    const result = new Map<string, number>();
    positions.forEach((p) => {
      const pnl = positionPeriodPnl.get(p.id);
      if (pnl !== undefined)
        result.set(p.category, (result.get(p.category) ?? 0) + pnl);
    });
    return result;
  }, [positions, positionPeriodPnl]);

  const accountPeriodPnl = useMemo<Map<string, number>>(() => {
    const result = new Map<string, number>();
    positions.forEach((p) => {
      const pnl = positionPeriodPnl.get(p.id);
      if (pnl !== undefined)
        result.set(p.account_name, (result.get(p.account_name) ?? 0) + pnl);
    });
    return result;
  }, [positions, positionPeriodPnl]);

  const handleDownloadPDF = async () => {
    setSaving(true);
    try {
      if (window.electronAPI?.pdf?.save) {
        await window.electronAPI.pdf.save();
      } else {
        window.print();
      }
    } finally {
      setSaving(false);
    }
  };

  // Bar chart data (same logic as MarketInsights)
  const mtmData: ChartPoint[] = marketData
    .map((md) => ({
      symbol: md.symbol,
      value: positions
        .filter((p) => p.symbol === md.symbol && p.category === "Equity")
        .reduce((s, p) => s + p.mtm_reporting, 0),
    }))
    .filter((d) => d.value !== 0)
    .sort((a, b) => b.value - a.value);

  const overallPnlData: ChartPoint[] = [
    ...new Set(positions.filter((p) => p.category === "Equity").map((p) => p.symbol)),
  ]
    .map((symbol) => ({
      symbol,
      value: positions
        .filter((p) => p.symbol === symbol)
        .reduce((s, p) => s + p.pnl_reporting, 0),
    }))
    .sort((a, b) => b.value - a.value);

  const periodPnlData: ChartPoint[] = [...symbolPeriodPnl.entries()]
    .map(([symbol, value]) => ({ symbol, value }))
    .filter((d) => d.value !== 0)
    .sort((a, b) => b.value - a.value);

  // Period gain: last MTM − first MTM within the filtered window
  const firstPt = historyPoints[0];
  const lastPt  = historyPoints[historyPoints.length - 1];
  const periodGain = lastPt && firstPt ? lastPt.mtm - firstPt.mtm : null;
  const periodPct  =
    periodGain != null && firstPt && firstPt.mtm > 0
      ? (periodGain / firstPt.mtm) * 100
      : null;

  const dateRange   = periodDateRange(period, allHistory, TODAY);
  const periodLabel = PERIOD_LABELS[period];

  const PERIODS: { key: Period; label: string }[] = [
    { key: "wtd",  label: "WTD"  },
    { key: "mtd",  label: "MTD"  },
    { key: "qtd",  label: "QTD"  },
    { key: "ytd",  label: "YTD"  },
    { key: "full", label: "Full" },
  ];

  return (
    <div className="min-h-screen bg-white text-gray-900 text-sm">

      {/* ── Toolbar (hidden when printing) ────────────────────────────────── */}
      <div className="print:hidden sticky top-0 z-10 bg-gray-900 border-b border-gray-700 px-6 py-3 flex items-center gap-4">
        <button
          onClick={() => navigate(-1)}
          className="text-gray-400 hover:text-white flex items-center gap-1 text-sm"
        >
          ← Back
        </button>
        <span className="text-white font-semibold text-sm">Portfolio Report</span>

        {/* Period selector */}
        <div className="flex rounded-lg overflow-hidden border border-gray-700 ml-4">
          {PERIODS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setPeriod(key)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                period === key
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2">
          {/* Generate / Regenerate AI summary */}
          <button
            onClick={generateAiSummary}
            disabled={aiLoading || loading}
            className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-gray-200 rounded-lg text-xs font-medium transition-colors"
          >
            {aiLoading ? "Generating…" : "✦ Generate AI Summary"}
          </button>
          <button
            onClick={handleDownloadPDF}
            disabled={saving || loading}
            className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
          >
            {saving ? "Saving…" : "⬇ Download PDF"}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">
          Loading report data…
        </div>
      ) : error ? (
        <div className="p-8 text-red-600">{error}</div>
      ) : (
        <div className="max-w-4xl mx-auto px-8 py-10">

          {/* ── Report Header ──────────────────────────────────────────────── */}
          <div className="mb-8 pb-6 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Portfolio Report</h1>
              <p className="text-gray-500 mt-1">{periodLabel}: {dateRange}</p>
              <p className="text-gray-400 text-xs mt-0.5">Generated on {TODAY} · v{__APP_VERSION__}</p>
            </div>
            <img
              src="/QuantformityIcon.png"
              alt="Quantformity"
              className="h-16 object-contain opacity-90"
            />
          </div>

          {/* ── Portfolio Overview ─────────────────────────────────────────── */}
          {summaryCat && (
            <section className="mb-10">
              <h2 className="text-lg font-semibold mb-4 text-gray-800">Portfolio Overview</h2>
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-5">
                  <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">
                    Total MTM ({currency})
                  </div>
                  <div className="text-2xl font-bold text-gray-900">
                    {fmt(summaryCat.total_mtm_reporting)}
                  </div>
                </div>
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-5">
                  <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">
                    Total PnL ({currency})
                  </div>
                  <div className={`text-2xl font-bold ${summaryCat.total_pnl_reporting >= 0 ? "text-green-600" : "text-red-600"}`}>
                    {summaryCat.total_pnl_reporting >= 0 ? "+" : ""}
                    {fmt(summaryCat.total_pnl_reporting)}
                  </div>
                </div>
                {periodGain != null && (
                  <div className="bg-gray-50 border border-gray-200 rounded-xl p-5">
                    <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">
                      {periodLabel} Gain ({currency})
                    </div>
                    <div className={`text-2xl font-bold ${periodGain >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {periodGain >= 0 ? "+" : ""}{fmt(periodGain)}
                      {periodPct != null && (
                        <span className="text-sm ml-2 font-normal">
                          ({periodPct >= 0 ? "+" : ""}{periodPct.toFixed(1)}%)
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* ── AI Analyst Summary ────────────────────────────────────────── */}
          <section className="mb-10">
            <h2 className="text-lg font-semibold mb-4 text-gray-800 flex items-center gap-2">
              ✦ Analyst Summary
              {aiLoading && (
                <span className="text-xs font-normal text-blue-500 animate-pulse">
                  Generating…
                </span>
              )}
            </h2>

            {aiLoading && (
              <div className="border border-blue-100 bg-blue-50 rounded-xl p-6">
                <div className="flex items-center gap-3 text-blue-500">
                  <svg className="animate-spin h-5 w-5 shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <span className="text-sm">AI is analysing your portfolio…</span>
                </div>
              </div>
            )}

            {!aiLoading && aiResult?.error && (
              <div className="border border-amber-200 bg-amber-50 rounded-xl p-5 text-amber-800 text-sm">
                <span className="font-semibold">AI unavailable:</span> {aiResult.error}
                <p className="text-xs mt-1 text-amber-600">Check your AI provider settings to enable this section.</p>
              </div>
            )}

            {!aiLoading && aiResult?.summary && (
              <div className="border border-gray-200 rounded-xl p-6 bg-gray-50">
                {/* Render markdown-style bold headings and paragraphs */}
                {aiResult.summary.split("\n").map((line, i) => {
                  if (!line.trim()) return <div key={i} className="h-3" />;
                  // Convert **text** to bold spans
                  const parts = line.split(/(\*\*[^*]+\*\*)/g);
                  return (
                    <p key={i} className="text-gray-700 leading-relaxed mb-1">
                      {parts.map((part, j) =>
                        part.startsWith("**") && part.endsWith("**")
                          ? <strong key={j} className="text-gray-900 font-semibold">{part.slice(2, -2)}</strong>
                          : part
                      )}
                    </p>
                  );
                })}
              </div>
            )}

            {!aiLoading && !aiResult && (
              <div className="border border-dashed border-gray-200 rounded-xl p-6 text-center">
                <p className="text-gray-400 text-sm mb-3">
                  Click to generate an AI narrative analysis of your portfolio for this period.
                </p>
                <button
                  onClick={generateAiSummary}
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
                >
                  ✦ Generate AI Summary
                </button>
              </div>
            )}
          </section>

          {/* ── Performance Chart ──────────────────────────────────────────── */}
          {historyPoints.length > 1 && (
            <section className="mb-10">
              <h2 className="text-lg font-semibold mb-4 text-gray-800">
                {periodLabel} Performance ({dateRange})
              </h2>
              <div className="border border-gray-200 rounded-xl p-4">
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart
                    data={historyPoints}
                    margin={{ top: 4, right: 24, left: 16, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10, fill: "#6b7280" }}
                      tickFormatter={(d: string) => d.slice(5)}
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: "#6b7280" }}
                      tickFormatter={(v: number) =>
                        `$${Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(0)}K` : v.toFixed(0)}`
                      }
                    />
                    <Tooltip
                      formatter={(v: number | undefined, name: string | undefined) => [`$${fmt(v ?? 0)} ${currency}`, name ?? ""]}
                      contentStyle={{ fontSize: 11, borderRadius: 8 }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line type="monotone" dataKey="mtm" name="MTM" stroke="#2563eb" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="pnl" name="PnL" stroke="#16a34a" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}

          {/* ── Portfolio Composition — 4 Pie Charts ──────────────────────── */}
          {summaryCat && (
            <section className="mb-10">
              <h2 className="text-lg font-semibold mb-4 text-gray-800">Portfolio Composition</h2>
              <div className="grid grid-cols-2 gap-4">
                <ReportPieChart title="By Category"          groups={summaryCat.groups}     currency={currency} />
                {summaryAcct    && <ReportPieChart title="By Account"           groups={summaryAcct.groups}    currency={currency} />}
                {summarySym     && <ReportPieChart title="By Symbol"            groups={summarySym.groups}     currency={currency} />}
                {summaryCashGic && <ReportPieChart title="Cash / GIC vs Other"  groups={summaryCashGic.groups} currency={currency} />}
              </div>
            </section>
          )}

          {/* ── Symbol Bar Charts ─────────────────────────────────────────── */}
          {(mtmData.length > 0 || overallPnlData.length > 0) && (
            <section className="mb-10">
              <h2 className="text-lg font-semibold mb-4 text-gray-800">Market Insights by Symbol</h2>
              <div className="space-y-4">
                <ReportBarChart
                  title="Mark-to-Market by Symbol"
                  data={mtmData}
                  currency={currency}
                  colorMode="flat"
                  colorPositive="#3b82f6"
                />
                <ReportBarChart
                  title="Overall PnL by Symbol"
                  data={overallPnlData}
                  currency={currency}
                  colorPositive="#22c55e"
                  colorNegative="#ef4444"
                />
                {periodPnlData.length > 0 && (
                  <ReportBarChart
                    title={`${periodUpper} PnL by Symbol`}
                    data={periodPnlData}
                    currency={currency}
                    colorPositive="#22c55e"
                    colorNegative="#ef4444"
                  />
                )}
              </div>
            </section>
          )}

          {/* ── Holdings by Category ───────────────────────────────────────── */}
          {summaryCat && (
            <section className="mb-10">
              <h2 className="text-lg font-semibold mb-4 text-gray-800">Holdings by Category</h2>
              <table className="w-full text-sm border border-gray-200 rounded-xl overflow-hidden">
                <thead className="bg-gray-100 text-gray-600 text-xs uppercase">
                  <tr>
                    <th className="px-4 py-2 text-left">Category</th>
                    <th className="px-4 py-2 text-right">MTM ({currency})</th>
                    <th className="px-4 py-2 text-right">PnL ({currency})</th>
                    <th className="px-4 py-2 text-right">{periodUpper} PnL ({currency})</th>
                    <th className="px-4 py-2 text-right">Weight</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {summaryCat.groups.map((g) => {
                    const periodPnl = categoryPeriodPnl.get(g.group_key);
                    return (
                      <tr key={g.group_key}>
                        <td className="px-4 py-2.5 font-medium">{g.group_key}</td>
                        <td className="px-4 py-2.5 text-right">{fmt(g.total_mtm_reporting)}</td>
                        <td className={`px-4 py-2.5 text-right ${g.total_pnl_reporting >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {g.total_pnl_reporting >= 0 ? "+" : ""}{fmt(g.total_pnl_reporting)}
                        </td>
                        <td className={`px-4 py-2.5 text-right ${periodPnl == null ? "text-gray-400" : periodPnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {periodPnl != null ? `${periodPnl >= 0 ? "+" : ""}${fmt(periodPnl)}` : "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right">{g.proportion.toFixed(1)}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>
          )}

          {/* ── Holdings by Account ────────────────────────────────────────── */}
          {summaryAcct && (
            <section className="mb-10">
              <h2 className="text-lg font-semibold mb-4 text-gray-800">Holdings by Account</h2>
              <table className="w-full text-sm border border-gray-200 rounded-xl overflow-hidden">
                <thead className="bg-gray-100 text-gray-600 text-xs uppercase">
                  <tr>
                    <th className="px-4 py-2 text-left">Account</th>
                    <th className="px-4 py-2 text-right">MTM ({currency})</th>
                    <th className="px-4 py-2 text-right">PnL ({currency})</th>
                    <th className="px-4 py-2 text-right">{periodUpper} PnL ({currency})</th>
                    <th className="px-4 py-2 text-right">Weight</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {summaryAcct.groups.map((g) => {
                    const periodPnl = accountPeriodPnl.get(g.group_key);
                    return (
                      <tr key={g.group_key}>
                        <td className="px-4 py-2.5 font-medium">{g.group_key}</td>
                        <td className="px-4 py-2.5 text-right">{fmt(g.total_mtm_reporting)}</td>
                        <td className={`px-4 py-2.5 text-right ${g.total_pnl_reporting >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {g.total_pnl_reporting >= 0 ? "+" : ""}{fmt(g.total_pnl_reporting)}
                        </td>
                        <td className={`px-4 py-2.5 text-right ${periodPnl == null ? "text-gray-400" : periodPnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {periodPnl != null ? `${periodPnl >= 0 ? "+" : ""}${fmt(periodPnl)}` : "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right">{g.proportion.toFixed(1)}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>
          )}

          {/* ── Holdings by Symbol ─────────────────────────────────────────── */}
          {summarySym && summarySym.groups.length > 0 && (
            <section className="mb-10">
              <h2 className="text-lg font-semibold mb-4 text-gray-800">Holdings by Symbol</h2>
              <table className="w-full text-sm border border-gray-200 rounded-xl overflow-hidden">
                <thead className="bg-gray-100 text-gray-600 text-xs uppercase">
                  <tr>
                    <th className="px-4 py-2 text-left">Symbol</th>
                    <th className="px-4 py-2 text-right">MTM ({currency})</th>
                    <th className="px-4 py-2 text-right">PnL ({currency})</th>
                    <th className="px-4 py-2 text-right">{periodUpper} PnL ({currency})</th>
                    <th className="px-4 py-2 text-right">Weight</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {summarySym.groups.map((g) => {
                    const periodPnl = symbolPeriodPnl.get(g.group_key);
                    return (
                      <tr key={g.group_key}>
                        <td className="px-4 py-2.5 font-semibold">{g.group_key}</td>
                        <td className="px-4 py-2.5 text-right">{fmt(g.total_mtm_reporting)}</td>
                        <td className={`px-4 py-2.5 text-right ${g.total_pnl_reporting >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {g.total_pnl_reporting >= 0 ? "+" : ""}{fmt(g.total_pnl_reporting)}
                        </td>
                        <td className={`px-4 py-2.5 text-right ${periodPnl == null ? "text-gray-400" : periodPnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {periodPnl != null ? `${periodPnl >= 0 ? "+" : ""}${fmt(periodPnl)}` : "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right">{g.proportion.toFixed(1)}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>
          )}

          {/* ── All Positions ──────────────────────────────────────────────── */}
          {positions.length > 0 && (
            <section className="mb-10">
              <h2 className="text-lg font-semibold mb-4 text-gray-800">All Positions</h2>
              <table className="w-full text-xs border border-gray-200 rounded-xl overflow-hidden">
                <thead className="bg-gray-100 text-gray-600 text-xs uppercase">
                  <tr>
                    <th className="px-3 py-2 text-left">Symbol</th>
                    <th className="px-3 py-2 text-left">Category</th>
                    <th className="px-3 py-2 text-left">Account</th>
                    <th className="px-3 py-2 text-right">Qty</th>
                    <th className="px-3 py-2 text-right">Cost</th>
                    <th className="px-3 py-2 text-right">Spot</th>
                    <th className="px-3 py-2 text-right">MTM ({currency})</th>
                    <th className="px-3 py-2 text-right">PnL ({currency})</th>
                    <th className="px-3 py-2 text-right">{periodUpper} PnL ({currency})</th>
                    <th className="px-3 py-2 text-right">Wt%</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {positions.map((p) => {
                    const periodPnl = positionPeriodPnl.get(p.id);
                    return (
                      <tr key={p.id}>
                        <td className="px-3 py-2 font-semibold">{p.symbol}</td>
                        <td className="px-3 py-2 text-gray-500">{p.category}</td>
                        <td className="px-3 py-2 text-gray-500">{p.account_name}</td>
                        <td className="px-3 py-2 text-right">{fmt(p.quantity, 0)}</td>
                        <td className="px-3 py-2 text-right">{fmt(p.cost_per_share)}</td>
                        <td className="px-3 py-2 text-right">
                          {p.spot_price != null ? fmt(p.spot_price) : "—"}
                        </td>
                        <td className="px-3 py-2 text-right">{fmt(p.mtm_reporting)}</td>
                        <td className={`px-3 py-2 text-right ${p.pnl_reporting >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {p.pnl_reporting >= 0 ? "+" : ""}{fmt(p.pnl_reporting)}
                        </td>
                        <td className={`px-3 py-2 text-right ${periodPnl == null ? "text-gray-400" : periodPnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {periodPnl != null ? `${periodPnl >= 0 ? "+" : ""}${fmt(periodPnl)}` : "—"}
                        </td>
                        <td className="px-3 py-2 text-right">{p.proportion.toFixed(1)}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>
          )}

          {/* ── Report Footer ──────────────────────────────────────────────── */}
          <div className="border-t border-gray-200 pt-4 text-xs text-gray-400 text-center">
            Qf Direct Invest Tracker · {periodLabel} Report · Generated {TODAY}
          </div>

        </div>
      )}
    </div>
  );
}
