import React, { useState } from "react";
import { useSurfaceStore } from "../store/surfaces";
import type { SurfaceEntry } from "../store/surfaces";
import { A2UIRenderer } from "../renderer/A2UIRenderer";
import { sendAction, streamChatV2 } from "../api/client";
import type { ChatMessage, SSEEvent } from "../api/client";
import type { A2UIComponent } from "../renderer/A2UIRenderer";

interface Props {
  conversation: ChatMessage[];
  onActionResponse?: (response: string) => void;
}

// ── Relative time helper ───────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

// ── Chart type detection ───────────────────────────────────────────────────────

interface ChartInfo {
  type: "BarChart" | "LineChart" | "PieChart";
  id: string;
  dataBinding?: string;
  currentLayout?: string;
  currentBars?: { key: string; label: string }[];
  currentSeries?: { key: string; label: string }[];
}

function detectCharts(components: object[]): ChartInfo[] {
  const charts: ChartInfo[] = [];
  for (const comp of components as A2UIComponent[]) {
    const [typeName, props] = Object.entries(comp.component ?? {})[0] ?? [];
    if (!typeName || !props) continue;
    const p = props as Record<string, unknown>;

    if (typeName === "BarChart") {
      charts.push({
        type: "BarChart",
        id: comp.id,
        dataBinding: p.dataBinding as string,
        currentLayout: (p.layout as string) ?? "vertical",
        currentBars: (p.bars as { key: string; label: string }[]) ?? [],
      });
    } else if (typeName === "LineChart") {
      charts.push({
        type: "LineChart",
        id: comp.id,
        dataBinding: p.dataBinding as string,
        currentSeries: (p.series as { key: string; label: string }[]) ?? [],
      });
    } else if (typeName === "PieChart") {
      charts.push({
        type: "PieChart",
        id: comp.id,
        dataBinding: p.dataBinding as string,
      });
    }
  }
  return charts;
}

// ── Chart controls drawer ─────────────────────────────────────────────────────

interface ControlsProps {
  surface: SurfaceEntry;
}

const METRIC_OPTIONS = [
  { label: "Market Value", value: "total_mtm_reporting" },
  { label: "P&L", value: "total_pnl_reporting" },
  { label: "% of Portfolio", value: "proportion" },
];

const PERIOD_OPTIONS = ["1M", "3M", "6M", "1Y", "All"];

const GROUP_OPTIONS = [
  { label: "By Sector", value: "sector" },
  { label: "By Symbol", value: "symbol" },
  { label: "By Account", value: "account" },
  { label: "By Category", value: "category" },
];

const CHART_TYPE_OPTIONS = ["BarChart", "LineChart", "PieChart"] as const;

