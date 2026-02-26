import { useEffect, useState, useCallback } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { api, type SummaryGroup, type SummaryOut } from "../api/client";

const fmt = (n: number) =>
  n.toLocaleString("en-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const COLORS = [
  "#60a5fa", "#34d399", "#f59e0b", "#f87171", "#a78bfa",
  "#fb923c", "#2dd4bf", "#e879f9", "#4ade80", "#facc15",
];

const GROUP_TYPES = [
  { key: "category", label: "By Category" },
  { key: "account",  label: "By Account" },
  { key: "symbol",   label: "By Symbol" },
  { key: "cash_gic", label: "Cash / GIC vs Other" },
  { key: "sector",   label: "By Sector" },
] as const;

type GroupKey = (typeof GROUP_TYPES)[number]["key"];

function SummaryCard({
  groups,
  currency,
  label,
}: {
  groups: SummaryGroup[];
  currency: string;
  label: string;
}) {
  const total    = groups.reduce((s, g) => s + g.total_mtm_reporting, 0);
  const totalPnl = groups.reduce((s, g) => s + g.total_pnl_reporting, 0);

  const pieData = groups
    .filter((g) => g.total_mtm_reporting > 0)
    .map((g) => ({ name: g.group_key, value: g.total_mtm_reporting }));

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700 bg-gray-700/30">
        <h3 className="font-semibold text-gray-200">{label}</h3>
      </div>

      {/* Pie chart */}
      {pieData.length > 0 && (
        <div className="px-2 pt-4 pb-2">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={85}
                paddingAngle={2}
                dataKey="value"
              >
                {pieData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip
                formatter={(value: number | undefined, name: string | undefined) => [`$${fmt(value ?? 0)} ${currency}`, name ?? ""]}
                contentStyle={{
                  backgroundColor: "#1f2937",
                  border: "1px solid #374151",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                labelStyle={{ color: "#f9fafb", fontWeight: 600 }}
                itemStyle={{ color: "#d1d5db" }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Table */}
      <table className="w-full text-sm">
        <thead className="text-gray-400 text-xs uppercase border-t border-gray-700">
          <tr>
            <th className="px-4 py-2 text-left">Group</th>
            <th className="px-4 py-2 text-right">MTM ({currency})</th>
            <th className="px-4 py-2 text-right">PnL ({currency})</th>
            <th className="px-4 py-2 text-right">Weight %</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700/50">
          {groups.map((g, i) => (
            <tr key={g.group_key} className="hover:bg-gray-700/30">
              <td className="px-4 py-2.5 font-medium text-white flex items-center gap-2">
                <span
                  className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                />
                {g.group_key}
              </td>
              <td className="px-4 py-2.5 text-right text-gray-200">{fmt(g.total_mtm_reporting)}</td>
              <td className={`px-4 py-2.5 text-right ${g.total_pnl_reporting >= 0 ? "text-green-400" : "text-red-400"}`}>
                {g.total_pnl_reporting >= 0 ? "+" : ""}{fmt(g.total_pnl_reporting)}
              </td>
              <td className="px-4 py-2.5 text-right text-gray-300">{g.proportion.toFixed(1)}%</td>
            </tr>
          ))}
          {/* Totals row */}
          <tr className="bg-gray-700/50 font-semibold">
            <td className="px-4 py-2.5 text-gray-200 pl-8">Total</td>
            <td className="px-4 py-2.5 text-right text-white">{fmt(total)}</td>
            <td className={`px-4 py-2.5 text-right ${totalPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {totalPnl >= 0 ? "+" : ""}{fmt(totalPnl)}
            </td>
            <td className="px-4 py-2.5 text-right text-white">100.0%</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function Summary() {
  const [summaries, setSummaries] = useState<Partial<Record<GroupKey, SummaryOut>>>({});
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState("");

  const fetchAll = useCallback(async () => {
    try {
      const results = await Promise.all(
        GROUP_TYPES.map(({ key }) => api.getSummary(key).then((data) => ({ key, data })))
      );
      const map: Partial<Record<GroupKey, SummaryOut>> = {};
      for (const { key, data } of results) map[key] = data;
      setSummaries(map);
      setError("");
    } catch {
      setError("Failed to load summary — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const currency = summaries.category?.reporting_currency ?? "CAD";

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Portfolio Summary</h1>
        {summaries.category && (
          <div className="flex gap-6 text-sm">
            <div className="text-right">
              <div className="text-gray-400">Total MTM ({currency})</div>
              <div className="text-white font-semibold text-lg">{fmt(summaries.category.total_mtm_reporting)}</div>
            </div>
            <div className="text-right">
              <div className="text-gray-400">Total PnL ({currency})</div>
              <div className={`font-semibold text-lg ${summaries.category.total_pnl_reporting >= 0 ? "text-green-400" : "text-red-400"}`}>
                {summaries.category.total_pnl_reporting >= 0 ? "+" : ""}{fmt(summaries.category.total_pnl_reporting)}
              </div>
            </div>
          </div>
        )}
      </div>

      {error && <div className="mb-4 p-3 bg-red-900/40 border border-red-700 text-red-300 rounded">{error}</div>}

      {loading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">Loading summary…</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {GROUP_TYPES.map(({ key, label }) => {
            const summary = summaries[key];
            if (!summary) return null;
            return (
              <SummaryCard
                key={key}
                groups={summary.groups}
                currency={currency}
                label={label}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
