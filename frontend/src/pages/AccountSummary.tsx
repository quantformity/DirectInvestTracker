import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { api, type EnrichedPosition, type SummaryOut } from "../api/client";

const fmt = (n: number) =>
  n.toLocaleString("en-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const COLORS = [
  "#60a5fa", "#34d399", "#f59e0b", "#f87171", "#a78bfa",
  "#fb923c", "#2dd4bf", "#e879f9", "#4ade80", "#facc15",
  "#38bdf8", "#fb7185", "#a3e635", "#c084fc", "#f472b6",
];

interface SymbolRow {
  symbol: string;
  quantity: number;
  cost_basis_reporting: number;
  mtm_reporting: number;
  pnl_reporting: number;
  mtm_weight: number;
  pnl_weight: number;
  category: string;
}

interface AccountBlock {
  account_id: number;
  account_name: string;
  account_currency: string;
  symbols: SymbolRow[];
  total_mtm: number;
  total_pnl: number;
}

function groupPositions(positions: EnrichedPosition[]): AccountBlock[] {
  const byAccount = new Map<number, EnrichedPosition[]>();
  for (const p of positions) {
    const list = byAccount.get(p.account_id) ?? [];
    list.push(p);
    byAccount.set(p.account_id, list);
  }

  const blocks: AccountBlock[] = [];
  for (const [account_id, rows] of byAccount) {
    const symbolMap = new Map<string, SymbolRow>();
    for (const r of rows) {
      // Aggregate cash positions under a single "Cash" key
      const key = r.category === "Cash" ? "Cash" : r.symbol;
      const existing = symbolMap.get(key);
      if (existing) {
        existing.quantity += r.quantity;
        existing.cost_basis_reporting += r.cost_per_share * r.quantity * r.fx_stock_to_account * r.fx_account_to_reporting;
        existing.mtm_reporting += r.mtm_reporting;
        existing.pnl_reporting += r.pnl_reporting;
      } else {
        symbolMap.set(key, {
          symbol: key,
          quantity: r.quantity,
          cost_basis_reporting: r.cost_per_share * r.quantity * r.fx_stock_to_account * r.fx_account_to_reporting,
          mtm_reporting: r.mtm_reporting,
          pnl_reporting: r.pnl_reporting,
          mtm_weight: 0,
          pnl_weight: 0,
          category: r.category,
        });
      }
    }

    const total_mtm = Array.from(symbolMap.values()).reduce((s, x) => s + x.mtm_reporting, 0);
    const total_pnl = Array.from(symbolMap.values()).reduce((s, x) => s + x.pnl_reporting, 0);

    const symbols = Array.from(symbolMap.values())
      .map((s) => ({
        ...s,
        mtm_weight: total_mtm ? (s.mtm_reporting / total_mtm) * 100 : 0,
        pnl_weight: total_pnl ? (s.pnl_reporting / total_pnl) * 100 : 0,
      }))
      .sort((a, b) => b.mtm_reporting - a.mtm_reporting);

    blocks.push({
      account_id,
      account_name: rows[0].account_name,
      account_currency: rows[0].account_currency,
      symbols,
      total_mtm,
      total_pnl,
    });
  }

  return blocks.sort((a, b) => b.total_mtm - a.total_mtm);
}

