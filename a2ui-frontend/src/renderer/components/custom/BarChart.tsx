import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

interface BarDef {
  key: string;
  label: string;
  color?: string;
}

interface Props {
  data: Record<string, unknown>[];
  title?: { literalString?: string };
  xKey: string;
  bars: BarDef[];
  yLabel?: string;
  layout?: "vertical" | "horizontal";
  height?: number;
}

export function BarChartComp({ data, title, xKey, bars, yLabel, layout = "vertical", height = 280 }: Props) {
  if (!data?.length) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-500 text-sm italic">
        No data available
      </div>
    );
  }

  const isHorizontal = layout === "horizontal";

  return (
    <div className="flex flex-col gap-2">
      {title?.literalString && (
        <h3 className="text-base font-semibold text-slate-200">{title.literalString}</h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={data}
          layout={isHorizontal ? "vertical" : "horizontal"}
          margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          {isHorizontal ? (
            <>
              <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <YAxis dataKey={xKey} type="category" tick={{ fill: "#94a3b8", fontSize: 11 }} width={100} />
            </>
          ) : (
            <>
              <XAxis dataKey={xKey} tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <YAxis
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 } : undefined}
              />
            </>
          )}
          <Tooltip
            contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 6, fontSize: 12 }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
          {bars.map((b, i) => (
            <Bar
              key={b.key}
              dataKey={b.key}
              name={b.label}
              fill={b.color ?? COLORS[i % COLORS.length]}
              radius={[2, 2, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
