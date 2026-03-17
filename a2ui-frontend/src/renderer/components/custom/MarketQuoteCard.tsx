import React from "react";

interface QuoteRow {
  symbol: string;
  company_name?: string;
  last_price?: number;
  change_percent?: number;
  pe_ratio?: number;
  beta?: number;
  sector?: string;
}

interface Props {
  data: Record<string, unknown>[];
  layout?: "grid" | "list";
  columns?: number;
}

function SectorBadge({ sector }: { sector?: string }) {
  if (!sector || sector === "Unspecified") return null;
  return (
    <span className="inline-block px-1.5 py-0.5 rounded text-xs bg-slate-700 text-slate-300 font-normal">
      {sector}
    </span>
  );
}

function QuoteCard({ row }: { row: QuoteRow }) {
  const chg = row.change_percent;
  const isPos = chg !== undefined && chg >= 0;

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 flex flex-col gap-1 hover:border-slate-600 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <span className="font-mono font-bold text-blue-300 text-base">{row.symbol}</span>
        <SectorBadge sector={row.sector} />
      </div>
      {row.company_name && (
        <p className="text-xs text-slate-400 truncate">{row.company_name}</p>
      )}
      <div className="flex items-baseline gap-2 mt-1">
        <span className="text-lg font-semibold text-white">
          {row.last_price !== undefined ? row.last_price.toFixed(2) : "—"}
        </span>
        {chg !== undefined && (
          <span className={`text-sm font-medium ${isPos ? "text-emerald-400" : "text-red-400"}`}>
            {isPos ? "+" : ""}{chg.toFixed(2)}%
          </span>
        )}
      </div>
      <div className="flex gap-3 text-xs text-slate-500 mt-0.5">
        {row.pe_ratio !== undefined && <span>P/E {row.pe_ratio.toFixed(1)}</span>}
        {row.beta !== undefined && <span>β {row.beta.toFixed(2)}</span>}
      </div>
    </div>
  );
}

export function MarketQuoteCard({ data, layout = "grid", columns = 3 }: Props) {
  if (!data?.length) {
    return (
      <p className="text-slate-500 italic text-sm">No market quotes available</p>
    );
  }

  const rows = data as unknown as QuoteRow[];

  if (layout === "list") {
    return (
      <div className="flex flex-col gap-2">
        {rows.map((row) => (
          <QuoteCard key={row.symbol} row={row} />
        ))}
      </div>
    );
  }

  return (
    <div
      className="grid gap-3"
      style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
    >
      {rows.map((row) => (
        <QuoteCard key={row.symbol} row={row} />
      ))}
    </div>
  );
}
