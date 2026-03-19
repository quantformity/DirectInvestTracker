import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface SurfaceEntry {
  id: string;
  /** Sequential display number, e.g. 1, 2, 3 */
  number: number;
  title: string;
  /** Root component ID (from beginRendering.root) */
  rootId: string;
  /** Full A2UI component list for this surface */
  components: object[];
  /** Hydrated data model: path → data */
  dataModel: Record<string, unknown>;
  createdAt: string;
  /** Updated when data is refreshed by the quote updater */
  updatedAt: string;
}

interface SurfaceState {
  surfaces: SurfaceEntry[];
  activeSurfaceId: string | null;
  /** Monotonically increasing counter for display numbers */
  nextNumber: number;

  addOrUpdateSurface: (entry: Omit<SurfaceEntry, "number" | "updatedAt"> & { number?: number; updatedAt?: string }) => void;
  setActiveSurface: (id: string) => void;
  deleteSurface: (id: string) => void;
  clearAll: () => void;
  /** Merge fresh data into an existing surface's dataModel and update updatedAt */
  patchDataModel: (id: string, partial: Record<string, unknown>) => void;
}

export const useSurfaceStore = create<SurfaceState>()(
  persist(
    (set, get) => ({
      surfaces: [],
      activeSurfaceId: null,
      nextNumber: 1,

      addOrUpdateSurface: (entry) =>
        set((state) => {
          const existing = state.surfaces.findIndex((s) => s.id === entry.id);
          const now = new Date().toISOString();

          if (existing >= 0) {
            // Update in-place, preserve number
            const updated = [...state.surfaces];
            updated[existing] = {
              ...updated[existing],
              ...entry,
              number: updated[existing].number,
              updatedAt: now,
            };
            return { surfaces: updated, activeSurfaceId: entry.id };
          }

          // New surface — assign next sequential number
          const number = entry.number ?? state.nextNumber;
          const newEntry: SurfaceEntry = {
            ...entry,
            number,
            updatedAt: entry.updatedAt ?? now,
          } as SurfaceEntry;

          return {
            surfaces: [newEntry, ...state.surfaces].slice(0, 50),
            activeSurfaceId: entry.id,
            nextNumber: Math.max(state.nextNumber, number) + 1,
          };
        }),

      setActiveSurface: (id) => set({ activeSurfaceId: id }),

      deleteSurface: (id) =>
        set((state) => ({
          surfaces: state.surfaces.filter((s) => s.id !== id),
          activeSurfaceId:
            state.activeSurfaceId === id
              ? (state.surfaces.find((s) => s.id !== id)?.id ?? null)
              : state.activeSurfaceId,
        })),

      clearAll: () => set({ surfaces: [], activeSurfaceId: null, nextNumber: 1 }),

      patchDataModel: (id, partial) =>
        set((state) => {
          const idx = state.surfaces.findIndex((s) => s.id === id);
          if (idx < 0) return state;
          const updated = [...state.surfaces];
          updated[idx] = {
            ...updated[idx],
            dataModel: { ...updated[idx].dataModel, ...partial },
            updatedAt: new Date().toISOString(),
          };
          return { surfaces: updated };
        }),
    }),
    { name: "qfi-a2ui-surfaces" }
  )
);
