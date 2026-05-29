"""
Library panel: scan-folder list (left) + sample table (right).
Supports drag-and-drop to DAW, double-click to play, and right-click to delete.
"""
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import (
    QAbstractTableModel, QMimeData, QModelIndex, QSortFilterProxyModel,
    Qt, Signal, QUrl,
)
from PySide6.QtGui import QAction, QColor, QDrag
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView,
    QMenu, QSplitter, QTableView, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ui.widgets.waveform_delegate import WaveformDelegate

log = logging.getLogger(__name__)

COLUMNS = ["Name", "Format", "Duration", "BPM", "Key", "SR", "Loudness", "Category", "Tags", "Waveform"]
COL_IDX = {c: i for i, c in enumerate(COLUMNS)}

WaveformRole = Qt.UserRole + 2


class FolderTree(QTreeWidget):
    """QTreeWidget that emits a signal on right-click for context menu."""
    folder_context_requested = Signal(object)  # QTreeWidgetItem or None

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        self.folder_context_requested.emit(item)


class SampleTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[Dict] = []

    def load(self, rows: List[Dict]):
        self.beginResetModel()
        self._data = rows
        self.endResetModel()

    def append_rows(self, rows: List[Dict]):
        if not rows:
            return
        first = len(self._data)
        self.beginInsertRows(QModelIndex(), first, first + len(rows) - 1)
        self._data.extend(rows)
        self.endInsertRows()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._data[index.row()]
        col = COLUMNS[index.column()]

        if role == Qt.DisplayRole:
            return self._format_cell(row, col)
        if role == Qt.UserRole:
            return row.get("file_path", "")
        if role == WaveformRole:
            return row.get("waveform_peaks")
        if role == Qt.ForegroundRole:
            if row.get("analyzed_at") is None:
                return QColor("#555555")
        if role == Qt.ToolTipRole:
            return row.get("file_path", "")
        return None

    def get_row(self, index: int) -> Optional[Dict]:
        if 0 <= index < len(self._data):
            return self._data[index]
        return None

    def _format_cell(self, row: Dict, col: str) -> str:
        if col == "Name":
            return row.get("file_name", "")
        if col == "Format":
            return row.get("extension", "").lstrip(".").upper()
        if col == "Duration":
            dur = row.get("duration_sec")
            if dur:
                return f"{int(dur//60):02d}:{int(dur%60):02d}"
            return "—"
        if col == "BPM":
            v = row.get("bpm")
            return f"{v:.1f}" if v else "—"
        if col == "Key":
            return row.get("key_note") or "—"
        if col == "SR":
            v = row.get("sample_rate")
            return f"{v//1000}k" if v else "—"
        if col == "Loudness":
            v = row.get("loudness_lufs")
            return f"{v:.1f}" if v else "—"
        if col == "Category":
            return row.get("category") or "—"
        if col == "Tags":
            tags = row.get("tags") or []
            return ", ".join(tags[:3]) if tags else "—"
        return ""

    # --- Drag & Drop (file drag to DAW) ---
    def flags(self, index):
        base = super().flags(index)
        return base | Qt.ItemIsDragEnabled

    def mimeTypes(self):
        return ["text/uri-list"]

    def mimeData(self, indexes):
        paths = list({self._data[i.row()].get("file_path", "") for i in indexes if i.column() == 0})
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths if p])
        return mime


