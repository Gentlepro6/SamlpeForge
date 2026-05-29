"""SQLite catalog — stores every scanned sample's metadata and analysis results."""
import json
import logging
import sqlite3
import time

import numpy as np
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import DB_PATH

log = logging.getLogger(__name__)


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS samples (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path       TEXT    UNIQUE NOT NULL,
    file_name       TEXT    NOT NULL,
    extension       TEXT    NOT NULL,
    size_bytes      INTEGER,
    sample_rate     INTEGER,
    bit_depth       INTEGER,
    channels        INTEGER,
    duration_sec    REAL,
    -- AI / DSP features
    bpm             REAL,
    key_note        TEXT,
    loudness_lufs   REAL,
    spectral_centroid REAL,
    embedding_id    TEXT,          -- matches ChromaDB id
    -- Catalogue
    category        TEXT,
    tags            TEXT,          -- JSON array
    favorite        INTEGER DEFAULT 0,
    color_label     TEXT,
    -- Timestamps
    scanned_at      REAL,
    analyzed_at     REAL,
    waveform_peaks  BLOB
);

CREATE INDEX IF NOT EXISTS idx_extension  ON samples(extension);
CREATE INDEX IF NOT EXISTS idx_category   ON samples(category);
CREATE INDEX IF NOT EXISTS idx_favorite   ON samples(favorite);
CREATE INDEX IF NOT EXISTS idx_bpm        ON samples(bpm);
CREATE INDEX IF NOT EXISTS idx_key        ON samples(key_note);
"""


class Catalog:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(CREATE_SQL)
        # Migration: add waveform_peaks column to existing DBs
        try:
            with self._conn() as conn:
                conn.execute("ALTER TABLE samples ADD COLUMN waveform_peaks BLOB")
        except sqlite3.OperationalError:
            pass  # column already exists
        log.info("Catalog ready at %s", self.db_path)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def upsert_sample(self, data: Dict[str, Any]) -> int:
        """Insert or replace a sample record. Returns row id."""
        data.setdefault("scanned_at", time.time())
        if "tags" in data and isinstance(data["tags"], list):
            data["tags"] = json.dumps(data["tags"])
        cols = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        sql = f"""
            INSERT INTO samples ({cols})
            VALUES ({placeholders})
            ON CONFLICT(file_path) DO UPDATE SET
            {', '.join(f"{k}=excluded.{k}" for k in data.keys() if k != 'file_path')}
        """
        with self._conn() as conn:
            cur = conn.execute(sql, data)
            return cur.lastrowid

    def update_analysis(self, file_path: str, analysis: Dict[str, Any]):
        analysis["analyzed_at"] = time.time()
        analysis["file_path"] = file_path
        if "waveform_peaks" in analysis and isinstance(analysis["waveform_peaks"], np.ndarray):
            analysis["waveform_peaks"] = sqlite3.Binary(
                analysis["waveform_peaks"].astype(np.float32).tobytes()
            )
        cols = ", ".join(f"{k}=:{k}" for k in analysis if k != "file_path")
        sql = f"UPDATE samples SET {cols} WHERE file_path=:file_path"
        with self._conn() as conn:
            conn.execute(sql, analysis)

    def set_favorite(self, file_path: str, state: bool):
        with self._conn() as conn:
            conn.execute("UPDATE samples SET favorite=? WHERE file_path=?", (int(state), file_path))

    def set_tags(self, file_path: str, tags: List[str]):
        with self._conn() as conn:
            conn.execute("UPDATE samples SET tags=? WHERE file_path=?", (json.dumps(tags), file_path))

    def set_category(self, file_path: str, category: str):
        with self._conn() as conn:
            conn.execute("UPDATE samples SET category=? WHERE file_path=?", (category, file_path))

    def delete_by_path(self, file_path: str):
        with self._conn() as conn:
            conn.execute("DELETE FROM samples WHERE file_path=?", (file_path,))

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def get_all(self, filters: Optional[Dict] = None) -> List[Dict]:
        sql = "SELECT * FROM samples"
        params: list = []
        if filters:
            clauses = []
            for k, v in filters.items():
                clauses.append(f"{k}=?")
                params.append(v)
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY file_name COLLATE NOCASE"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_by_path(self, file_path: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM samples WHERE file_path=?", (file_path,)).fetchone()
        return self._row_to_dict(row) if row else None

    # ------------------------------------------------------------------
    # Waveform
    # ------------------------------------------------------------------
    def store_waveform(self, file_path: str, peaks: np.ndarray):
        data = sqlite3.Binary(peaks.astype(np.float32).tobytes())
        with self._conn() as conn:
            conn.execute("UPDATE samples SET waveform_peaks=? WHERE file_path=?", (data, file_path))

    def get_waveform(self, file_path: str) -> Optional[np.ndarray]:
        with self._conn() as conn:
            row = conn.execute("SELECT waveform_peaks FROM samples WHERE file_path=?", (file_path,)).fetchone()
        if row and row[0]:
            return np.frombuffer(row[0], dtype=np.float32)
        return None

    def search(self, query: str) -> List[Dict]:
        q = f"%{query}%"
        sql = """SELECT * FROM samples
                 WHERE file_name LIKE ? OR category LIKE ? OR tags LIKE ?
                 ORDER BY file_name COLLATE NOCASE"""
        with self._conn() as conn:
            rows = conn.execute(sql, (q, q, q)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_by_folder_prefix(self, folder_path: str) -> List[Dict]:
        """Return all samples whose file_path starts with folder_path (recursive).
        Normalizes / to \\ to handle mixed separators from QFileDialog."""
        import os
        prefix = os.path.normpath(folder_path) + os.sep
        escaped = self._escape_like(prefix)
        bs = chr(92)  # single backslash — parameterised to avoid SQL string-escape confusion

        sql = ("SELECT * FROM samples WHERE REPLACE(file_path, '/', ?) "
               "LIKE ? ESCAPE '!' ORDER BY file_name COLLATE NOCASE")
        with self._conn() as conn:
            rows = conn.execute(sql, (bs, escaped + "%")).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_immediate_subdirs(self, folder_path: str) -> List[str]:
        """Return sorted list of immediate child directory paths under folder_path."""
        import os
        prefix = os.path.normpath(folder_path)
        bs = chr(92)
        escaped = self._escape_like(prefix + os.sep)

        sql = ("SELECT DISTINCT file_path FROM samples "
               "WHERE REPLACE(file_path, '/', ?) LIKE ? ESCAPE '!'")
        with self._conn() as conn:
            rows = conn.execute(sql, (bs, escaped + "%")).fetchall()

        subdirs: set[str] = set()
        plen = len(prefix) + 1  # +1 for the separator
        for (fp,) in rows:
            fp_norm = fp.replace("/", "\\")
            if len(fp_norm) <= plen:
                continue
            rest = fp_norm[plen:]
            first_part = rest.split("\\", 1)[0]
            if first_part:
                subdirs.add(os.path.join(prefix, first_part))
        return sorted(subdirs, key=lambda p: p.lower())

    @staticmethod
    def _escape_like(s: str) -> str:
        """Escape LIKE special characters using ! as escape char."""
        return s.replace("!", "!!").replace("%", "!%").replace("_", "!_")

    def get_by_ids(self, ids: List[str]) -> List[Dict]:
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        sql = f"SELECT * FROM samples WHERE embedding_id IN ({placeholders})"
        with self._conn() as conn:
            rows = conn.execute(sql, ids).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_by_paths(self, paths: List[str]) -> List[Dict]:
        """Batch lookup by file_path instead of loading all records."""
        if not paths:
            return []
        placeholders = ",".join("?" * len(paths))
        sql = f"SELECT * FROM samples WHERE file_path IN ({placeholders})"
        with self._conn() as conn:
            rows = conn.execute(sql, paths).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]

    def count_analyzed(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM samples WHERE analyzed_at IS NOT NULL").fetchone()[0]

    def purge_paths_containing(self, substring: str) -> int:
        """Elimina del catálogo todos los archivos cuya ruta contiene substring."""
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM samples WHERE file_path LIKE ?",
                (f"%{substring}%",)
            )
            return cur.rowcount

    def exists(self, file_path: str) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT 1 FROM samples WHERE file_path=?", (file_path,)).fetchone()
        return row is not None

    # ------------------------------------------------------------------
    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        d = dict(row)
        if d.get("tags") and isinstance(d["tags"], str):
            try:
                d["tags"] = json.loads(d["tags"])
            except json.JSONDecodeError:
                d["tags"] = []
        if d.get("waveform_peaks") and isinstance(d["waveform_peaks"], bytes):
            d["waveform_peaks"] = np.frombuffer(d["waveform_peaks"], dtype=np.float32)
        return d
