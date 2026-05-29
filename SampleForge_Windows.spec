# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec para SampleForge — Windows

import sys
from pathlib import Path

APP_DIR = Path(SPECPATH)

block_cipher = None

added_datas = [
    (str(APP_DIR / "ui" / "styles"), "ui/styles"),
    (str(APP_DIR / "config.py"), "."),
]

hidden_imports = [
    # transformers + GLAP (mispeech/GLAP, trust_remote_code)
    "transformers",
    "transformers.pipelines",
    "huggingface_hub",
    "huggingface_hub.file_download",
    "safetensors",
    "safetensors.torch",
    # GLAP dependencies
    "glap_model",
    "dasheng",
    "sentencepiece",
    "einops",
    "torchaudio",
    "loguru",
    "pytorch_ignite",
    # torch
    "torch",
    "torch.nn",
    "torch.nn.functional",
    # audio
    "librosa",
    "soundfile",
    "sounddevice",
    "mutagen",
    "mutagen.mp3",
    "mutagen.flac",
    "mutagen.mp4",
    "audioread",
    # vector db — chromadb tiene muchos submódulos dinámicos
    "chromadb",
    "chromadb.db.impl",
    "chromadb.segment",
    "chromadb.segment.impl",
    "chromadb.api",
    "chromadb.api.client",
    "chromadb.api.shared_system_client",
    "chromadb.config",
    "chromadb.telemetry",
    "chromadb.telemetry.product",
    "chromadb.telemetry.product.posthog",
    "chromadb.migrations",
    "chromadb.db",
    "chromadb.db.mixins",
    "chromadb.db.mixins.embeddings_queue",
    "chromadb.execution",
    "chromadb.execution.executor",
    "chromadb.execution.executor.local",
    "posthog",
    "hnswlib",
    # umap
    "umap",
    "umap.umap_",
    "sklearn",
    "sklearn.neighbors",
    "sklearn.utils",
    "pynndescent",
    # UI
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    # misc
    "numpy",
    "scipy",
    "sqlalchemy",
    "sqlalchemy.dialects.sqlite",
]

a = Analysis(
    [str(APP_DIR / "main.py")],
    pathex=[str(APP_DIR)],
    binaries=[],
    datas=added_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
        "mlx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SampleForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,   # sin ventana de terminal (GUI app)
    disable_windowed_traceback=False,
    icon=None,       # reemplaza con "assets/icon.ico" si tienes icono
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SampleForge",
)
