/**
 * Preload script — exposes limited IPC APIs to the renderer process.
 */
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("sampleforge", {
  getVersion: () => ipcRenderer.invoke("get-version"),
  getUserDataPath: () => ipcRenderer.invoke("get-user-data-path"),
  getPythonStatus: () => ipcRenderer.invoke("get-python-status"),
  onPythonReady: (callback) => ipcRenderer.on("python-ready", callback),
  onPythonError: (callback) => ipcRenderer.on("python-error", (_event, msg) => callback(msg)),
  onPythonExit: (callback) => ipcRenderer.on("python-exit", (_event, code) => callback(code)),
});
