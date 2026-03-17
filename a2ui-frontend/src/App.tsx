import React, { useState } from "react";
import { HistoryPanel } from "./panels/HistoryPanel";
import { SurfacePanel } from "./panels/SurfacePanel";
import { ChatPanel } from "./panels/ChatPanel";
import type { ChatMessage } from "./api/client";

export default function App() {
  const [conversation, setConversation] = useState<ChatMessage[]>([]);

  const handleActionResponse = (response: string) => {
    setConversation((prev) => [
      ...prev,
      { role: "assistant", content: response },
    ]);
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950">
      {/* Left panel — surface history */}
      <HistoryPanel />

      {/* Centre panel — active A2UI surface */}
      <SurfacePanel
        conversation={conversation}
        onActionResponse={handleActionResponse}
      />

      {/* Right panel — chat */}
      <ChatPanel />
    </div>
  );
}
