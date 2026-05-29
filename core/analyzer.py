"""
Audio analysis pipeline:
  1. Load audio (librosa, resampled to 16 kHz for GLAP)
  2. Extract GLAP embedding (multilingual, supports Chinese)
  3. Extract DSP features via librosa (BPM, key, loudness, spectral centroid)
  4. Store embedding in ChromaDB, features in SQLite catalog
"""
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

import librosa
import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from config import (
    ANALYSIS_SAMPLE_RATE,
    BATCH_SIZE,
    GLAP_MODEL_ID,
    WAVEFORM_PEAKS_COUNT,
    WORKER_THREADS,
)
from core.catalog import Catalog
from core.vector_store import VectorStore

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy model loader — GLAP (multilingual, supports Chinese + 8 languages)
# ---------------------------------------------------------------------------
_glap_model = None


def _load_glap():
    global _glap_model
    if _glap_model is None:
        import torch
        from transformers import AutoModel

        log.info("Loading GLAP model %s …", GLAP_MODEL_ID)
        _glap_model = AutoModel.from_pretrained(
            GLAP_MODEL_ID, trust_remote_code=True, local_files_only=False,
        ).eval()

        if _try_mps():
            _glap_model = _glap_model.to("mps")
            log.info("GLAP running on Apple MPS")
        elif _try_cuda():
            _glap_model = _glap_model.to("cuda")
            log.info("GLAP running on CUDA")
        else:
            log.info("GLAP running on CPU")

    return _glap_model


def _try_mps() -> bool:
    try:
        import torch
        return torch.backends.mps.is_available()
    except Exception:
        return False


def _try_cuda() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Per-file analysis
# ---------------------------------------------------------------------------

def _make_embedding_id(file_path: str) -> str:
    return hashlib.sha1(file_path.encode()).hexdigest()


def extract_dsp_features(audio: np.ndarray, sr: int) -> Dict:
    """Extract BPM, key, loudness, and spectral centroid using librosa."""
    features: Dict = {}
    if len(audio) == 0:
        return {"bpm": None, "key_note": None, "loudness_lufs": None, "spectral_centroid": None}

    # BPM
    try:
        tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
        features["bpm"] = float(tempo)
    except Exception:
        features["bpm"] = None

    # Key (using chroma + Krumhansl-Schmuckler)
    try:
        chroma = librosa.feature.chroma_cqt(y=audio, sr=sr)
        key_idx = int(np.argmax(chroma.mean(axis=1)))
        notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        features["key_note"] = notes[key_idx % 12]
    except Exception:
        features["key_note"] = None

    # Integrated loudness (simple RMS → LUFS approximation)
    try:
        rms = librosa.feature.rms(y=audio)[0].mean()
        lufs = 20 * np.log10(rms + 1e-9) - 0.691
        features["loudness_lufs"] = float(lufs)
    except Exception:
        features["loudness_lufs"] = None

    # Spectral centroid
    try:
        centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0].mean()
        features["spectral_centroid"] = float(centroid)
    except Exception:
        features["spectral_centroid"] = None

    return features


MIN_DURATION_SEC = 0.5   # descartar samples menores a 0.5s


def analyse_file(file_path: str, model) -> Optional[Dict]:
    """Full analysis: load audio → DSP → GLAP embedding. Returns feature dict."""
    import torch

    try:
        audio, _ = librosa.load(file_path, sr=ANALYSIS_SAMPLE_RATE, mono=True, duration=30)
    except Exception as exc:
        log.warning("Cannot load %s: %s", file_path, exc)
        return None

    if len(audio) < int(MIN_DURATION_SEC * ANALYSIS_SAMPLE_RATE):
        log.debug("Skipping too-short file (%d samples): %s", len(audio), file_path)
        return None

    # Waveform peaks (200 points for table thumbnail)
    step = max(1, len(audio) // WAVEFORM_PEAKS_COUNT)
    peaks = np.array(
        [audio[i:i+step].max() for i in range(0, len(audio)-step, step)],
        dtype=np.float32,
    )

    # DSP features
    dsp = extract_dsp_features(audio, ANALYSIS_SAMPLE_RATE)

    # GLAP embedding
    try:
        device = next(model.parameters()).device
        audio_tensor = torch.from_numpy(audio).unsqueeze(0).to(device)
        with torch.no_grad():
            embedding = model.encode_audio(audio_tensor)
        embedding_np = embedding.squeeze().cpu().numpy().tolist()
    except Exception as exc:
        log.warning("GLAP embedding failed for %s: %s", file_path, exc)
        return None

    return {
        "embedding": embedding_np,
        "embedding_id": _make_embedding_id(file_path),
        "waveform_peaks": peaks,
        **dsp,
    }


def get_text_embedding(text: str) -> Optional[List[float]]:
    """Return a GLAP text embedding for multilingual semantic search."""
    import torch
    try:
        model = _load_glap()
        # GLAP expects prompted text: "The sound of {label} can be heard."
        with torch.no_grad():
            emb = model.encode_text([f"The sound of {text} can be heard."])
        return emb.squeeze().cpu().numpy().tolist()
    except Exception as exc:
        log.error("Text embedding failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

class AnalysisWorker(QObject):
    """Analyses pending (unanalysed) samples in the background."""

    progress = Signal(int, int)       # (done, total)
    sample_analysed = Signal(str)     # file_path
    finished = Signal(int)
    error = Signal(str)

    def __init__(self, catalog: Catalog, vector_store: VectorStore):
        super().__init__()
        self.catalog = catalog
        self.vector_store = vector_store
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            # Load model once
            model = _load_glap()

            all_samples = self.catalog.get_all()
            pending = [s for s in all_samples if s.get("analyzed_at") is None]
            total = len(pending)
            log.info("Analysing %d samples …", total)

            for idx, sample in enumerate(pending):
                if self._stop:
                    break

                fp = sample["file_path"]
                result = analyse_file(fp, model)
                if result:
                    embedding = result.pop("embedding")
                    emb_id = result["embedding_id"]

                    # Store in ChromaDB
                    self.vector_store.upsert(
                        embedding_id=emb_id,
                        embedding=embedding,
                        metadata={"file_path": fp},
                    )

                    # Update SQLite
                    self.catalog.update_analysis(fp, result)
                    self.sample_analysed.emit(fp)

                self.progress.emit(idx + 1, total)

            self.finished.emit(total)

        except Exception as exc:
            log.exception("Analysis worker error")
            self.error.emit(str(exc))


class SemanticSearchWorker(QObject):
    """Runs GLAP text embedding + vector search in background thread."""

    results_ready = Signal(list)    # list of {id, distance, file_path}
    error = Signal(str)

    def __init__(self, query: str, vector_store: VectorStore):
        super().__init__()
        self.query = query
        self.vector_store = vector_store
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            embedding = get_text_embedding(self.query)
            if self._stop:
                return
            if not embedding:
                self.error.emit("Failed to generate text embedding.")
                return
            similar = self.vector_store.find_by_text(embedding)
            if self._stop:
                return
            self.results_ready.emit(similar or [])
        except Exception as exc:
            log.exception("Semantic search error")
            self.error.emit(str(exc))
