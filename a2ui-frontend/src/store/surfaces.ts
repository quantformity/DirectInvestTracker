import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface SurfaceEntry {
  id: string;
  title: string;
  /** Root component ID (from beginRendering.root) */
  rootId: string;
  /** Full A2UI component list for this surface */
  components: object[];
  /** Hydrated data model: path → data */
  dataModel: Record<string, unknown>;
  createdAt: string;
}

interface SurfaceState {
  surfaces: SurfaceEntry[];
  activeSurfaceId: string | null;

  addOrUpdateSurface: (entry: SurfaceEntry) => void;
  setActiveSurface: (id: string) => void;
  deleteSurface: (id: string) => void;
  clearAll: () => void;
}

export const useSurfaceStore = create<SurfaceState>()(
  persist(
    (set) => ({
      surfaces: [],
      activeSurfaceId: null,

      addOrUpdateSurface: (entry) =>
        set((state) => {
          const existing = state.surfaces.findIndex((s) => s.id === entry.id);
          if (existing >= 0) {
            const updated = [...state.surfaces];
            updated[existing] = entry;
            return { surfaces: updated, activeSurfaceId: entry.id };
          }
          return {
            surfaces: [entry, ...state.surfaces].slice(0, 50), // keep last 50
            activeSurfaceId: entry.id,
          };
        }),

      setActiveSurface: (id) => set({ activeSurfaceId: id }),

      deleteSurface: (id) =>
        set((state) => ({
          surfaces: state.surfaces.filter((s) => s.id !== id),
          activeSurfaceId:
            state.activeSurfaceId === id ? null : state.activeSurfaceId,
        })),

      clearAll: () => set({ surfaces: [], activeSurfaceId: null }),
    }),
    {
      name: "qfi-a2ui-surfaces",
    }
  )
);
