"""Global configuration for the Audio Sample Manager."""
import os
import platform
import sys
from pathlib import Path

# --- Paths ---
APP_NAME = "SampleForge"

if getattr(sys, "frozen", False):
    # sys._MEIPASS is the read-only app bundle (_internal dir)
    APP_DIR = Path(sys._MEIPASS)
    # Writable data goes alongside the exe or to user's AppData
    DATA_DIR = Path(os.environ.get("SAMPLEFORGE_DATA_DIR", Path(sys.executable).parent / "data"))
else:
    APP_DIR = Path(__file__).parent
    DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "catalog.db"
CHROMA_DIR = DATA_DIR / "chroma"
CACHE_DIR = DATA_DIR / "cache"

for d in (DATA_DIR, CHROMA_DIR, CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- Hugging Face mirror for China ---
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# --- GLAP Model (multilingual, supports Chinese) ---
GLAP_MODEL_ID = "mispeech/GLAP"
EMBEDDING_DIM = 1024

# --- Audio ---
SUPPORTED_EXTENSIONS = {".wav", ".flac", ".aiff", ".aif", ".mp3", ".ogg", ".m4a", ".opus"}
ANALYSIS_SAMPLE_RATE = 16000  # GLAP requires 16kHz
MAX_WAVEFORM_SAMPLES = 4096   # resolution for waveform display (player)
WAVEFORM_PEAKS_COUNT = 200    # downsample points for table cell waveform
PLAYER_BLOCK_SIZE = 2048

# --- Scan ---
WORKER_THREADS = max(2, os.cpu_count() - 2)
BATCH_SIZE = 32               # files per analysis batch

# --- Search ---
TOP_K_SIMILAR = 50
TOP_K_TEXT = 30
SEMANTIC_MIN_SIMILARITY = 0.85  # cosine similarity threshold (0-1); results below this are filtered

# --- UMAP ---
UMAP_N_NEIGHBORS = 15
UMAP_MIN_DIST = 0.1
UMAP_METRIC = "cosine"

# --- Platform ---
IS_MACOS = platform.system() == "Darwin"
IS_APPLE_SILICON = IS_MACOS and platform.machine() == "arm64"

# Attempt MLX acceleration on Apple Silicon
USE_MLX = IS_APPLE_SILICON and os.environ.get("DISABLE_MLX", "0") == "0"

# --- UI ---
ACCENT_COLOR = "#999999"
ACCENT_HOVER = "#888888"
BG_COLOR = "#141414"
PANEL_COLOR = "#1e1e1e"
BORDER_COLOR = "#2a2a2a"
TEXT_PRIMARY = "#e8e8e8"
TEXT_SECONDARY = "#888888"
