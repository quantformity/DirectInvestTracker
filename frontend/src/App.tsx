import { HashRouter, Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { PositionManager } from "./pages/PositionManager";
import { PositionList } from "./pages/PositionList";
import { Summary } from "./pages/Summary";
import { MarketInsights } from "./pages/MarketInsights";
import { History } from "./pages/History";
import { Report } from "./pages/Report";
import { IndustryMappingPage } from "./pages/IndustryMappingPage";
import { useBackendReady } from "./hooks/useBackendReady";

function statusMessage(elapsed: number): string {
  if (elapsed < 5)  return "Starting backend…";
  if (elapsed < 15) return "Loading models and database…";
  if (elapsed < 30) return "This may take a moment on first launch…";
  return "Almost there…";
}

function LoadingScreen({ elapsed, timedOut }: { elapsed: number; timedOut: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-950 select-none">
      {/* App name */}
      <div className="mb-8 text-center">
        <div className="text-2xl font-bold text-white tracking-tight">
          Qf Direct Invest Tracker
        </div>
        <div className="text-xs text-gray-500 mt-1">Personal Portfolio Manager</div>
      </div>

      {timedOut ? (
        /* ── Error state ── */
        <div className="flex flex-col items-center gap-3 max-w-sm text-center px-6">
          <div className="text-3xl">⚠️</div>
          <p className="text-red-400 text-sm font-medium">Backend failed to start</p>
          <p className="text-gray-400 text-xs leading-relaxed">
            The backend service did not respond within 90 seconds.
            Check the error dialog or the backend log file for details.
          </p>
        </div>
      ) : (
        /* ── Loading state ── */
        <div className="flex flex-col items-center gap-4">
          {/* Spinner */}
          <svg
            className="animate-spin h-9 w-9 text-blue-500"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-20"
              cx="12" cy="12" r="10"
              stroke="currentColor" strokeWidth="3"
            />
            <path
              className="opacity-90"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>

          {/* Status */}
          <p className="text-gray-400 text-sm">{statusMessage(elapsed)}</p>

          {/* Elapsed time — only shown after 5 s so it doesn't flicker on fast starts */}
          {elapsed >= 5 && (
            <p className="text-gray-600 text-xs">{elapsed}s</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const { ready, elapsed, timedOut } = useBackendReady();

  if (!ready) {
    return <LoadingScreen elapsed={elapsed} timedOut={timedOut} />;
  }

  return (
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<PositionManager />} />
          <Route path="positions" element={<PositionList />} />
          <Route path="summary" element={<Summary />} />
          <Route path="market" element={<MarketInsights />} />
          <Route path="history" element={<History />} />
          <Route path="industry" element={<IndustryMappingPage />} />
        </Route>
        <Route path="report" element={<Report />} />
      </Routes>
    </HashRouter>
  );
}
