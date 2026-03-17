const { app, BrowserWindow, shell } = require("electron");
const path = require("path");
const http = require("http");

const isDev = process.env.NODE_ENV !== "production" && !app.isPackaged;

function waitForFrontend(port, retries, callback) {
  const req = http.get({ host: "127.0.0.1", port, path: "/", timeout: 1000 }, (res) => {
    if (res.statusCode < 500) callback(null);
    else scheduleRetry(port, retries, callback);
  });
  req.on("error", () => scheduleRetry(port, retries, callback));
  req.on("timeout", () => { req.destroy(); scheduleRetry(port, retries, callback); });
}

function scheduleRetry(port, retries, callback) {
  if (retries <= 0) { callback(new Error("Frontend did not start")); return; }
  setTimeout(() => waitForFrontend(port, retries - 1, callback), 500);
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1600,
    height: 960,
    minWidth: 1200,
    minHeight: 700,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
    },
    show: false,
  });

  if (isDev) {
    waitForFrontend(5174, 20, () => {
      win.loadURL("http://localhost:5174");
      win.webContents.openDevTools();
    });
  } else {
    win.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  win.once("ready-to-show", () => win.show());
  setTimeout(() => { if (!win.isDestroyed() && !win.isVisible()) win.show(); }, 6000);

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
