/**
 * SampleForge Electron Main Process
 *
 * Launches the Python/PySide6 application and manages its lifecycle.
 * Bundles a portable Python 3.12 runtime — no system Python required.
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
// Path helpers
// ---------------------------------------------------------------------------

function isDev() {
  return !app.isPackaged;
}

function getPythonDir() {
  // Dev: electron/python/   Prod: resources/python/
  if (isDev()) return path.join(__dirname, "python");
  return path.join(process.resourcesPath, "python");
}

function getPythonExe() {
  const exe = path.join(getPythonDir(), "python.exe");
  if (fs.existsSync(exe)) return exe;
  // Fallback: system Python
  return process.platform === "win32" ? "python" : "python3";
}

function getAppRoot() {
  // Dev: __dirname/.. = SamlpeForge root
  // Prod: extraResources puts .py files at resources/, not inside app/
  if (isDev()) return path.join(__dirname, "..");
  return process.resourcesPath;
}

function getIconPath() {
  // Prefer .ico on Windows for best compatibility
  const names = process.platform === "win32"
    ? ["icon.ico", "icon.png"]
    : ["icon.png", "icon.ico"];
  for (const name of names) {
    const p = path.join(__dirname, name);
    if (fs.existsSync(p)) return p;
  }
  // Fallback for dev: ../assets/
  for (const name of names) {
    const p = path.join(__dirname, "..", "assets", name);
    if (fs.existsSync(p)) return p;
  }
  return path.join(__dirname, "icon.png");
}

// ---------------------------------------------------------------------------
// Python process management
// ---------------------------------------------------------------------------

function startPythonApp() {
  const pythonExe = getPythonExe();
  const pythonDir = getPythonDir();
  const appRoot = getAppRoot();
  const mainPy = path.join(appRoot, "main.py");

  console.log(`[electron] Python exe: ${pythonExe} (exists: ${fs.existsSync(pythonExe)})`);
  console.log(`[electron] Python dir: ${pythonDir}`);
  console.log(`[electron] App root:   ${appRoot}`);
  console.log(`[electron] main.py:    ${mainPy} (exists: ${fs.existsSync(mainPy)})`);

  // If bundled Python is missing, show detailed error
  if (!fs.existsSync(pythonExe)) {
    dialog.showErrorBox(
      "Python Engine Error",
      `Bundled Python not found at:\n${pythonExe}\n\n` +
      `Python dir contents: ${fs.existsSync(pythonDir) ? fs.readdirSync(pythonDir).slice(0, 10).join(", ") : "(dir missing)"}`
    );
    app.quit();
    return;
  }

  if (!fs.existsSync(mainPy)) {
    dialog.showErrorBox(
      "Python Engine Error",
      `main.py not found at:\n${mainPy}\n\n` +
      `App root contents: ${fs.readdirSync(appRoot).slice(0, 20).join(", ")}`
    );
    app.quit();
    return;
  }

  const args = ["-u", mainPy];

  // Build environment: add bundled Python & site-packages to PATH/PYTHONPATH
  const env = {
    ...process.env,
    SAMPLEFORGE_DATA_DIR: path.join(app.getPath("userData"), "data"),
    ELECTRON_RUN: "1",
    PATH: [
      pythonDir,
      path.join(pythonDir, "Scripts"),
      path.join(pythonDir, "DLLs"),
      process.env.PATH,
    ].join(path.delimiter),
    PYTHONHOME: pythonDir,
  };

  // Remove system Python paths to avoid conflicts with bundled version
  delete env.VIRTUAL_ENV;
  delete env.PYTHONPATH;

  pyProcess = spawn(pythonExe, args, {
    cwd: appRoot,
    env,
    stdio: ["pipe", "pipe", "pipe"],
  });

  let firstOutput = true;
  pyProcess.stdout.on("data", (data) => {
    const msg = data.toString().trim();
    console.log(`[python] ${msg}`);
    // Hide the launcher window once Python starts producing output.
    // The PySide6 app creates its own native window.
    if (firstOutput) {
      firstOutput = false;
      setTimeout(() => {
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.hide();
        }
      }, 1500); // give Qt window time to appear
    }
  });

  pyProcess.stderr.on("data", (data) => {
    console.error(`[python:err] ${data.toString().trim()}`);
  });

  pyProcess.on("error", (err) => {
    dialog.showErrorBox(
      "Python Engine Error",
      `Failed to start Python engine:\n${err.message}\n\nPath: ${pythonExe}`
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
  const iconPath = getIconPath();
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    title: "SampleForge",
    backgroundColor: "#141414",
    show: false,
    icon: iconPath,
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
    const iconPath = getIconPath();
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
