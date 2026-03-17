/**
 * Standard A2UI v0.8 components.
 * Returns undefined if the component type is not handled here.
 */
import React, { useState } from "react";
import type { RendererContext } from "../../A2UIRenderer";
import { renderNode, resolveBinding } from "../../A2UIRenderer";

function resolveText(v: unknown): string {
  if (typeof v === "string") return v;
  if (typeof v === "object" && v !== null) {
    const o = v as Record<string, unknown>;
    if ("literalString" in o) return String(o.literalString);
  }
  return "";
}

function resolveChildren(
  children: unknown,
  ctx: RendererContext
): React.ReactNode[] {
  if (!children) return [];
  if (typeof children === "object" && children !== null) {
    const c = children as Record<string, unknown>;
    if (Array.isArray(c.explicitList)) {
      return (c.explicitList as string[]).map((id) => (
        <React.Fragment key={id}>{renderNode(id, ctx)}</React.Fragment>
      ));
    }
  }
  return [];
}

// ── Text ──────────────────────────────────────────────────────────────────────

function TextComp({
  text,
  usageHint,
}: {
  text: unknown;
  usageHint?: string;
}) {
  const content = resolveText(text);
  if (usageHint === "h1")
    return <h1 className="text-2xl font-bold text-white mb-2">{content}</h1>;
  if (usageHint === "h2")
    return <h2 className="text-xl font-semibold text-white mb-1">{content}</h2>;
  if (usageHint === "h3")
    return <h3 className="text-lg font-semibold text-slate-200 mb-1">{content}</h3>;
  if (usageHint === "caption")
    return <p className="text-xs text-slate-400">{content}</p>;
  return <p className="text-slate-300">{content}</p>;
}

// ── Column / Row ──────────────────────────────────────────────────────────────

function ColumnComp({
  children,
  gap,
  ctx,
}: {
  children: unknown;
  gap?: string;
  ctx: RendererContext;
}) {
  const gapClass = gap === "small" ? "gap-2" : gap === "large" ? "gap-6" : "gap-4";
  return (
    <div className={`flex flex-col ${gapClass}`}>{resolveChildren(children, ctx)}</div>
  );
}

