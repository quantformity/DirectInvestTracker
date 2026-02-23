import { useEffect, useState, useCallback } from "react";
import { createColumnHelper, type ColumnDef } from "@tanstack/react-table";
import { api, type EnrichedPosition } from "../api/client";
import { DataTable } from "../components/DataTable";
import { useSettingsStore } from "../store/settings";

const fmt = (n: number, decimals = 2) =>
  n.toLocaleString("en-CA", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

const columnHelper = createColumnHelper<EnrichedPosition>();

const columns = [
  columnHelper.accessor("symbol", { header: "Symbol", cell: (i) => <span className="font-semibold text-white">{i.getValue()}</span> }),
  columnHelper.accessor("category", { header: "Category" }),
  columnHelper.accessor("account_name", { header: "Account" }),
  columnHelper.accessor("account_currency", { header: "Acct CCY" }),
  columnHelper.accessor("stock_currency", {
    header: "Stock CCY",
    cell: (i) => <span className="px-2 py-0.5 bg-purple-900/50 text-purple-300 rounded text-xs">{i.getValue()}</span>,
  }),
  columnHelper.accessor("quantity", { header: "Qty", cell: (i) => fmt(i.getValue(), 0) }),
  columnHelper.accessor("cost_per_share", {
    header: (h) => `Cost (${h.table.getRowModel().rows[0]?.original.stock_currency ?? "—"})`,
    cell: (i) => fmt(i.getValue()),
  }),
  columnHelper.accessor("spot_price", {
    header: (h) => `Spot (${h.table.getRowModel().rows[0]?.original.stock_currency ?? "—"})`,
    cell: (i) => i.getValue() != null ? fmt(i.getValue()!) : <span className="text-gray-500">—</span>,
  }),
  columnHelper.accessor("mtm_account", { header: "MTM (Acct)", cell: (i) => fmt(i.getValue()) }),
  columnHelper.accessor("pnl_account", {
    header: "PnL (Acct)",
    cell: (i) => {
      const v = i.getValue();
      return <span className={v >= 0 ? "text-green-400" : "text-red-400"}>{v >= 0 ? "+" : ""}{fmt(v)}</span>;
    },
  }),
  columnHelper.accessor("mtm_reporting", { header: "MTM (Rpt)", cell: (i) => fmt(i.getValue()) }),
  columnHelper.accessor("pnl_reporting", {
    header: "PnL (Rpt)",
    cell: (i) => {
      const v = i.getValue();
      return <span className={v >= 0 ? "text-green-400" : "text-red-400"}>{v >= 0 ? "+" : ""}{fmt(v)}</span>;
    },
  }),
  columnHelper.accessor("proportion", {
    header: "Weight %",
    cell: (i) => <span className="text-gray-300">{fmt(i.getValue(), 1)}%</span>,
  }),
];

export function PositionList() {
  const { reportingCurrency } = useSettingsStore();
  const [data, setData] = useState<EnrichedPosition[]>([]);
  const [totals, setTotals] = useState({ mtm: 0, pnl: 0, currency: "CAD" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetch = useCallback(async () => {
    try {
      const summary = await api.getSummary();
      setData(summary.positions);
      setTotals({
        mtm: summary.total_mtm_reporting,
        pnl: summary.total_pnl_reporting,
        currency: summary.reporting_currency,
      });
      setError("");
    } catch {
      setError("Failed to load positions — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
    const interval = setInterval(fetch, 30_000);
    return () => clearInterval(interval);
  }, [fetch]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Position List</h1>
        <div className="flex gap-6 text-sm">
          <div className="text-right">
            <div className="text-gray-400">Total MTM ({totals.currency})</div>
            <div className="text-white font-semibold text-lg">{fmt(totals.mtm)}</div>
          </div>
          <div className="text-right">
            <div className="text-gray-400">Total PnL ({totals.currency})</div>
            <div className={`font-semibold text-lg ${totals.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {totals.pnl >= 0 ? "+" : ""}{fmt(totals.pnl)}
            </div>
          </div>
        </div>
      </div>

      {error && <div className="mb-4 p-3 bg-red-900/40 border border-red-700 text-red-300 rounded">{error}</div>}

      {loading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">Loading positions…</div>
      ) : (
        <>
          <DataTable data={data} columns={columns as ColumnDef<EnrichedPosition, unknown>[]} />
          <p className="mt-3 text-xs text-gray-600">
            Reporting currency: <strong>{reportingCurrency}</strong> · Auto-refreshes every 30s
          </p>
        </>
      )}
    </div>
  );
}
