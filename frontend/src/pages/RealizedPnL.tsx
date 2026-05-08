import { useEffect, useState } from "react";
import { api, type RealizedPnLOut, type SellTransactionOut } from "../api/client";

const fmt = (n: number) =>
  n.toLocaleString("en-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fmtQty = (n: number) =>
  n.toLocaleString(undefined, { maximumFractionDigits: 4 });

interface AccountGroup {
  account_id: number;
  account_name: string;
  transactions: SellTransactionOut[];
  total_pnl_reporting: number;
}

function groupByAccount(transactions: SellTransactionOut[]): AccountGroup[] {
  const map = new Map<number, AccountGroup>();
  for (const tx of transactions) {
    const g = map.get(tx.account_id) ?? {
      account_id: tx.account_id,
      account_name: tx.account_name,
      transactions: [],
      total_pnl_reporting: 0,
    };
    g.transactions.push(tx);
    g.total_pnl_reporting += tx.realized_pnl_reporting;
    map.set(tx.account_id, g);
  }
  return Array.from(map.values()).sort((a, b) => b.total_pnl_reporting - a.total_pnl_reporting);
}

function PnLCell({ value, currency }: { value: number; currency: string }) {
  const color = value >= 0 ? "text-green-400" : "text-red-400";
  return (
    <span className={`font-mono ${color}`}>
      {value >= 0 ? "+" : ""}{fmt(value)} {currency}
    </span>
  );
}

function AccountTable({ group, reportingCurrency }: { group: AccountGroup; reportingCurrency: string }) {
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-700 bg-gray-700/30 flex items-center justify-between">
        <h3 className="font-semibold text-gray-200">{group.account_name}</h3>
        <div className="text-right">
          <div className="text-xs text-gray-400">Realized PnL ({reportingCurrency})</div>
          <div className={`font-mono font-semibold text-sm ${group.total_pnl_reporting >= 0 ? "text-green-400" : "text-red-400"}`}>
            {group.total_pnl_reporting >= 0 ? "+" : ""}{fmt(group.total_pnl_reporting)}
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-gray-400 text-xs uppercase border-b border-gray-700">
            <tr>
              <th className="px-4 py-2 text-left">Date</th>
              <th className="px-4 py-2 text-left">Symbol</th>
              <th className="px-4 py-2 text-left">Category</th>
              <th className="px-4 py-2 text-right">Qty Sold</th>
              <th className="px-4 py-2 text-right">Sell Price</th>
              <th className="px-4 py-2 text-right">Cost/Share</th>
              <th className="px-4 py-2 text-right">Fee</th>
              <th className="px-4 py-2 text-right">PnL (Stock Ccy)</th>
              <th className="px-4 py-2 text-right">PnL ({reportingCurrency})</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {group.transactions.map((tx) => (
              <tr key={tx.id} className="hover:bg-gray-700/30">
                <td className="px-4 py-2.5 text-gray-400 font-mono text-xs">{tx.date}</td>
                <td className="px-4 py-2.5 font-medium text-white">{tx.symbol}</td>
                <td className="px-4 py-2.5">
                  <span className="px-1.5 py-0.5 bg-gray-700 text-gray-400 rounded text-[10px]">{tx.category}</span>
                </td>
                <td className="px-4 py-2.5 text-right text-gray-300 font-mono">{fmtQty(tx.quantity)}</td>
                <td className="px-4 py-2.5 text-right text-gray-300 font-mono">
                  {fmt(tx.sell_price)} <span className="text-gray-500 text-xs">{tx.stock_currency}</span>
                </td>
                <td className="px-4 py-2.5 text-right text-gray-300 font-mono">
                  {fmt(tx.cost_per_share)} <span className="text-gray-500 text-xs">{tx.stock_currency}</span>
                </td>
                <td className="px-4 py-2.5 text-right text-gray-400 font-mono">
                  {tx.fee > 0 ? `${fmt(tx.fee)} ${tx.stock_currency}` : "—"}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <PnLCell value={tx.realized_pnl_stock} currency={tx.stock_currency} />
                </td>
                <td className="px-4 py-2.5 text-right">
                  <PnLCell value={tx.realized_pnl_reporting} currency={reportingCurrency} />
                </td>
              </tr>
            ))}
            <tr className="bg-gray-700/50 font-semibold border-t border-gray-600">
              <td colSpan={8} className="px-4 py-2.5 text-gray-300 pl-8">Total</td>
              <td className="px-4 py-2.5 text-right">
                <PnLCell value={group.total_pnl_reporting} currency={reportingCurrency} />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function RealizedPnL() {
  const [data, setData] = useState<RealizedPnLOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const resp = await api.getRealizedPnL();
        setData(resp);
        setError("");
      } catch {
        setError("Failed to load realized PnL — is the backend running?");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const groups = data ? groupByAccount(data.transactions) : [];
  const currency = data?.reporting_currency ?? "CAD";

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Realized PnL</h1>
        {data && (
          <div className="text-right">
            <div className="text-gray-400 text-sm">Total Realized PnL ({currency})</div>
            <div className={`font-semibold text-lg ${data.total_realized_pnl_reporting >= 0 ? "text-green-400" : "text-red-400"}`}>
              {data.total_realized_pnl_reporting >= 0 ? "+" : ""}{fmt(data.total_realized_pnl_reporting)}
            </div>
          </div>
        )}
      </div>

      {error && <div className="mb-4 p-3 bg-red-900/40 border border-red-700 text-red-300 rounded">{error}</div>}

      {loading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">Loading realized PnL…</div>
      ) : groups.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 gap-2 text-gray-500">
          <div className="text-lg">No sell transactions recorded yet.</div>
          <div className="text-sm text-gray-600">Sells made from this version onwards will appear here.</div>
        </div>
      ) : (
        <div className="space-y-6">
          {groups.map((g) => (
            <AccountTable key={g.account_id} group={g} reportingCurrency={currency} />
          ))}
        </div>
      )}
    </div>
  );
}
