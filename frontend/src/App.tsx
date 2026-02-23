import { HashRouter, Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { PositionManager } from "./pages/PositionManager";
import { PositionList } from "./pages/PositionList";
import { Summary } from "./pages/Summary";
import { MarketInsights } from "./pages/MarketInsights";
import { History } from "./pages/History";

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<PositionManager />} />
          <Route path="positions" element={<PositionList />} />
          <Route path="summary" element={<Summary />} />
          <Route path="market" element={<MarketInsights />} />
          <Route path="history" element={<History />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
