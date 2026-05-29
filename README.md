# SampleForge

**AI-Powered Audio Sample Manager** — Organize, analyze, and explore your entire sample library using deep audio embeddings and multilingual semantic search.

SampleForge uses the [GLAP](https://huggingface.co/mispeech/GLAP) model (Generalized Language-Audio Pretraining, from Xiaomi) to understand the *sound* of every file in your library — not just its filename. Find what you're looking for by describing it in plain text in **English, Chinese, or 8+ other languages**, or explore your collection visually on an interactive 2D map.

---

## Screenshots

![Library View](screenshots/library_view.png)

*Library view — browse samples with metadata columns (format, duration, BPM, key, loudness, sample rate), waveform thumbnail preview, and color-coded tags.*

![Constellation Map](screenshots/constellation_map.png)

*Constellation Map — every sample plotted in 2D space by sonic similarity. Hover for name, click to preview, drag to your project.*

---

## Features

- **Multilingual Semantic Search** — GLAP (`mispeech/GLAP`) supports Chinese, English, Japanese, Korean, French, German, Spanish, Russian, and more. Describe sounds naturally: "鼓声", "dark evolving pad", "punchy kick with room".
- **Deep Scan** — Analyzes audio files with GLAP (16kHz, 1024-dim embeddings). Runs in background with progress tracking.
- **Waveform Previews** — Every sample row shows a miniature waveform thumbnail for at-a-glance visual scanning. True relative volume — louder samples look louder.
- **Constellation Map** — Interactive 2D UMAP projection. Sonically similar samples cluster together. Click any dot to preview.
- **Rich Metadata** — Automatic extraction of BPM, musical key, loudness (LUFS), spectral centroid, format, bit depth, sample rate, channels, and duration.
- **Fast Filter** — Instant filtering by filename, folder, or tag across your entire library. Lazy-loaded folder tree handles deep directory structures efficiently.
- **Waveform Player** — Built-in audio player with real-time waveform display and click-to-seek. Keyboard shortcuts: **Space** for play/pause.
- **Export** — Export selected samples to WAV, preserving original sample rate and bit depth.
- **Vector Database** — ChromaDB-backed storage for fast cosine-similarity queries at scale.
- **Cross-platform** — macOS (Apple Silicon & Intel) and Windows.

---

## Supported Formats

`.wav` · `.flac` · `.aiff` · `.aif` · `.mp3` · `.ogg` · `.m4a` · `.opus`

---

## Installation

### macOS

```bash
git clone https://github.com/Marcosblancarg/SamlpeForge.git
cd SamlpeForge
pip install -r requirements.txt
python main.py
```

Or run the bundled app:

```bash
chmod +x install.sh
./install.sh
```

### Windows

Download the latest pre-built release from the [Actions tab](../../actions):

1. Go to **Actions** → latest **Build Windows EXE** run
2. Download the `SampleForge-Windows` artifact
3. Extract the `.zip`
4. Run `SampleForge.exe` inside the extracted folder

> **Note:** Windows Defender may show a warning on first run since the app is not code-signed. Click "More info" → "Run anyway".

---

## Requirements

| Dependency | Version |
|---|---|
| Python | 3.10 – 3.12 |
| PySide6 | ≥ 6.6.0 |
| PyTorch | ≥ 2.1.0 |
| transformers | ≥ 4.36.0 |
| glap_model | ≥ 0.0.13 |
| chromadb | ≥ 0.4.22 |
| librosa | ≥ 0.10.1 |
| umap-learn | ≥ 0.5.5 |
| soundfile | ≥ 0.12.1 |

Full list in [`requirements.txt`](requirements.txt).

---

## How It Works

```
Audio files
    │
    ▼
librosa / soundfile          ← load & resample to 16kHz
    │
    ▼
GLAP (mispeech/GLAP)         ← generate 1024-dim audio embedding (multilingual)
    │
    ▼
ChromaDB                     ← store & query by cosine similarity
    │
    ▼
UMAP                         ← reduce to 2D for Constellation Map
    │
    ▼
PySide6 UI                   ← display, filter, play, export, explore
```

### GLAP Model

GLAP is a 0.9B-parameter multilingual audio-text model by Xiaomi. It maps both audio and text into a shared 1024-dimensional embedding space. Unlike CLAP (English-only RoBERTa text encoder), GLAP's text encoder supports Chinese and 8+ other languages natively.

| Component | Detail |
|---|---|
| Model ID | `mispeech/GLAP` |
| Audio encoder | 12-layer Transformer, 768-dim, 16kHz input |
| Text encoder | 24-layer multilingual Transformer, 1024-dim |
| Shared space | 1024-dim projection |
| License | Apache 2.0 |

### Recommended Search Prompts

| Task | Prompt template |
|---|---|
| General sound | `The sound of {description} can be heard.` |
| Music / instrument | `The music in the style of {description}.` |
| Speech / vocal | `{description}` |

---

## Project Structure

```
SampleForge/
├── main.py                    # Entry point
├── config.py                  # Global settings
├── requirements.txt
├── core/
│   ├── analyzer.py            # GLAP embedding pipeline + DSP features
│   ├── catalog.py             # SQLite metadata store (with waveform peaks)
│   ├── player.py              # Audio playback engine
│   ├── scanner.py             # Folder scanner & batch processor
│   └── vector_store.py        # ChromaDB interface (GLAP embeddings)
├── ui/
│   ├── main_window.py         # Main application window
│   ├── styles/                # QSS dark theme (gray accent)
│   └── widgets/
│       ├── constellation.py   # 2D UMAP map widget
│       ├── library_view.py    # Sample table with lazy folder tree
│       ├── player_bar.py      # Playback controls + waveform view
│       ├── search_bar.py      # Search & semantic filter bar
│       ├── waveform_view.py   # Waveform renderer (player)
│       ├── waveform_delegate.py # Waveform thumbnails (table cells)
│       └── metadata_panel.py
└── utils/
    └── audio_utils.py
```

---

## Building from Source (Windows EXE)

The GitHub Actions workflow builds the Windows executable automatically on every push to `main`.

To build manually on Windows:

```bash
pip install pyinstaller
pip install -r requirements.txt
pyinstaller SampleForge_Windows.spec
# Output: dist/SampleForge/SampleForge.exe
```

---

## License

MIT — free to use, modify, and distribute.
