"""Waveform display widget with click-to-seek and playhead."""
import numpy as np
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient, QMouseEvent
from PySide6.QtWidgets import QWidget


class WaveformView(QWidget):
    seek_requested = Signal(float)   # 0.0 – 1.0 relative position

    def __init__(self, parent=None):
        super().__init__(parent)
        self._peaks: np.ndarray = np.array([])
        self._position: float = 0.0   # 0.0 – 1.0
        self._duration: float = 0.0
        self.setMinimumHeight(100)
        self.setMaximumHeight(180)
        self.setCursor(Qt.PointingHandCursor)

    def set_peaks(self, peaks: np.ndarray):
        self._peaks = np.clip(peaks, -1.0, 1.0)
        self.update()

    def set_position(self, seconds: float):
        if self._duration > 0:
            self._position = seconds / self._duration
        else:
            self._position = 0.0
        self.update()

    def set_duration(self, duration: float):
        self._duration = duration

    def clear(self):
        self._peaks = np.array([])
        self._position = 0.0
        self._duration = 0.0
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()
        mid = h // 2

        # Background
        painter.fillRect(0, 0, w, h, QColor("#111111"))

        if len(self._peaks) == 0:
            painter.setPen(QColor("#333333"))
            painter.drawLine(0, mid, w, mid)
            painter.end()
            return

        # Waveform gradient fill
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor("#6e6e6e"))
        grad.setColorAt(0.5, QColor("#999999"))
        grad.setColorAt(1.0, QColor("#6e6e6e"))

        playhead_x = int(self._position * w)

        # Draw played (brighter) and unplayed (dimmer) separately
        n = len(self._peaks)
        bar_w = max(1, w // n)

        for i, peak in enumerate(self._peaks):
            x = int(i / n * w)
            bar_h = max(2, int(abs(peak) * mid * 0.95))
            is_played = x <= playhead_x

            if is_played:
                color = QColor("#999999")
            else:
                color = QColor("#505050")

            painter.fillRect(x, mid - bar_h, bar_w, bar_h * 2, color)

        # Centre line
        painter.setPen(QPen(QColor("#2a2a2a"), 1))
        painter.drawLine(0, mid, w, mid)

        # Playhead
        if self._duration > 0:
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawLine(playhead_x, 0, playhead_x, h)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            pos = event.position().x() / self.width()
            self.seek_requested.emit(max(0.0, min(1.0, pos)))

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton:
            pos = event.position().x() / self.width()
            self.seek_requested.emit(max(0.0, min(1.0, pos)))