function RowComp({
  children,
  distribution,
  ctx,
}: {
  children: unknown;
  distribution?: string;
  ctx: RendererContext;
}) {
  const justify =
    distribution === "spaceBetween"
      ? "justify-between"
      : distribution === "spaceAround"
      ? "justify-around"
      : distribution === "center"
      ? "justify-center"
      : "justify-start";
  return (
    <div className={`flex flex-row gap-4 ${justify} items-stretch`}>
      {resolveChildren(children, ctx)}
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────

function CardComp({
  title,
  children,
  ctx,
}: {
  title?: unknown;
  children: unknown;
  ctx: RendererContext;
}) {
  return (
    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
      {Boolean(title) && (
        <h3 className="text-sm font-semibold text-slate-300 mb-3">
          {resolveText(title)}
        </h3>
      )}
      {resolveChildren(children, ctx)}
    </div>
  );
}

// ── Divider ───────────────────────────────────────────────────────────────────

function DividerComp({ axis }: { axis?: string }) {
  if (axis === "vertical")
    return <div className="w-px bg-slate-700 self-stretch mx-2" />;
  return <hr className="border-slate-700 my-2" />;
}

// ── Button ────────────────────────────────────────────────────────────────────

function ButtonComp({
  label,
  actionName,
  actionContext,
  variant,
  onAction,
}: {
  label: unknown;
  actionName?: string;
  actionContext?: Record<string, unknown>;
  variant?: string;
  onAction: (name: string, ctx: Record<string, unknown>) => void;
}) {
  const text = resolveText(label);
  const base = "px-3 py-1.5 rounded text-sm font-medium transition-colors cursor-pointer";
  const cls =
    variant === "danger"
      ? `${base} bg-red-700 hover:bg-red-600 text-white`
      : variant === "secondary"
      ? `${base} bg-slate-700 hover:bg-slate-600 text-slate-200`
      : `${base} bg-blue-600 hover:bg-blue-500 text-white`;

  return (
    <button
      className={cls}
      onClick={() => actionName && onAction(actionName, actionContext ?? {})}
    >
      {text}
    </button>
  );
}

// ── List ──────────────────────────────────────────────────────────────────────

function ListComp({
  items,
  dataModel,
}: {
  items?: unknown[];
  __data?: unknown;
  dataModel?: Record<string, unknown>;
}) {
  const rows = Array.isArray(items) ? items : [];
  if (rows.length === 0)
    return <p className="text-slate-400 text-sm italic">No items.</p>;
  return (
    <ul className="space-y-1">
      {rows.map((item, i) => (
        <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
          <span className="text-slate-500 mt-0.5">•</span>
          <span>{typeof item === "string" ? item : JSON.stringify(item)}</span>
        </li>
      ))}
    </ul>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

function TabsComp({
  tabs,
  ctx,
}: {
  tabs: { label: string; children: unknown }[];
  ctx: RendererContext;
}) {
  const [active, setActive] = useState(0);
  if (!tabs?.length) return null;
  return (
    <div className="flex flex-col gap-0">
      <div className="flex gap-0 border-b border-slate-700">
        {tabs.map((tab, i) => (
          <button
            key={i}
            onClick={() => setActive(i)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              i === active
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="pt-4">{resolveChildren(tabs[active]?.children, ctx)}</div>
    </div>
  );
}

// ── Image ─────────────────────────────────────────────────────────────────────

function ImageComp({ url, alt, height }: { url: unknown; alt?: unknown; height?: number }) {
  const src = resolveText(url);
  const altText = resolveText(alt);
  return (
    <img
      src={src}
      alt={altText}
      style={{ height: height ? `${height}px` : "auto", maxWidth: "100%" }}
      className="rounded"
    />
  );
}

// ── TextField ─────────────────────────────────────────────────────────────────

function TextFieldComp({
  label,
  placeholder,
  actionName,
  onAction,
}: {
  label?: unknown;
  placeholder?: unknown;
  actionName?: string;
  onAction: (name: string, ctx: Record<string, unknown>) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <div className="flex flex-col gap-1">
      {Boolean(label) && (
        <label className="text-xs text-slate-400">{resolveText(label)}</label>
      )}
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={resolveText(placeholder)}
          className="flex-1 bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
          onKeyDown={(e) => {
            if (e.key === "Enter" && actionName) {
              onAction(actionName, { value });
              setValue("");
            }
          }}
        />
        {actionName && (
          <button
            onClick={() => { onAction(actionName, { value }); setValue(""); }}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm"
          >
            Submit
          </button>
        )}
      </div>
    </div>
  );
}

// ── MultipleChoice ────────────────────────────────────────────────────────────

function MultipleChoiceComp({
  label,
  options,
  actionName,
  onAction,
}: {
  label?: unknown;
  options?: string[];
  actionName?: string;
  onAction: (name: string, ctx: Record<string, unknown>) => void;
}) {
  const [selected, setSelected] = useState("");
  return (
    <div className="flex flex-col gap-1">
      {Boolean(label) && (
        <label className="text-xs text-slate-400">{resolveText(label)}</label>
      )}
      <select
        value={selected}
        onChange={(e) => {
          setSelected(e.target.value);
          if (actionName) onAction(actionName, { value: e.target.value });
        }}
        className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
      >
        <option value="">Select...</option>
        {options?.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

// ── CheckBox ──────────────────────────────────────────────────────────────────

function CheckBoxComp({
  label,
  checked: initialChecked,
  actionName,
  onAction,
}: {
  label?: unknown;
  checked?: boolean;
  actionName?: string;
  onAction: (name: string, ctx: Record<string, unknown>) => void;
}) {
  const [checked, setChecked] = useState(!!initialChecked);
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => {
          setChecked(e.target.checked);
          if (actionName) onAction(actionName, { checked: e.target.checked });
        }}
        className="w-4 h-4 accent-blue-500"
      />
      <span className="text-sm text-slate-300">{resolveText(label)}</span>
    </label>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function ModalComp({
  title,
  open,
  children,
  ctx,
}: {
  title?: unknown;
  open?: boolean;
  children: unknown;
  ctx: RendererContext;
}) {
  const [visible, setVisible] = useState(!!open);
  if (!visible) return null;
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 w-full max-w-lg shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">{resolveText(title)}</h2>
          <button
            onClick={() => setVisible(false)}
            className="text-slate-400 hover:text-white text-xl leading-none"
          >
            ×
          </button>
        </div>
        {resolveChildren(children, ctx)}
      </div>
    </div>
  );
}

// ── Dispatch ──────────────────────────────────────────────────────────────────

export function renderStandard(
  type: string,
  props: Record<string, unknown>,
  ctx: RendererContext
): React.ReactNode | undefined {
  const { onAction } = ctx;

  switch (type) {
    case "Text":
      return <TextComp text={props.text} usageHint={props.usageHint as string} />;

    case "Column":
      return <ColumnComp children={props.children} gap={props.gap as string} ctx={ctx} />;

    case "Row":
      return (
        <RowComp
          children={props.children}
          distribution={props.distribution as string}
          ctx={ctx}
        />
      );

    case "Card":
      return <CardComp title={props.title} children={props.children} ctx={ctx} />;

    case "Divider":
      return <DividerComp axis={props.axis as string} />;

    case "Button":
      return (
        <ButtonComp
          label={props.label}
          actionName={props.actionName as string}
          actionContext={props.actionContext as Record<string, unknown>}
          variant={props.variant as string}
          onAction={onAction}
        />
      );

    case "List":
      return (
        <ListComp
          items={(props.__data as unknown[]) ?? (props.items as unknown[])}
          dataModel={ctx.dataModel}
        />
      );

    case "Tabs":
      return (
        <TabsComp
          tabs={props.tabs as { label: string; children: unknown }[]}
          ctx={ctx}
        />
      );

    case "Image":
      return (
        <ImageComp
          url={props.url}
          alt={props.alt}
          height={props.height as number}
        />
      );

    case "TextField":
      return (
        <TextFieldComp
          label={props.label}
          placeholder={props.placeholder}
          actionName={props.actionName as string}
          onAction={onAction}
        />
      );

    case "MultipleChoice":
      return (
        <MultipleChoiceComp
          label={props.label}
          options={props.options as string[]}
          actionName={props.actionName as string}
          onAction={onAction}
        />
      );

    case "CheckBox":
      return (
        <CheckBoxComp
          label={props.label}
          checked={props.checked as boolean}
          actionName={props.actionName as string}
          onAction={onAction}
        />
      );

    case "Modal":
      return (
        <ModalComp title={props.title} open={props.open as boolean} children={props.children} ctx={ctx} />
      );

    case "Slider":
      return (
        <div className="flex flex-col gap-1">
          {Boolean(props.label) && (
            <label className="text-xs text-slate-400">
              {resolveText(props.label)}
            </label>
          )}
          <input
            type="range"
            min={props.min as number ?? 0}
            max={props.max as number ?? 100}
            step={props.step as number ?? 1}
            className="w-full accent-blue-500"
          />
        </div>
      );

    case "DateTimeInput":
      return (
        <div className="flex flex-col gap-1">
          {Boolean(props.label) && (
            <label className="text-xs text-slate-400">
              {resolveText(props.label)}
            </label>
          )}
          <input
            type="date"
            className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
          />
        </div>
      );

    default:
      return undefined;
  }
}
