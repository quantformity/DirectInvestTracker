import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

interface SeriesDef {
  key: string;
  label: string;
  color?: string;
  yAxis?: "left" | "right";
}

interface Props {
  data: Record<string, unknown>[];
  title?: { literalString?: string };
  xKey: string;
  series: SeriesDef[];
  yLabel?: string;
  y2Label?: string;
  height?: number;
}

export function LineChartComp({ data, title, xKey, series, yLabel, y2Label, height = 300 }: Props) {
  if (!data?.length) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-500 text-sm italic">
        No data available
      </div>
    );
  }

  const hasRightAxis = series.some((s) => s.yAxis === "right");

  return (
    <div className="flex flex-col gap-2">
      {title?.literalString && (
        <h3 className="text-base font-semibold text-slate-200">{title.literalString}</h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey={xKey}
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickFormatter={(v) => String(v).slice(0, 10)}
          />
          <YAxis
            yAxisId="left"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 } : undefined}
          />
          {hasRightAxis && (
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              label={y2Label ? { value: y2Label, angle: 90, position: "insideRight", fill: "#94a3b8", fontSize: 11 } : undefined}
            />
          )}
          <Tooltip
            contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 6, fontSize: 12 }}
            labelStyle={{ color: "#94a3b8" }}
          />
          <Legend
            wrapperStyle={{ fontSize: 12, color: "#94a3b8" }}
          />
          {series.map((s, i) => (
            <Line
              key={s.key}
              yAxisId={s.yAxis ?? "left"}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color ?? COLORS[i % COLORS.length]}
              dot={false}
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
