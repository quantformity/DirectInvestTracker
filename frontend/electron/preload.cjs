const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,

  db: {
    getPath:    ()          => ipcRenderer.invoke("db:get-path"),
    selectFile: ()          => ipcRenderer.invoke("db:select-file"),
    setPath:    (newPath)   => ipcRenderer.invoke("db:set-path", newPath),
  },

  app: {
    relaunch: () => ipcRenderer.invoke("app:relaunch"),
    onOpenSettings: (cb) => ipcRenderer.on("open-settings", cb),
    removeOpenSettingsListener: (cb) => ipcRenderer.removeListener("open-settings", cb),
  },

  pdf: {
    save: () => ipcRenderer.invoke("pdf:save"),
  },
});
