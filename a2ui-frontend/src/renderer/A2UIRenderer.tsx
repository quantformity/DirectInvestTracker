/**
 * A2UI Renderer — walks the flat adjacency-list component tree and renders it.
 *
 * Component model:
 *   { id: string, component: { <TypeName>: { ...props } }, weight?: number }
 *
 * Data binding resolution:
 *   { "dataBinding": "/positions/rows" } → look up dataModel["/positions/rows"]
 */
import React from "react";

import { renderStandard } from "./components/standard";
import { renderCustom } from "./components/custom";

export interface A2UIComponent {
  id: string;
  component: Record<string, Record<string, unknown>>;
  weight?: number;
}

export interface RendererContext {
  components: Map<string, A2UIComponent>;
  dataModel: Record<string, unknown>;
  onAction: (name: string, context: Record<string, unknown>) => void;
  primaryColor?: string;
}

/** Resolve a data binding: returns the value from dataModel or undefined */
export function resolveBinding(
  value: unknown,
  dataModel: Record<string, unknown>
): unknown {
  if (value === null || value === undefined) return value;
  if (typeof value === "object" && value !== null) {
    const v = value as Record<string, unknown>;
    if ("literalString" in v) return v.literalString;
    if ("literalNumber" in v) return v.literalNumber;
    if ("literalBoolean" in v) return v.literalBoolean;
    if ("path" in v || "dataBinding" in v) {
      const path = (v.path ?? v.dataBinding) as string;
      const key = path.startsWith("/") ? path.slice(1) : path;
      return dataModel[key] ?? dataModel[path];
    }
  }
  return value;
}

/** Render a single component node */
export function renderNode(id: string, ctx: RendererContext): React.ReactNode {
  const entry = ctx.components.get(id);
  if (!entry) return null;

  const [typeName, props] = Object.entries(entry.component)[0] ?? [];
  if (!typeName) return null;

  // Resolve dataBinding shorthand
  const resolvedProps: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    if (k === "dataBinding") {
      const path = v as string;
      const key = path.startsWith("/") ? path.slice(1) : path;
      resolvedProps.__data = ctx.dataModel[key] ?? ctx.dataModel[path] ?? [];
      resolvedProps.dataBinding = v;
    } else {
      resolvedProps[k] = v;
    }
  }

  // Try custom catalog first, then standard
  const customResult = renderCustom(typeName, resolvedProps, ctx);
  if (customResult !== undefined) return customResult;

  const standardResult = renderStandard(typeName, resolvedProps, ctx);
  if (standardResult !== undefined) return standardResult;

  // Unknown component — render a debug placeholder
  return (
    <div
      key={id}
      className="p-2 border border-yellow-600 rounded text-yellow-400 text-xs"
    >
      Unknown component: <code>{typeName}</code>
    </div>
  );
}

interface A2UIRendererProps {
  rootId: string;
  components: A2UIComponent[];
  dataModel: Record<string, unknown>;
  onAction: (name: string, context: Record<string, unknown>) => void;
  primaryColor?: string;
}

export function A2UIRenderer({
  rootId,
  components,
  dataModel,
  onAction,
  primaryColor = "#3b82f6",
}: A2UIRendererProps) {
  const compMap = new Map(components.map((c) => [c.id, c]));
  const ctx: RendererContext = { components: compMap, dataModel, onAction, primaryColor };

  return (
    <div className="a2ui-surface h-full overflow-auto p-4">
      {renderNode(rootId, ctx)}
    </div>
  );
}
