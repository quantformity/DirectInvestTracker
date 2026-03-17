import React from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"];

interface Props {
  data: Record<string, unknown>[];
  title?: { literalString?: string };
  nameKey: string;
  valueKey: string;
  valuePrefix?: string;
  showLegend?: boolean;
  height?: number;
}

export function PieChartComp({ data, title, nameKey, valueKey, valuePrefix = "", showLegend = true, height = 280 }: Props) {
  if (!data?.length) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-500 text-sm italic">
        No data available
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {title?.literalString && (
        <h3 className="text-base font-semibold text-slate-200">{title.literalString}</h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={data}
            dataKey={valueKey}
            nameKey={nameKey}
            cx="50%"
            cy="50%"
            outerRadius={height / 3}
            label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(1)}%`}
            labelLine={false}
          >
            {data.map((_entry, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 6, fontSize: 12 }}
            formatter={(value) => [`${valuePrefix}${Number(value).toLocaleString("en-CA", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`]}
          />
          {showLegend && (
            <Legend
              wrapperStyle={{ fontSize: 12, color: "#94a3b8" }}
            />
          )}
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
