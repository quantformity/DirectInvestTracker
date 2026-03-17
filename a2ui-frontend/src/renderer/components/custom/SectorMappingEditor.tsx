import React, { useState, useCallback } from "react";

interface MappingRow {
  symbol: string;
  sector: string;
}

interface Props {
  data: Record<string, unknown>[];
  title?: { literalString?: string };
  onAction: (name: string, ctx: Record<string, unknown>) => void;
}

const COMMON_SECTORS = [
  "Communication Services", "Consumer Discretionary", "Consumer Staples",
  "Energy", "Financials", "Health Care", "Industrials",
  "Information Technology", "Materials", "Real Estate", "Utilities",
];

export function SectorMappingEditor({ data, title, onAction }: Props) {
  const rows = data as unknown as MappingRow[];

  // Build list of unique sectors from existing data
  const existingSectors = [...new Set(
    rows.map((r) => r.sector).filter((s) => s && s !== "Unspecified")
  )].sort();
  const sectorOptions = [...new Set([
    ...COMMON_SECTORS,
    ...existingSectors,
  ])].sort();

  const [pending, setPending] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<Set<string>>(new Set());

  const getValue = useCallback(
    (symbol: string, original: string) =>
      pending[symbol] !== undefined ? pending[symbol] : original,
    [pending]
  );

  const handleSave = (symbol: string, original: string) => {
    const newSector = getValue(symbol, original);
    if (newSector === original) return;
    if (newSector === "Unspecified" || !newSector) {
      onAction("sector.reset", { symbol });
    } else {
      onAction("sector.update", { symbol, sector: newSector });
    }
    setSaved((s) => new Set(s).add(symbol));
    setTimeout(() => setSaved((s) => { const n = new Set(s); n.delete(symbol); return n; }), 2000);
  };

  const handleReset = (symbol: string) => {
    onAction("sector.reset", { symbol });
    setPending((p) => {
      const n = { ...p };
      delete n[symbol];
      return n;
    });
  };

  return (
    <div className="flex flex-col gap-2">
      {title?.literalString && (
        <h3 className="text-base font-semibold text-slate-200">{title.literalString}</h3>
      )}
      {rows.length === 0 ? (
        <p className="text-slate-500 italic text-sm">No symbols found</p>
      ) : (
        <div className="overflow-x-auto rounded border border-slate-700">
          <table className="w-full text-sm text-slate-300">
            <thead className="bg-slate-800 text-slate-400 text-xs uppercase">
              <tr>
                <th className="px-3 py-2 text-left">Symbol</th>
                <th className="px-3 py-2 text-left">Sector</th>
                <th className="px-3 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => {
                const currentVal = getValue(row.symbol, row.sector);
                const isDirty = currentVal !== row.sector;
                const isSaved = saved.has(row.symbol);

                return (
                  <tr
                    key={row.symbol}
                    className={`border-t border-slate-700 ${i % 2 === 0 ? "" : "bg-slate-800/30"}`}
                  >
                    <td className="px-3 py-2 font-mono font-semibold text-blue-300">
                      {row.symbol}
                    </td>
                    <td className="px-3 py-2">
                      <input
                        list={`sectors-${row.symbol}`}
                        value={currentVal}
                        onChange={(e) =>
                          setPending((p) => ({ ...p, [row.symbol]: e.target.value }))
                        }
                        onBlur={() => isDirty && handleSave(row.symbol, row.sector)}
                        className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                        placeholder="Enter sector..."
                      />
                      <datalist id={`sectors-${row.symbol}`}>
                        {sectorOptions.map((s) => (
                          <option key={s} value={s} />
                        ))}
                      </datalist>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex gap-2 items-center">
                        {isDirty && (
                          <button
                            onClick={() => handleSave(row.symbol, row.sector)}
                            className="px-2 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs"
                          >
                            Save
                          </button>
                        )}
                        {isSaved && (
                          <span className="text-emerald-400 text-xs">✓ Saved</span>
                        )}
                        {row.sector !== "Unspecified" && (
                          <button
                            onClick={() => handleReset(row.symbol)}
                            className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded text-xs"
                          >
                            Reset
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
