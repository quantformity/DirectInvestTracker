const { app, BrowserWindow, shell, ipcMain, dialog, Menu } = require("electron");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");
const http = require("http");

const isDev = process.env.NODE_ENV !== "production" && !app.isPackaged;

let backendProcess = null;

// ── Config management (userData/app-config.json) ──────────────────────────────

function getConfigPath() {
  return path.join(app.getPath("userData"), "app-config.json");
}

function loadConfig() {
  try {
    return JSON.parse(fs.readFileSync(getConfigPath(), "utf8"));
  } catch {
    return {};
  }
}

function saveConfig(data) {
  const merged = { ...loadConfig(), ...data };
  fs.writeFileSync(getConfigPath(), JSON.stringify(merged, null, 2));
}

function getDbPath() {
  const config = loadConfig();
  return config.dbPath || path.join(app.getPath("userData"), "investments.db");
}

// ── Backend process management ────────────────────────────────────────────────

function getBackendBinPath() {
  if (isDev) return null;
  const binName =
    process.platform === "win32"
      ? "investments-backend.exe"
      : "investments-backend";
  return path.join(process.resourcesPath, "backend", binName);
}

function waitForBackend(port, retries, callback) {
  const req = http.get(
    { host: "127.0.0.1", port, path: "/", timeout: 1000 },
    (res) => {
      if (res.statusCode === 200) {
        callback(null);
      } else {
        scheduleRetry(port, retries, callback);
      }
    }
  );
  req.on("error", () => scheduleRetry(port, retries, callback));
  req.on("timeout", () => {
    req.destroy();
    scheduleRetry(port, retries, callback);
  });
}

function scheduleRetry(port, retries, callback) {
  if (retries <= 0) {
    callback(new Error("Backend did not respond after timeout"));
    return;
  }
  setTimeout(() => waitForBackend(port, retries - 1, callback), 500);
}

function startBackend() {
  return new Promise((resolve, reject) => {
    const binPath = getBackendBinPath();

    if (!binPath) {
      waitForBackend(8000, 10, (err) => {
        if (err) console.warn("Dev backend not detected, continuing anyway.");
        resolve();
      });
      return;
    }

    const dbPath = getDbPath().replace(/\\/g, "/");
    const dbUrl = `sqlite:///${dbPath}`;

    // Ensure the database directory exists
    const dbDir = path.dirname(dbPath);
    if (dbDir) fs.mkdirSync(dbDir, { recursive: true });

    backendProcess = spawn(binPath, [], {
      env: { ...process.env, DATABASE_URL: dbUrl, PORT: "8000" },
      stdio: "ignore",
    });

    backendProcess.on("error", (err) => {
      reject(new Error(`Failed to start backend: ${err.message}`));
    });

    waitForBackend(8000, 60, (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill("SIGTERM");
    backendProcess = null;
  }
}

// ── Window management ─────────────────────────────────────────────────────────

function buildMenu(win) {
  const template = [
    {
      label: "File",
      submenu: [
        {
          label: "Settings…",
          accelerator: "CmdOrCtrl+,",
          click: () => win.webContents.send("open-settings"),
        },
        { type: "separator" },
        { role: "quit" },
      ],
    },
    { role: "editMenu" },
    { role: "viewMenu" },
    { role: "windowMenu" },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
    },
    titleBarStyle: "default",
    show: false,
  });

  buildMenu(win);

  if (isDev) {
    win.loadURL("http://localhost:5173");
    win.webContents.openDevTools();
  } else {
    win.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  win.once("ready-to-show", () => win.show());

  // Fallback: if the renderer fails to load, show the window anyway so the
  // error is visible rather than leaving a permanently hidden window.
  win.webContents.on("did-fail-load", (_e, code, desc) => {
    console.error(`Renderer failed to load (${code}): ${desc}`);
    win.show();
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

// ── IPC handlers ──────────────────────────────────────────────────────────────

function registerIpcHandlers() {
  // Return the current database file path
  ipcMain.handle("db:get-path", () => getDbPath());

  // Open a native save-file dialog so the user can pick a new DB location
  ipcMain.handle("db:select-file", async () => {
    const result = await dialog.showSaveDialog({
      title: "Choose database file location",
      defaultPath: getDbPath(),
      filters: [{ name: "SQLite Database", extensions: ["db"] }],
      properties: ["createDirectory"],
    });
    return result.canceled ? null : result.filePath;
  });

  // Persist the chosen path to config.json (takes effect on next launch / relaunch)
  ipcMain.handle("db:set-path", (_event, newPath) => {
    saveConfig({ dbPath: newPath });
    return newPath;
  });

  // Relaunch the app so the new database path is picked up
  ipcMain.handle("app:relaunch", () => {
    app.relaunch();
    app.quit();
  });
}

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  registerIpcHandlers();

  startBackend()
    .then(() => {
      createWindow();
      app.on("activate", () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
      });
    })
    .catch((err) => {
      console.error("Fatal: could not start backend —", err.message);
      app.quit();
    });
});

app.on("before-quit", stopBackend);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
