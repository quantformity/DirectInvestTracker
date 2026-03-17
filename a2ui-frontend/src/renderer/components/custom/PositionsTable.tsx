import React, { useState, useMemo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";

interface Props {
  data: Record<string, unknown>[];
  title?: { literalString?: string };
  showPnl?: boolean;
  showSector?: boolean;
  columns?: string[];
  onAction?: (name: string, ctx: Record<string, unknown>) => void;
}

const ALL_COLUMNS = [
  "symbol", "category", "account_name", "quantity", "cost_per_share",
  "currency", "date_added", "current_price", "mtm", "pnl", "pnl_pct", "sector",
];

const fmtNum = (v: unknown, decimals = 2) => {
  const n = Number(v);
  return isNaN(n) ? "—" : n.toLocaleString("en-CA", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
};

const fmtPct = (v: unknown) => {
  const n = Number(v);
  return isNaN(n) ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
};

export function PositionsTable({ data, title, showPnl = true, showSector = false, columns: colFilter, onAction }: Props) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");

  const visibleCols = colFilter ?? ALL_COLUMNS.filter(c => {
    if (c === "pnl" || c === "pnl_pct" || c === "current_price" || c === "mtm") return showPnl;
    if (c === "sector") return showSector;
    return true;
  });

  const columnDefs = useMemo<ColumnDef<Record<string, unknown>>[]>(() => {
    const defs: ColumnDef<Record<string, unknown>>[] = [];
    if (visibleCols.includes("symbol")) defs.push({ accessorKey: "symbol", header: "Symbol", cell: (i) => <span className="font-mono font-semibold text-blue-300">{String(i.getValue())}</span> });
    if (visibleCols.includes("category")) defs.push({ accessorKey: "category", header: "Category" });
    if (visibleCols.includes("account_name")) defs.push({ accessorKey: "account_name", header: "Account" });
    if (visibleCols.includes("quantity")) defs.push({ accessorKey: "quantity", header: "Qty", cell: (i) => fmtNum(i.getValue(), 0) });
    if (visibleCols.includes("cost_per_share")) defs.push({ accessorKey: "cost_per_share", header: "Cost/sh", cell: (i) => fmtNum(i.getValue(), 4) });
    if (visibleCols.includes("currency")) defs.push({ accessorKey: "currency", header: "Ccy" });
    if (visibleCols.includes("current_price")) defs.push({ accessorKey: "current_price", header: "Price", cell: (i) => fmtNum(i.getValue(), 4) });
    if (visibleCols.includes("mtm")) defs.push({ accessorKey: "mtm_reporting", header: "MTM", cell: (i) => fmtNum(i.getValue()) });
    if (visibleCols.includes("pnl")) defs.push({
      accessorKey: "pnl_reporting",
      header: "P&L",
      cell: (i) => {
        const n = Number(i.getValue());
        return <span className={n >= 0 ? "text-emerald-400" : "text-red-400"}>{fmtNum(i.getValue())}</span>;
      },
    });
    if (visibleCols.includes("pnl_pct")) defs.push({
      accessorKey: "pnl_pct",
      header: "P&L %",
      cell: (i) => {
        const n = Number(i.getValue());
        return <span className={n >= 0 ? "text-emerald-400" : "text-red-400"}>{fmtPct(i.getValue())}</span>;
      },
    });
    if (visibleCols.includes("sector")) defs.push({ accessorKey: "sector", header: "Sector" });
    if (visibleCols.includes("date_added")) defs.push({ accessorKey: "date_added", header: "Added" });
    return defs;
  }, [visibleCols]);

  const table = useReactTable({
    data,
    columns: columnDefs,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  return (
    <div className="flex flex-col gap-2">
      {title?.literalString && (
        <h3 className="text-base font-semibold text-slate-200">{title.literalString}</h3>
      )}
      <input
        type="text"
        placeholder="Filter positions..."
        value={globalFilter}
        onChange={(e) => setGlobalFilter(e.target.value)}
        className="w-48 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
      />
      <div className="overflow-x-auto rounded border border-slate-700">
        <table className="w-full text-xs text-slate-300">
          <thead className="bg-slate-800 text-slate-400 uppercase">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th
                    key={h.id}
                    className="px-3 py-2 text-left cursor-pointer select-none whitespace-nowrap"
                    onClick={h.column.getToggleSortingHandler()}
                  >
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    {h.column.getIsSorted() === "asc" ? " ↑" : h.column.getIsSorted() === "desc" ? " ↓" : ""}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columnDefs.length} className="px-3 py-6 text-center text-slate-500 italic">
                  No positions found
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row, i) => (
                <tr
                  key={row.id}
                  className={`border-t border-slate-700 ${i % 2 === 0 ? "" : "bg-slate-800/30"} hover:bg-slate-700/40`}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-1.5 whitespace-nowrap">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {data.length > 0 && (
        <p className="text-xs text-slate-500">{table.getFilteredRowModel().rows.length} of {data.length} positions</p>
      )}
    </div>
  );
}
