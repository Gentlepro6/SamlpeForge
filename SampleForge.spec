# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'PySide6.QtMultimedia', 'PySide6.QtNetwork', 'torch', 'transformers', 'glap_model', 'sqlalchemy', 'sqlalchemy.dialects.sqlite', 'soundfile', 'sounddevice', 'librosa', 'scipy', 'scipy.signal', 'scipy.fft', 'numpy', 'numpy.core', 'mutagen', 'umap', 'pyqtgraph', 'matplotlib', 'tqdm', 'httpx', 'urllib3', 'onnxruntime', 'tokenizers']
hiddenimports += collect_submodules('chromadb.telemetry')
hiddenimports += collect_submodules('chromadb.api')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/icon.ico', 'assets'), ('assets/icon.png', 'assets'), ('ui/styles/dark_theme.qss', 'ui/styles')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'test', 'IPython', 'jupyter', 'notebook'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SampleForge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SampleForge',
)
