"""ChromaDB wrapper for storing and querying GLAP audio embeddings locally."""
import logging
from pathlib import Path
from typing import Dict, List, Optional

from config import CHROMA_DIR, EMBEDDING_DIM, TOP_K_SIMILAR, TOP_K_TEXT

log = logging.getLogger(__name__)


class VectorStore:
    """Persistent vector store backed by ChromaDB."""

    COLLECTION = "audio_samples"

    def __init__(self, persist_dir: Path = CHROMA_DIR):
        import chromadb
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._col = self._client.get_or_create_collection(
            name=self.COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        log.info("VectorStore ready (%d vectors)", self._col.count())

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def upsert(self, embedding_id: str, embedding: List[float], metadata: Dict):
        self._col.upsert(
            ids=[embedding_id],
            embeddings=[embedding],
            metadatas=[metadata],
        )

    def upsert_batch(self, ids: List[str], embeddings: List[List[float]], metadatas: List[Dict]):
        if not ids:
            return
        self._col.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def delete(self, embedding_id: str):
        self._col.delete(ids=[embedding_id])

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def find_similar(self, embedding: List[float], n: int = TOP_K_SIMILAR) -> List[Dict]:
        """Cosine-similarity nearest neighbours. Returns list of {id, distance, metadata}."""
        if self._col.count() == 0:
            return []
        results = self._col.query(
            query_embeddings=[embedding],
            n_results=min(n, self._col.count()),
            include=["metadatas", "distances"],
        )
        out = []
        for eid, dist, meta in zip(
            results["ids"][0],
            results["distances"][0],
            results["metadatas"][0],
        ):
            out.append({"id": eid, "distance": dist, "file_path": meta.get("file_path", "")})
        return out

    def find_by_text(self, text_embedding: List[float], n: int = TOP_K_TEXT) -> List[Dict]:
        return self.find_similar(text_embedding, n=n)

    def find_similar_by_id(self, embedding_id: str, n: int = TOP_K_SIMILAR) -> List[Dict]:
        """Audio-to-audio similarity: find samples like the one with the given ID."""
        result = self._col.get(ids=[embedding_id], include=["embeddings"])
        if not result["ids"]:
            return []
        emb = result["embeddings"][0]
        # Request n+1 — the closest result is the sample itself
        results = self.find_similar(emb, n=n + 1)
        return [r for r in results if r["id"] != embedding_id][:n]

    def count(self) -> int:
        return self._col.count()

    def get_all_embeddings(self) -> Dict:
        """Return all stored embeddings (for UMAP projection)."""
        if self._col.count() == 0:
            return {"ids": [], "embeddings": [], "metadatas": []}
        result = self._col.get(include=["embeddings", "metadatas"])
        return result