function AccountCard({ block, currency }: { block: AccountBlock; currency: string }) {
  const pieData = block.symbols
    .filter((s) => s.mtm_reporting > 0)
    .map((s) => ({ name: s.symbol, value: s.mtm_reporting }));

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700 bg-gray-700/30 flex items-center justify-between">
        <h3 className="font-semibold text-gray-200">{block.account_name}</h3>
        <div className="flex gap-4 text-xs">
          <div className="text-right">
            <div className="text-gray-400">MTM</div>
            <div className="text-white font-mono font-semibold">{fmt(block.total_mtm)}</div>
          </div>
          <div className="text-right">
            <div className="text-gray-400">PnL</div>
            <div className={`font-mono font-semibold ${block.total_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {block.total_pnl >= 0 ? "+" : ""}{fmt(block.total_pnl)}
            </div>
          </div>
        </div>
      </div>

      {/* Pie chart */}
      {pieData.length > 0 && (
        <div className="px-2 pt-4 pb-2">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={95}
                paddingAngle={2}
                dataKey="value"
              >
                {pieData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip
                formatter={(value: number | undefined, name: string | undefined) => [`${fmt(value ?? 0)} ${currency}`, name ?? ""]}
                contentStyle={{
                  backgroundColor: "#1f2937",
                  border: "1px solid #374151",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                labelStyle={{ color: "#f9fafb", fontWeight: 600 }}
                itemStyle={{ color: "#d1d5db" }}
              />
              <Legend
                wrapperStyle={{ fontSize: "11px" }}
                iconSize={8}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Table */}
      <table className="w-full text-sm">
        <thead className="text-gray-400 text-xs uppercase border-t border-gray-700">
          <tr>
            <th className="px-4 py-2 text-left">Symbol</th>
            <th className="px-4 py-2 text-right">Qty</th>
            <th className="px-4 py-2 text-right">MTM ({currency})</th>
            <th className="px-4 py-2 text-right">PnL ({currency})</th>
            <th className="px-4 py-2 text-right">PnL %</th>
            <th className="px-4 py-2 text-right">MtM Weight</th>
            <th className="px-4 py-2 text-right">PnL Weight</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700/50">
          {block.symbols.map((s, i) => (
            <tr key={s.symbol} className="hover:bg-gray-700/30">
              <td className="px-4 py-2.5 font-medium text-white flex items-center gap-2">
                <span
                  className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                />
                {s.symbol}
                <span className="px-1.5 py-0.5 bg-gray-700 text-gray-400 rounded text-[10px]">{s.category}</span>
              </td>
              <td className="px-4 py-2.5 text-right text-gray-300 font-mono">
                {s.quantity.toLocaleString(undefined, { maximumFractionDigits: 4 })}
              </td>
              <td className="px-4 py-2.5 text-right text-gray-200 font-mono">{fmt(s.mtm_reporting)}</td>
              <td className={`px-4 py-2.5 text-right font-mono ${s.pnl_reporting >= 0 ? "text-green-400" : "text-red-400"}`}>
                {s.pnl_reporting >= 0 ? "+" : ""}{fmt(s.pnl_reporting)}
              </td>
              <td className={`px-4 py-2.5 text-right font-mono ${s.pnl_reporting >= 0 ? "text-green-400" : "text-red-400"}`}>
                {s.cost_basis_reporting
                  ? `${s.pnl_reporting >= 0 ? "+" : ""}${((s.pnl_reporting / Math.abs(s.cost_basis_reporting)) * 100).toFixed(2)}%`
                  : "—"}
              </td>
              <td className="px-4 py-2.5 text-right text-gray-300 font-mono">{s.mtm_weight.toFixed(1)}%</td>
              <td className="px-4 py-2.5 text-right text-gray-300 font-mono">{s.pnl_weight.toFixed(1)}%</td>
            </tr>
          ))}
          <tr className="bg-gray-700/50 font-semibold">
            <td className="px-4 py-2.5 text-gray-200 pl-8">Total</td>
            <td />
            <td className="px-4 py-2.5 text-right text-white font-mono">{fmt(block.total_mtm)}</td>
            <td className={`px-4 py-2.5 text-right font-mono ${block.total_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {block.total_pnl >= 0 ? "+" : ""}{fmt(block.total_pnl)}
            </td>
            <td className={`px-4 py-2.5 text-right font-mono ${block.total_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {(() => {
                const basis = block.total_mtm - block.total_pnl;
                if (!basis) return "—";
                return `${block.total_pnl >= 0 ? "+" : ""}${((block.total_pnl / Math.abs(basis)) * 100).toFixed(2)}%`;
              })()}
            </td>
            <td className="px-4 py-2.5 text-right text-white font-mono">100.0%</td>
            <td className="px-4 py-2.5 text-right text-white font-mono">{block.total_pnl === 0 ? "—" : "100.0%"}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function AccountSummary() {
  const [data, setData] = useState<SummaryOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const resp = await api.getSummary("symbol");
        setData(resp);
        setError("");
      } catch {
        setError("Failed to load summary — is the backend running?");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const blocks = data ? groupPositions(data.positions) : [];
  const currency = data?.reporting_currency ?? "CAD";

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Account Summary</h1>
        {data && (
          <div className="flex gap-6 text-sm">
            <div className="text-right">
              <div className="text-gray-400">Total MTM ({currency})</div>
              <div className="text-white font-semibold text-lg">{fmt(data.total_mtm_reporting)}</div>
            </div>
            <div className="text-right">
              <div className="text-gray-400">Total PnL ({currency})</div>
              <div className={`font-semibold text-lg ${data.total_pnl_reporting >= 0 ? "text-green-400" : "text-red-400"}`}>
                {data.total_pnl_reporting >= 0 ? "+" : ""}{fmt(data.total_pnl_reporting)}
              </div>
            </div>
          </div>
        )}
      </div>

      {error && <div className="mb-4 p-3 bg-red-900/40 border border-red-700 text-red-300 rounded">{error}</div>}

      {loading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">Loading account summary…</div>
      ) : blocks.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-gray-500">No positions yet.</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {blocks.map((b) => (
            <AccountCard key={b.account_id} block={b} currency={currency} />
          ))}
        </div>
      )}
    </div>
  );
}
