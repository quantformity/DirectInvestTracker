import React from "react";
import { useSurfaceStore } from "../store/surfaces";
import { A2UIRenderer } from "../renderer/A2UIRenderer";
import { sendAction } from "../api/client";
import type { ChatMessage } from "../api/client";

interface Props {
  conversation: ChatMessage[];
  onActionResponse?: (response: string) => void;
}

export function SurfacePanel({ conversation, onActionResponse }: Props) {
  const { surfaces, activeSurfaceId } = useSurfaceStore();
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

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Surface title bar */}
      <div className="px-4 py-2 border-b border-slate-700 bg-slate-900 flex items-center gap-2">
        <span className="text-sm font-semibold text-slate-300 truncate">
          {active.title || "Untitled Surface"}
        </span>
        <span className="ml-auto text-xs text-slate-600">{active.id.slice(0, 8)}</span>
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
    </div>
  );
}
