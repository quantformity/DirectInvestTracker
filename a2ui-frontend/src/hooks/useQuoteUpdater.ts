/**
 * useQuoteUpdater — background poller that refreshes live market data every 3 minutes.
 *
 * On each tick it calls GET /data/prices, which returns the latest hydrated data
 * for market/quotes, positions/rows, and portfolio/kpi.
 *
 * It then patches the dataModel of every surface in the store that references
 * any of those paths, so charts and tables re-render automatically.
 */
import { useEffect } from "react";
import { useSurfaceStore } from "../store/surfaces";
import { fetchLivePrices } from "../api/client";

const POLL_INTERVAL_MS = 3 * 60 * 1000; // 3 minutes

export function useQuoteUpdater() {
  const { surfaces, patchDataModel } = useSurfaceStore();

  useEffect(() => {
    async function refresh() {
      try {
        const prices = await fetchLivePrices();
        if (!prices || Object.keys(prices).length === 0) return;

        // Patch every surface whose dataModel contains any of the refreshed paths
        for (const surface of surfaces) {
          const updates: Record<string, unknown> = {};
          for (const [path, data] of Object.entries(prices)) {
            if (path in surface.dataModel) {
              updates[path] = data;
            }
          }
          if (Object.keys(updates).length > 0) {
            patchDataModel(surface.id, updates);
          }
        }
      } catch {
        // Network error — silently skip this tick
      }
    }

    // Run once immediately on mount, then on interval
    refresh();
    const timer = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
    // Re-subscribe whenever surfaces list changes (new surface added)
  }, [surfaces.length, patchDataModel]);
}
