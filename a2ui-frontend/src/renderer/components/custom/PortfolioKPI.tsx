import React from "react";

interface KPIData {
  total_mtm?: number;
  total_pnl?: number;
  total_pnl_pct?: number;
  account_count?: number;
  position_count?: number;
  currency?: string;
}

interface Props {
  data?: Record<string, unknown>;
  currency?: { literalString?: string };
}

function KPITile({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex flex-col gap-1">
      <p className="text-xs text-slate-400 uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-bold ${color ?? "text-white"}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

export function PortfolioKPI({ data, currency }: Props) {
  const ccy = currency?.literalString ?? (data?.currency as string) ?? "CAD";
  const kpi = (data ?? {}) as KPIData;

  const fmtMoney = (v?: number) =>
    v !== undefined
      ? v.toLocaleString("en-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : "—";

  const pnlColor =
    kpi.total_pnl !== undefined
      ? kpi.total_pnl >= 0
        ? "text-emerald-400"
        : "text-red-400"
      : "text-white";

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <KPITile
        label="Total Market Value"
        value={`${ccy} ${fmtMoney(kpi.total_mtm)}`}
      />
      <KPITile
        label="Total P&L"
        value={`${ccy} ${fmtMoney(kpi.total_pnl)}`}
        sub={
          kpi.total_pnl_pct !== undefined
            ? `${kpi.total_pnl_pct >= 0 ? "+" : ""}${kpi.total_pnl_pct.toFixed(2)}%`
            : undefined
        }
        color={pnlColor}
      />
      <KPITile
        label="Accounts"
        value={String(kpi.account_count ?? "—")}
      />
      <KPITile
        label="Positions"
        value={String(kpi.position_count ?? "—")}
      />
    </div>
  );
}
