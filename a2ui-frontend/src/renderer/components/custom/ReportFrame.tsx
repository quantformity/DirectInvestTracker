import React from "react";

interface ReportData {
  html?: string;
}

interface Props {
  data?: Record<string, unknown>;
  height?: number;
}

export function ReportFrame({ data, height = 700 }: Props) {
  const reportData = (data ?? {}) as ReportData;
  const html = reportData.html;

  if (!html) {
    return (
      <div
        className="flex items-center justify-center bg-slate-800 border border-slate-700 rounded text-slate-500 italic text-sm"
        style={{ height }}
      >
        Report not generated yet
      </div>
    );
  }

  return (
    <iframe
      srcDoc={html}
      sandbox="allow-same-origin allow-scripts"
      style={{ width: "100%", height, border: "none" }}
      className="rounded border border-slate-700"
      title="Portfolio Report"
    />
  );
}
