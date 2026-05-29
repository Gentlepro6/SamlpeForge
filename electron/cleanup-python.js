/**
 * Clean up portable Python installation before packaging.
 * Removes unneeded files to reduce installer size.
 */
const fs = require("fs");
const path = require("path");

const PYTHON_DIR = path.join(__dirname, "python");

function rmDir(dir) {
  if (fs.existsSync(dir)) {
    fs.rmSync(dir, { recursive: true, force: true });
    console.log("Removed:", path.relative(PYTHON_DIR, dir));
  }
}

function rmGlob(baseDir, pattern) {
  const dir = path.join(PYTHON_DIR, baseDir);
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.match(pattern)) {
      fs.rmSync(path.join(dir, entry.name), { recursive: true, force: true });
      console.log("Removed:", path.relative(PYTHON_DIR, path.join(dir, entry.name)));
    }
  }
}

// Remove unnecessary stdlib
["Lib/test", "Lib/distutils", "Lib/ensurepip",
 "Lib/idlelib", "Lib/turtledemo", "Lib/venv", "Lib/tkinter", "Lib/lib2to3",
 "include", "libs", "tcl",
].forEach(d => rmDir(path.join(PYTHON_DIR, d)));

// Remove pip/setuptools/wheel (deps already installed)
[/^pip$/, /^pip-.*\.dist-info$/, /^setuptools$/, /^setuptools-.*\.dist-info$/,
 /^wheel$/, /^wheel-.*\.dist-info$/,
].forEach(p => rmGlob("Lib/site-packages", p));

// Recursive __pycache__ cleanup
function removePycache(dir) {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const full = path.join(dir, entry.name);
    if (entry.name === "__pycache__") {
      fs.rmSync(full, { recursive: true, force: true });
    } else {
      removePycache(full);
    }
  }
}
console.log("Cleaning __pycache__...");
removePycache(path.join(PYTHON_DIR, "Lib"));

// Remove .pyc files
function removePyc(dir) {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) removePyc(full);
    else if (entry.name.endsWith(".pyc")) fs.unlinkSync(full);
  }
}
console.log("Cleaning .pyc...");
removePyc(path.join(PYTHON_DIR, "Lib"));

// Remove CUDA libraries (CPU-only deployment)
const torchLib = path.join(PYTHON_DIR, "Lib", "site-packages", "torch", "lib");
if (fs.existsSync(torchLib)) {
  for (const f of fs.readdirSync(torchLib)) {
    if (/cuda|cudnn|nccl|^nv|cublas|cusparse|nvrtc|cufft|curand|cusolver/i.test(f)) {
      fs.unlinkSync(path.join(torchLib, f));
      console.log("Removed:", f);
    }
  }
}

// Measure final size
function getSize(dir) {
  let size = 0;
  if (!fs.existsSync(dir)) return 0;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) size += getSize(full);
    else try { size += fs.statSync(full).size; } catch {}
  }
  return size;
}
console.log("\nPython runtime size:", (getSize(PYTHON_DIR) / (1024 * 1024)).toFixed(1), "MB");
console.log("Cleanup complete.");
