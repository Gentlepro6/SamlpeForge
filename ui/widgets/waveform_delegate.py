"""Custom delegate that paints waveform thumbnails in sample table cells."""
import logging
from typing import Dict, Optional

import numpy as np
import soundfile as sf
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem, QStyledItemDelegate

from config import ACCENT_COLOR, BG_COLOR, WAVEFORM_PEAKS_COUNT

log = logging.getLogger(__name__)

WaveformRole = Qt.UserRole + 2


class WaveformDelegate(QStyledItemDelegate):
    """Paints a small waveform thumbnail from pre-computed or lazy-loaded peaks."""

    _cache: Dict[str, np.ndarray] = {}
    _pending: set[str] = set()

    def __init__(self, catalog=None, parent=None):
        super().__init__(parent)
        self._catalog = catalog

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        sz = super().sizeHint(option, index)
        sz.setHeight(44)
        return sz

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        # --- background & selection ---
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor("#252525"))
        else:
            painter.fillRect(option.rect, QColor(BG_COLOR))

        peaks = index.data(WaveformRole)
        file_path = index.data(Qt.UserRole) or ""

        # Try lazy-load if no peaks yet
        if peaks is None and file_path:
            peaks = self._lazy_load(file_path)

        rect = option.rect.adjusted(4, 4, -4, -4)
        if peaks is None or len(peaks) == 0:
            self._draw_placeholder(painter, rect)
            return

        self._draw_waveform(painter, rect, peaks)

    # ------------------------------------------------------------------
    def _draw_waveform(self, painter: QPainter, rect: QRectF, peaks: np.ndarray):
        """Draw filled envelope waveform."""
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)

        w, h = rect.width(), rect.height()
        mid_y = rect.top() + h / 2
        n = len(peaks)

        scale = (h / 2) * 0.85

        top = QPainterPath()
        top.moveTo(rect.left(), mid_y)
        for i in range(n):
            x = rect.left() + i * w / n
            y = mid_y - abs(float(peaks[i])) * scale
            top.lineTo(QPointF(x, y))
        top.lineTo(rect.right(), mid_y)

        bot = QPainterPath()
        bot.moveTo(rect.right(), mid_y)
        for i in range(n - 1, -1, -1):
            x = rect.left() + i * w / n
            y = mid_y + abs(float(peaks[i])) * scale
            bot.lineTo(QPointF(x, y))
        bot.lineTo(rect.left(), mid_y)

        full = top + bot

        painter.setBrush(QColor(ACCENT_COLOR))
        painter.setPen(Qt.NoPen)
        painter.drawPath(full)

        painter.restore()

    def _draw_placeholder(self, painter: QPainter, rect: QRectF):
        """Flat center line for missing waveform data."""
        painter.save()
        mid_y = rect.center().y()
        pen = painter.pen()
        pen.setColor(QColor("#3a3a3a"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(int(rect.left()), int(mid_y), int(rect.right()), int(mid_y))
        painter.restore()

    # ------------------------------------------------------------------
    def _lazy_load(self, file_path: str) -> Optional[np.ndarray]:
        """Load waveform for unanalysed samples on first display."""
        if file_path in self._pending:
            return None
        if file_path in self._cache:
            return self._cache[file_path]

        # Try DB first
        if self._catalog:
            db_wf = self._catalog.get_waveform(file_path)
            if db_wf is not None:
                self._cache[file_path] = db_wf
                return db_wf

        self._pending.add(file_path)
        try:
            data, sr = sf.read(file_path, dtype="float32", always_2d=False, stop=30 * 48000)
            if data.ndim > 1:
                data = data.mean(axis=1)
            step = max(1, len(data) // WAVEFORM_PEAKS_COUNT)
            peaks = np.array(
                [data[i:i+step].max() for i in range(0, len(data)-step, step)],
                dtype=np.float32,
            )
            self._cache[file_path] = peaks
            if self._catalog:
                try:
                    self._catalog.store_waveform(file_path, peaks)
                except Exception:
                    pass
            return peaks
        except Exception:
            return None
        finally:
            self._pending.discard(file_path)
