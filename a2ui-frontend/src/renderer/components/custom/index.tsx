/**
 * Custom QFI catalog components (qfi-catalog-v1).
 * Returns undefined if the component type is not in this catalog.
 */
import React from "react";
import type { RendererContext } from "../../A2UIRenderer";

import { PositionsTable } from "./PositionsTable";
import { LineChartComp } from "./LineChart";
import { PieChartComp } from "./PieChart";
import { BarChartComp } from "./BarChart";
import { MarketQuoteCard } from "./MarketQuoteCard";
import { FxRateTable } from "./FxRateTable";
import { PortfolioKPI } from "./PortfolioKPI";
import { SectorMappingEditor } from "./SectorMappingEditor";
import { ReportFrame } from "./ReportFrame";

export function renderCustom(
  type: string,
  props: Record<string, unknown>,
  ctx: RendererContext
): React.ReactNode | undefined {
  switch (type) {
    case "PositionsTable":
      return (
        <PositionsTable
          data={(props.__data as Record<string, unknown>[]) ?? []}
          title={props.title as { literalString?: string } | undefined}
          showPnl={props.showPnl as boolean}
          showSector={props.showSector as boolean}
          columns={props.columns as string[] | undefined}
          onAction={ctx.onAction}
        />
      );

    case "LineChart":
      return (
        <LineChartComp
          data={(props.__data as Record<string, unknown>[]) ?? []}
          title={props.title as { literalString?: string } | undefined}
          xKey={props.xKey as string}
          series={(props.series as { key: string; label: string; color?: string; yAxis?: string }[] ?? []).map(s => ({ ...s, yAxis: (s.yAxis === "right" ? "right" : "left") as "left" | "right" | undefined }))}
          yLabel={props.yLabel as string}
          y2Label={props.y2Label as string}
          height={props.height as number}
        />
      );

    case "PieChart":
      return (
        <PieChartComp
          data={(props.__data as Record<string, unknown>[]) ?? []}
          title={props.title as { literalString?: string } | undefined}
          nameKey={props.nameKey as string}
          valueKey={props.valueKey as string}
          valuePrefix={props.valuePrefix as string}
          showLegend={props.showLegend as boolean}
          height={props.height as number}
        />
      );

    case "BarChart":
      return (
        <BarChartComp
          data={(props.__data as Record<string, unknown>[]) ?? []}
          title={props.title as { literalString?: string } | undefined}
          xKey={props.xKey as string}
          bars={props.bars as { key: string; label: string; color?: string }[]}
          yLabel={props.yLabel as string}
          layout={props.layout as "vertical" | "horizontal"}
          height={props.height as number}
        />
      );

    case "MarketQuoteCard":
      return (
        <MarketQuoteCard
          data={(props.__data as Record<string, unknown>[]) ?? []}
          layout={props.layout as "grid" | "list"}
          columns={props.columns as number}
        />
      );

    case "FxRateTable":
      return (
        <FxRateTable
          data={(props.__data as Record<string, unknown>[]) ?? []}
          title={props.title as { literalString?: string } | undefined}
          showTimestamp={props.showTimestamp as boolean}
        />
      );

    case "PortfolioKPI":
      return (
        <PortfolioKPI
          data={props.__data as Record<string, unknown>}
          currency={props.currency as { literalString?: string } | undefined}
        />
      );

    case "SectorMappingEditor":
      return (
        <SectorMappingEditor
          data={(props.__data as Record<string, unknown>[]) ?? []}
          title={props.title as { literalString?: string } | undefined}
          onAction={ctx.onAction}
        />
      );

    case "ReportFrame":
      return (
        <ReportFrame
          data={props.__data as Record<string, unknown>}
          height={props.height as number}
        />
      );

    default:
      return undefined;
  }
}
