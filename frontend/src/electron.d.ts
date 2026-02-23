// Type declarations for the Electron contextBridge API exposed via preload.cjs

interface ElectronAPI {
  platform: string;
  db: {
    getPath:    () => Promise<string>;
    selectFile: () => Promise<string | null>;
    setPath:    (newPath: string) => Promise<string>;
  };
  app: {
    relaunch: () => Promise<void>;
    onOpenSettings: (cb: () => void) => void;
    removeOpenSettingsListener: (cb: () => void) => void;
  };
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
