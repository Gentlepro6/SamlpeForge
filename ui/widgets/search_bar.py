"""Search bar supporting both text-filter and semantic (GLAP) search."""
import logging
from typing import Callable

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget,
)

log = logging.getLogger(__name__)


class SearchBar(QWidget):
    """
    Emits two kinds of searches:
      - text_search(query)     → simple SQLite LIKE filter
      - semantic_search(query) → GLAP text-embedding query
    """

    text_search = Signal(str)
    semantic_search = Signal(str)
    filter_changed = Signal(str)   # for live table filtering

    def __init__(self, parent=None):
        super().__init__(parent)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._build_ui()

    def _build_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # Mode selector
        self.mode = QComboBox()
        self.mode.addItem("Filter", "filter")
        self.mode.addItem("Catalog Search", "text")
        self.mode.addItem("AI Semantic", "semantic")
        self.mode.setFixedWidth(130)
        self.mode.setToolTip("Search mode")

        # Scope selector
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("All", "all")
        self.scope_combo.addItem("Current Folder", "folder")
        self.scope_combo.addItem("Current Disk", "disk")
        self.scope_combo.setFixedWidth(120)
        self.scope_combo.setToolTip("Search scope")

        # Input
        self.input = QLineEdit()
        self.input.setPlaceholderText('Search… (e.g. "dark cinematic sub bass")')
        self.input.setClearButtonEnabled(True)

        # Search button
        self.btn = QPushButton("Search")
        self.btn.setObjectName("accent")
        self.btn.setFixedWidth(80)

        # Status indicator
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#555; font-size:11px;")
        self.lbl_status.setFixedWidth(160)

        lay.addWidget(QLabel("🔍"))
        lay.addWidget(self.mode)
        lay.addWidget(self.scope_combo)
        lay.addWidget(self.input, 1)
        lay.addWidget(self.btn)
        lay.addWidget(self.lbl_status)

        # Connect
        self.input.returnPressed.connect(self._on_search)
        self.btn.clicked.connect(self._on_search)
        self.input.textChanged.connect(self._on_text_changed)
        self.mode.currentIndexChanged.connect(self._update_placeholder)
        self._update_placeholder()

        # Debounce for filter mode
        self._debounce.timeout.connect(self._emit_filter)

    def _update_placeholder(self):
        mode = self.mode.currentData()
        placeholders = {
            "filter": 'Quick filter by filename or tag…',
            "text": 'Search catalog by name, category, tag…',
            "semantic": '"dark cinematic sub bass" · "punchy kick with low end"',
        }
        self.input.setPlaceholderText(placeholders.get(mode, "Search…"))

    def _on_text_changed(self, text: str):
        if self.mode.currentData() == "filter":
            self._debounce.start()

    def _emit_filter(self):
        self.filter_changed.emit(self.input.text())

    def _on_search(self):
        query = self.input.text().strip()
        if not query:
            return
        mode = self.mode.currentData()
        if mode == "filter":
            self.filter_changed.emit(query)
        elif mode == "text":
            self.text_search.emit(query)
        elif mode == "semantic":
            self.set_status("Searching…")
            self.semantic_search.emit(query)

    def scope(self) -> str:
        return self.scope_combo.currentData()

    def set_status(self, msg: str):
        self.lbl_status.setText(msg)

    def clear(self):
        self.input.clear()
        self.lbl_status.clear()
