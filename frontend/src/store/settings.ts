import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsState {
  reportingCurrency: string;
  apiUrl: string;
  setReportingCurrency: (currency: string) => void;
  setApiUrl: (url: string) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      reportingCurrency: "CAD",
      apiUrl: "http://localhost:8000",
      setReportingCurrency: (currency) => set({ reportingCurrency: currency }),
      setApiUrl: (url) => set({ apiUrl: url }),
    }),
    {
      name: "qf-direct-invest-tracker-settings",
    }
  )
);
