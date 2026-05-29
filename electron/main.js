/**
 * SampleForge Electron Main Process
 *
 * Launches the Python/PySide6 application and manages its lifecycle.
 * Electron provides native OS integration: installer, tray, file associations.
 */
const { app, BrowserWindow, dialog, Menu, Tray, nativeImage } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");

// ---------------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------------
let mainWindow = null;
let pyProcess = null;
let tray = null;
let isQuitting = false;

// ---------------------------------------------------------------------------
// Python process management
// ---------------------------------------------------------------------------

function findPython() {
  // Priority: bundled Python > system python3 > system python
  const bundled = path.join(process.resourcesPath, "python", "python.exe");
  if (fs.existsSync(bundled)) return bundled;
  if (process.platform === "win32") return "python";
  return "python3";
}

function startPythonApp() {
  const pythonExe = findPython();
  const appRoot = path.join(__dirname, "..");

  const args = ["-u", path.join(appRoot, "main.py")];

  const env = {
    ...process.env,
    SAMPLEFORGE_DATA_DIR: path.join(app.getPath("userData"), "data"),
    ELECTRON_RUN: "1",
  };

  pyProcess = spawn(pythonExe, args, {
    cwd: appRoot,
    env,
    stdio: ["pipe", "pipe", "pipe"],
  });

  pyProcess.stdout.on("data", (data) => {
    console.log(`[python] ${data.toString().trim()}`);
  });

  pyProcess.stderr.on("data", (data) => {
    console.error(`[python:err] ${data.toString().trim()}`);
  });

  pyProcess.on("error", (err) => {
    dialog.showErrorBox(
      "Python Error",
      `Failed to start Python process:\n${err.message}\n\n` +
        "Please ensure Python 3.10–3.12 is installed and in your PATH."
    );
    app.quit();
  });

  pyProcess.on("close", (code) => {
    console.log(`Python process exited with code ${code}`);
    pyProcess = null;
    if (!isQuitting) app.quit();
  });
}

function stopPythonApp() {
  if (!pyProcess) return;
  if (process.platform === "win32") {
    spawn("taskkill", ["/pid", pyProcess.pid.toString(), "/f", "/t"]);
  } else {
    pyProcess.kill("SIGTERM");
  }
}

// ---------------------------------------------------------------------------
// Window management
// ---------------------------------------------------------------------------

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    title: "SampleForge",
    backgroundColor: "#141414",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "renderer", "launcher.html"));

  mainWindow.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    startPythonApp();
  });
}

// ---------------------------------------------------------------------------
// System tray
// ---------------------------------------------------------------------------

function createTray() {
  try {
    const iconPath = path.join(__dirname, "..", "assets", "tray-icon.png");
    if (fs.existsSync(iconPath)) {
      tray = new Tray(iconPath);
    }
  } catch {
    return;
  }

  if (!tray) return;

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Show SampleForge",
      click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } },
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => { isQuitting = true; app.quit(); },
    },
  ]);

  tray.setToolTip("SampleForge");
  tray.setContextMenu(contextMenu);
  tray.on("double-click", () => {
    if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
  });
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

app.whenReady().then(() => {
  createMainWindow();
  createTray();

  app.on("activate", () => {
    if (mainWindow) mainWindow.show();
    else createMainWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    isQuitting = true;
    stopPythonApp();
    app.quit();
  }
});

app.on("before-quit", () => {
  isQuitting = true;
  stopPythonApp();
});

app.on("quit", () => {
  stopPythonApp();
});