class LibraryView(QWidget):
    """Scan-folder tree + sample table with signals for selection and play."""

    sample_selected = Signal(dict)       # full metadata row
    sample_play_requested = Signal(str)  # file_path
    samples_delete_requested = Signal(list)  # list of file_paths
    folder_selected = Signal(str)       # folder path
    folder_remove_requested = Signal(str)  # folder path to remove

    FOLDER_ROLE = Qt.UserRole + 1  # stores the full folder path for added folders

    def __init__(self, parent=None):
        super().__init__(parent)
        self._added_folders: set[str] = set()
        self._subdir_provider: Callable[[str], list[str]] = lambda p: []
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        # ── Folder Tree ──────────────────────────────────────────────
        self.folder_tree = FolderTree()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setMinimumWidth(200)
        self.folder_tree.setMaximumWidth(320)
        self.folder_tree.setIndentation(16)
        self.folder_tree.setRootIsDecorated(True)
        self.folder_tree.setAnimated(True)
        self.folder_tree.itemClicked.connect(self._on_folder_item_clicked)
        self.folder_tree.itemExpanded.connect(self._on_item_expanded)
        self.folder_tree.folder_context_requested.connect(self._on_folder_context_menu)
        # "All Samples" root item
        self._all_item = QTreeWidgetItem(self.folder_tree, ["All Samples"])
        self._all_item.setData(0, self.FOLDER_ROLE, "")
        font = self._all_item.font(0)
        font.setBold(True)
        self._all_item.setFont(0, font)

        # ── Sample Table ─────────────────────────────────────────────
        self._model = SampleTableModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)

        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.horizontalHeader().setStretchLastSection(True)

        # Column widths
        widths = [200, 60, 60, 60, 50, 50, 70, 100, 150, 180]
        for i, w in enumerate(widths):
            self.table.setColumnWidth(i, w)

        # Waveform delegate (catalog wired later from MainWindow)
        self.waveform_delegate = WaveformDelegate()
        self.table.setItemDelegateForColumn(COL_IDX["Waveform"], self.waveform_delegate)

        # Drag from table
        self.table.setDragEnabled(True)
        self.table.setDragDropMode(QAbstractItemView.DragOnly)
        self.table.setDefaultDropAction(Qt.CopyAction)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._on_double_click)

        splitter.addWidget(self.folder_tree)
        splitter.addWidget(self.table)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

    # ------------------------------------------------------------------
    def load_samples(self, samples: List[Dict]):
        self._model.load(samples)

    def append_samples(self, samples: List[Dict]):
        self._model.append_rows(samples)

    def filter_text(self, text: str):
        self._proxy.setFilterRole(Qt.DisplayRole)
        self._proxy.setFilterFixedString(text)

    def selected_row(self) -> Optional[Dict]:
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            return None
        src = self._proxy.mapToSource(idxs[0])
        return self._model.get_row(src.row())

    def selected_paths(self) -> List[str]:
        """Return file_paths of all selected rows."""
        paths = []
        for idx in self.table.selectionModel().selectedRows():
            src = self._proxy.mapToSource(idx)
            row = self._model.get_row(src.row())
            if row:
                paths.append(row["file_path"])
        return paths

    # ------------------------------------------------------------------
    # Folder tree management
    # ------------------------------------------------------------------
    def _path_parts(self, path: str) -> list[str]:
        """Split a path into hierarchy parts, e.g. C:/Users/me/audio → ['C:', 'Users', 'me', 'audio']"""
        p = Path(path)
        parts = []
        # Drive or root
        if p.drive:
            parts.append(p.drive.rstrip(":"))
        elif p.anchor:
            parts.append(p.anchor.rstrip("/\\"))
        for part in p.parts[len(Path(p.anchor).parts):]:
            if part:
                parts.append(part)
        return parts

    def add_folder(self, folder_path: str):
        if folder_path in self._added_folders:
            return
        self._added_folders.add(folder_path)
        self._rebuild_folder_tree()

    def set_folders(self, paths: list[str]):
        self._added_folders = set(paths)
        self._rebuild_folder_tree()

    def folders(self) -> list[str]:
        return list(self._added_folders)

    def _rebuild_folder_tree(self):
        """Rebuild the tree from _added_folders, showing full path hierarchy
        including subdirectories from the catalog."""
        while self._all_item.childCount():
            self._all_item.removeChild(self._all_item.child(0))

        if not self._added_folders:
            self.folder_tree.expandAll()
            log.debug("Folder tree: no folders to show")
            return

        sorted_folders = sorted(self._added_folders, key=lambda p: p.lower())
        log.debug("Building folder tree for: %s", sorted_folders)

        for folder in sorted_folders:
            parts = self._path_parts(folder)
            if not parts:
                continue

            parent = self._all_item
            accumulated = ""
            for i, part in enumerate(parts):
                if i == 0:
                    accumulated = part + ":\\" if ":" not in part else part
                else:
                    accumulated = str(Path(accumulated) / part)

                child = None
                for j in range(parent.childCount()):
                    if parent.child(j).text(0) == part:
                        child = parent.child(j)
                        break
                if child is None:
                    child = QTreeWidgetItem(parent, [part])
                    child.setData(0, self.FOLDER_ROLE, accumulated)
                parent = child

            # Bold the added folder node
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)

            # Add placeholder child so expand arrow appears (lazy loading)
            self._add_placeholder(parent)

        self._all_item.setExpanded(True)  # show drives / top-level folders
        log.debug("Folder tree built with %d folders", len(self._added_folders))

    @staticmethod
    def _add_placeholder(parent_item: QTreeWidgetItem):
        """Add a dummy child so Qt shows the expand arrow."""
        if parent_item.childCount() == 0:
            dummy = QTreeWidgetItem(parent_item, ["..."])
            dummy.setData(0, Qt.UserRole + 1, "__placeholder__")

    def _on_item_expanded(self, item: QTreeWidgetItem):
        """Lazy-load subdirectories when user expands a node."""
        # Remove placeholder if present
        if item.childCount() == 1 and item.child(0).data(0, Qt.UserRole + 1) == "__placeholder__":
            item.removeChild(item.child(0))

            folder_path = item.data(0, self.FOLDER_ROLE) or ""
            if not folder_path:
                return

            subdirs = self._subdir_provider(folder_path)
            for sd in subdirs:
                name = Path(sd).name
                child = QTreeWidgetItem(item, [name])
                child.setData(0, self.FOLDER_ROLE, sd)
                # Add placeholder for next level
                self._add_placeholder(child)

    def _on_folder_item_clicked(self, item: QTreeWidgetItem, col: int):
        path = item.data(0, self.FOLDER_ROLE) or ""
        self.folder_selected.emit(path)

    def _on_folder_context_menu(self, item):
        if not item:
            return
        path = item.data(0, self.FOLDER_ROLE) or ""
        if not path:
            return
        # Normalize path separators for comparison (tree uses \, JSON may use /)
        path_norm = str(Path(path))
        if not any(Path(f) == Path(path_norm) for f in self._added_folders):
            return
        menu = QMenu(self)
        action = QAction("Remove Folder from Library", self)
        action.triggered.connect(lambda: self.folder_remove_requested.emit(path))
        menu.addAction(action)
        menu.exec(self.folder_tree.viewport().mapToGlobal(
            self.folder_tree.visualItemRect(item).center().toPoint()
        ))

    # ------------------------------------------------------------------
    def _on_context_menu(self, pos):
        paths = self.selected_paths()
        if not paths:
            return
        menu = QMenu(self)
        action = QAction(f"Remove from Catalog ({len(paths)} selected)", self)
        action.triggered.connect(lambda: self.samples_delete_requested.emit(paths))
        menu.addAction(action)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_selection_changed(self):
        row = self.selected_row()
        if row:
            self.sample_selected.emit(row)

    def _on_double_click(self, proxy_idx):
        src = self._proxy.mapToSource(proxy_idx)
        row = self._model.get_row(src.row())
        if row:
            self.sample_play_requested.emit(row["file_path"])
