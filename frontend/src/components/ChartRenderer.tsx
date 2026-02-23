import type { ChartResponse } from "../api/client";
import { DataTable } from "./DataTable";
import { createColumnHelper } from "@tanstack/react-table";

interface ChartRendererProps {
  response: ChartResponse;
}

export function ChartRenderer({ response }: ChartRendererProps) {
  if (response.type === "image") {
    return (
      <div className="mt-2">
        <img
          src={`data:image/png;base64,${response.data}`}
          alt="Generated chart"
          className="max-w-full rounded border border-gray-700"
        />
      </div>
    );
  }

  if (response.type === "plotly") {
    try {
      const spec = JSON.parse(response.data);
      // Dynamic import to avoid loading Plotly on initial render
      return <PlotlyChart spec={spec} />;
    } catch {
      return <div className="text-red-400 text-sm">Invalid Plotly JSON</div>;
    }
  }

  if (response.type === "table") {
    try {
      const rows: Record<string, unknown>[] = JSON.parse(response.data);
      if (!rows.length) return <div className="text-gray-400 text-sm">No results</div>;

      const columnHelper = createColumnHelper<Record<string, unknown>>();
      const columns = Object.keys(rows[0]).map((key) =>
        columnHelper.accessor(key, {
          header: key,
          cell: (info) => String(info.getValue() ?? ""),
        })
      );

      return <DataTable data={rows} columns={columns} className="mt-2" />;
    } catch {
      return <div className="text-red-400 text-sm">Could not parse table data</div>;
    }
  }

  if (response.type === "error") {
    return (
      <div className="mt-2 p-3 bg-red-900/30 border border-red-700 rounded text-red-300 text-sm font-mono whitespace-pre-wrap">
        {response.data}
      </div>
    );
  }

  return null;
}

// Lazy Plotly component
function PlotlyChart({ spec }: { spec: { data: unknown[]; layout?: unknown } }) {
  return (
    <div className="mt-2 w-full min-h-[300px] flex items-center justify-center bg-gray-800 rounded">
      <div className="text-gray-400 text-sm">
        [Plotly chart — open in browser for full rendering]
      </div>
      <pre className="hidden">{JSON.stringify(spec, null, 2)}</pre>
    </div>
  );
}