function ChartControlsDrawer({ surface }: ControlsProps) {
  const { addOrUpdateSurface, nextNumber } = useSurfaceStore();
  const charts = detectCharts(surface.components);

  const [metric, setMetric] = useState(
    charts[0]?.currentBars?.[0]?.key ?? "total_mtm_reporting"
  );
  const [layout, setLayout] = useState(charts[0]?.currentLayout ?? "horizontal");
  const [period, setPeriod] = useState("3M");
  const [groupBy, setGroupBy] = useState<string>(() => {
    const binding = charts[0]?.dataBinding ?? "";
    for (const g of ["sector", "symbol", "account", "category"]) {
      if (binding.includes(g)) return g;
    }
    return "sector";
  });
  const [chartType, setChartType] = useState<string>(charts[0]?.type ?? "BarChart");
  const [applying, setApplying] = useState(false);

  if (charts.length === 0) return null;

  const hasBar = charts.some((c) => c.type === "BarChart");
  const hasLine = charts.some((c) => c.type === "LineChart");

  // Build a natural-language prompt describing the desired modification.
  // The AI will always create a NEW surface in response.
  function buildPrompt(): string {
    const parts: string[] = [];

    if (chartType === "BarChart") {
      const metricLabel = METRIC_OPTIONS.find((m) => m.value === metric)?.label ?? metric;
      const groupLabel = GROUP_OPTIONS.find((g) => g.value === groupBy)?.label ?? groupBy;
      parts.push(
        `Show a ${layout === "horizontal" ? "horizontal" : "vertical"} bar chart of ${metricLabel} ${groupLabel}.`
      );
    } else if (chartType === "LineChart") {
      const metricLabel = METRIC_OPTIONS.find((m) => m.value === metric)?.label ?? metric;
      parts.push(
        `Show a line chart of portfolio ${metricLabel} history for the last ${period === "All" ? "all time" : period}.`
      );
    } else if (chartType === "PieChart") {
      const metricLabel = METRIC_OPTIONS.find((m) => m.value === metric)?.label ?? metric;
      const groupLabel = GROUP_OPTIONS.find((g) => g.value === groupBy)?.label ?? groupBy;
      parts.push(`Show a pie chart of ${metricLabel} ${groupLabel}.`);
    }

    return parts.join(" ");
  }

  async function handleApply() {
    const prompt = buildPrompt();
    if (!prompt || applying) return;
    setApplying(true);

    const apiMessages: ChatMessage[] = [
      { role: "user", content: prompt },
    ];

    let newSurfaceId = "";
    let rootId = "";
    let llmTitle = "";
    const components: A2UIComponent[] = [];
    const dataModel: Record<string, unknown> = {};

    try {
      for await (const event of streamChatV2(apiMessages)) {
        const e = event as SSEEvent;
        if (e.type === "a2ui") {
          const msg = e.message as Record<string, unknown>;
          if ("beginRendering" in msg) {
            const br = msg.beginRendering as Record<string, unknown>;
            newSurfaceId = (br.surfaceId as string) || crypto.randomUUID();
            rootId = br.root as string;
            if (typeof br.title === "string") llmTitle = br.title;
          } else if ("surfaceUpdate" in msg) {
            const su = msg.surfaceUpdate as Record<string, unknown>;
            components.push(...(su.components as A2UIComponent[]));
          } else if ("dataModelUpdate" in msg) {
            const dmu = msg.dataModelUpdate as Record<string, unknown>;
            for (const item of (dmu.contents as { key: string; valueString: string }[])) {
              if (item.valueString && item.valueString !== "__hydrate__") {
                try { dataModel[item.key] = JSON.parse(item.valueString); }
                catch { dataModel[item.key] = item.valueString; }
              }
            }
          }
        } else if (e.type === "done" && e.surface_id) {
          newSurfaceId = e.surface_id;
        }
      }

      if (components.length > 0 && newSurfaceId) {
        const number = nextNumber;
        addOrUpdateSurface({
          id: newSurfaceId,
          number,
          title: llmTitle || prompt.slice(0, 40),
          rootId,
          components,
          dataModel,
          createdAt: new Date().toISOString(),
        });
      }
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="border-t border-slate-700 bg-slate-900/60 px-4 py-3 flex flex-wrap items-center gap-3">
      {/* Chart type */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-slate-500 mr-1">Type</span>
        {CHART_TYPE_OPTIONS.map((t) => (
          <button
            key={t}
            onClick={() => setChartType(t)}
            className={`px-2 py-0.5 rounded text-xs transition-colors ${
              chartType === t
                ? "bg-blue-600 text-white"
                : "bg-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            {t.replace("Chart", "")}
          </button>
        ))}
      </div>

      <div className="w-px h-4 bg-slate-700" />

      {/* Group by */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-slate-500 mr-1">Group</span>
        <select
          value={groupBy}
          onChange={(e) => setGroupBy(e.target.value)}
          className="bg-slate-800 border border-slate-600 rounded px-1.5 py-0.5 text-xs text-slate-200 focus:outline-none"
        >
          {GROUP_OPTIONS.map((g) => (
            <option key={g.value} value={g.value}>{g.label}</option>
          ))}
        </select>
      </div>

      {/* Metric */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-slate-500 mr-1">Metric</span>
        <select
          value={metric}
          onChange={(e) => setMetric(e.target.value)}
          className="bg-slate-800 border border-slate-600 rounded px-1.5 py-0.5 text-xs text-slate-200 focus:outline-none"
        >
          {METRIC_OPTIONS.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </div>

      {/* Layout (bar only) */}
      {(chartType === "BarChart") && (
        <div className="flex items-center gap-1">
          <span className="text-xs text-slate-500 mr-1">Layout</span>
          {["horizontal", "vertical"].map((l) => (
            <button
              key={l}
              onClick={() => setLayout(l)}
              className={`px-2 py-0.5 rounded text-xs transition-colors ${
                layout === l
                  ? "bg-slate-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              {l === "horizontal" ? "↔" : "↕"}
            </button>
          ))}
        </div>
      )}

      {/* Period (line only) */}
      {(chartType === "LineChart") && (
        <div className="flex items-center gap-1">
          <span className="text-xs text-slate-500 mr-1">Period</span>
          {PERIOD_OPTIONS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-2 py-0.5 rounded text-xs transition-colors ${
                period === p
                  ? "bg-slate-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      )}

      <div className="ml-auto">
        <button
          onClick={handleApply}
          disabled={applying}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded text-xs font-medium transition-colors"
        >
          {applying ? "Creating..." : "New Surface →"}
        </button>
      </div>
    </div>
  );
}

// ── SurfacePanel ──────────────────────────────────────────────────────────────

export function SurfacePanel({ conversation, onActionResponse }: Props) {
  const { surfaces, activeSurfaceId } = useSurfaceStore();
  const [showControls, setShowControls] = useState(true);
  const active = surfaces.find((s) => s.id === activeSurfaceId);

  if (!active) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center px-8 h-full bg-slate-950/30">
        <div className="text-4xl mb-4">✨</div>
        <h2 className="text-xl font-semibold text-slate-300 mb-2">QFI AI Advisor</h2>
        <p className="text-slate-500 text-sm max-w-xs">
          Ask the AI to show your portfolio, history charts, market quotes, or anything else.
          The UI will appear here.
        </p>
      </div>
    );
  }

  const handleAction = async (name: string, ctx: Record<string, unknown>) => {
    const result = await sendAction(active.id, name, ctx, conversation);
    if (result.llm_response && onActionResponse) {
      onActionResponse(result.llm_response);
    }
  };

  const hasCharts = detectCharts(active.components).length > 0;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Status bar */}
      <div className="px-4 py-2 border-b border-slate-700 bg-slate-900 flex items-center gap-2 flex-shrink-0">
        <span className="text-xs font-mono text-blue-400">#{active.number ?? "?"}</span>
        <span className="text-sm font-semibold text-slate-200 truncate">
          {active.title || "Untitled Surface"}
        </span>
        <span className="ml-auto flex items-center gap-3 flex-shrink-0">
          <span className="text-xs text-slate-500">
            updated {relativeTime(active.updatedAt ?? active.createdAt)}
          </span>
          {hasCharts && (
            <button
              onClick={() => setShowControls((v) => !v)}
              title={showControls ? "Hide chart controls" : "Show chart controls"}
              className={`text-xs px-2 py-0.5 rounded transition-colors ${
                showControls
                  ? "bg-slate-700 text-slate-300"
                  : "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
              }`}
            >
              ⚙ Charts
            </button>
          )}
        </span>
      </div>

      {/* A2UI surface */}
      <div className="flex-1 overflow-auto bg-slate-950/20">
        <A2UIRenderer
          rootId={active.rootId || (active.components[0] as { id?: string })?.id || ""}
          components={active.components as Parameters<typeof A2UIRenderer>[0]["components"]}
          dataModel={active.dataModel}
          onAction={handleAction}
        />
      </div>

      {/* Chart controls drawer (always creates new surface) */}
      {hasCharts && showControls && <ChartControlsDrawer surface={active} />}
    </div>
  );
}
