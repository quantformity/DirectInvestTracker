import React from "react";

interface FxRow {
  pair: string;
  rate: number;
  timestamp?: string;
}

interface Props {
  data: Record<string, unknown>[];
  title?: { literalString?: string };
  showTimestamp?: boolean;
}

function formatTs(ts?: string) {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export function FxRateTable({ data, title, showTimestamp = true }: Props) {
  const rows = data as unknown as FxRow[];

  return (
    <div className="flex flex-col gap-2">
      {title?.literalString && (
        <h3 className="text-base font-semibold text-slate-200">{title.literalString}</h3>
      )}
      {rows.length === 0 ? (
        <p className="text-slate-500 italic text-sm">No FX rates available</p>
      ) : (
        <div className="overflow-x-auto rounded border border-slate-700">
          <table className="w-full text-sm text-slate-300">
            <thead className="bg-slate-800 text-slate-400 text-xs uppercase">
              <tr>
                <th className="px-3 py-2 text-left">Pair</th>
                <th className="px-3 py-2 text-right">Rate</th>
                {showTimestamp && <th className="px-3 py-2 text-right">Updated</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={row.pair} className={`border-t border-slate-700 ${i % 2 === 0 ? "" : "bg-slate-800/30"}`}>
                  <td className="px-3 py-2 font-mono font-semibold text-blue-300">{row.pair}</td>
                  <td className="px-3 py-2 text-right">{row.rate.toFixed(6)}</td>
                  {showTimestamp && (
                    <td className="px-3 py-2 text-right text-xs text-slate-500">
                      {formatTs(row.timestamp)}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
