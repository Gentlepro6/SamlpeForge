"""
2D Constellation Map — UMAP projection of GLAP embeddings.
Each point is a sample; similar sounds cluster together.
Interactive: hover for name, click to select.
"""
import logging
from typing import Dict, List, Optional

import math

import numpy as np
from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QMimeData, QUrl
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QKeyEvent, QMouseEvent, QWheelEvent,
    QDrag, QImage,
)
from PySide6.QtWidgets import QWidget

_DRAG_THRESHOLD_SQ = 64   # 8 px de movimiento para iniciar drag

log = logging.getLogger(__name__)


# Category → color mapping
CATEGORY_COLORS = {
    "Kick":      "#ef4444",
    "Snare":     "#f97316",
    "Hi-Hat":    "#eab308",
    "Cymbal":    "#84cc16",
    "Bass":      "#06b6d4",
    "Lead":      "#6366f1",
    "Pad":       "#8b5cf6",
    "FX":        "#ec4899",
    "Vocal":     "#f43f5e",
    "Loop":      "#14b8a6",
    "Percussion":"#fb923c",
}
DEFAULT_COLOR = "#999999"


class ConstellationMap(QWidget):
    """Interactive 2D scatter plot of audio embeddings via UMAP."""

    sample_clicked = Signal(str)    # file_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points: List[Dict] = []   # [{x, y, label, category, file_path}]
        self._hovered: Optional[int] = None
        self._selected: Optional[int] = None

        # Pan/zoom state
        self._zoom = 1.0
        self._offset = QPointF(0, 0)
        self._drag_start: Optional[QPointF] = None
        self._drag_offset: Optional[QPointF] = None

        # Estado de press sobre un punto (para distinguir click de drag)
        self._press_pos: Optional[QPointF] = None
        self._press_point_idx: Optional[int] = None
        self._drag_initiated = False

        # Cache del hue map de fondo (se invalida al cargar nuevos puntos)
        self._hue_map: Optional[QImage] = None

        self.setMouseTracking(True)
        self.setMinimumSize(400, 300)
        self.setFocusPolicy(Qt.StrongFocus)   # necesario para recibir teclas
        self.setToolTip("Click: select · Flechas: navegar+play · Scroll: zoom · Drag: pan")

    # ------------------------------------------------------------------
    def load_points(self, points: List[Dict]):
        """
        Each point: {x: float, y: float, label: str, category: str, file_path: str}
        Coordinates should be pre-normalised to [0, 1].
        """
        self._points = points
        self._selected = None
        self._hovered = None
        self._hue_map = None   # invalidar cache
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor("#0d0d0d"))

        # Grid
        painter.setPen(QPen(QColor("#1e1e1e"), 1))
        for i in range(0, w, 50):
            painter.drawLine(i, 0, i, h)
        for i in range(0, h, 50):
            painter.drawLine(0, i, w, i)

        if not self._points:
            painter.setPen(QColor("#333"))
            painter.setFont(QFont("sans-serif", 14))
            painter.drawText(
                QRectF(0, 0, w, h), Qt.AlignCenter,
                "No embeddings yet.\nRun Deep Scan + Analysis to populate the map."
            )
            painter.end()
            return

        # Hue map de fondo (calculado una vez, se estira con pan/zoom)
        if self._hue_map is None:
            self._hue_map = self._build_hue_map()
        x0, y0 = self._world_to_screen(0.0, 0.0)
        x1, y1 = self._world_to_screen(1.0, 1.0)
        painter.drawImage(QRectF(x0, y0, x1 - x0, y1 - y0), self._hue_map)

        # Draw points
        for idx, pt in enumerate(self._points):
            sx, sy = self._world_to_screen(pt["x"], pt["y"])
            cat = pt.get("category") or ""
            color = QColor(CATEGORY_COLORS.get(cat, DEFAULT_COLOR))

            is_hov = idx == self._hovered
            is_sel = idx == self._selected

            r = 7 if is_sel else (5 if is_hov else 4)

            if is_sel:
                painter.setPen(QPen(QColor("#ffffff"), 2))
            elif is_hov:
                painter.setPen(QPen(color.lighter(150), 1))
            else:
                painter.setPen(Qt.NoPen)

            painter.setBrush(QBrush(color if not is_sel else color.lighter(140)))
            painter.drawEllipse(QPointF(sx, sy), r, r)

        # Hover label
        if self._hovered is not None:
            pt = self._points[self._hovered]
            sx, sy = self._world_to_screen(pt["x"], pt["y"])
            label = pt.get("label", "")
            if label:
                painter.setPen(QColor("#e8e8e8"))
                painter.setFont(QFont("sans-serif", 10))
                # Draw background rect for label
                fm = painter.fontMetrics()
                lw = fm.horizontalAdvance(label) + 8
                lh = fm.height() + 4
                lx = min(sx + 8, w - lw - 4)
                ly = max(sy - lh - 4, 4)
                painter.fillRect(int(lx), int(ly), lw, lh, QColor("#222222cc"))
                painter.drawText(int(lx + 4), int(ly + lh - 6), label)

        # Legend
        self._draw_legend(painter, w, h)
        painter.end()

    def _build_hue_map(self) -> QImage:
        """
        Hue map de fondo:
        - El HUE se determina por la POSICIÓN (x, y) en el espacio 2D,
          no por la categoría. Así siempre es colorido aunque no haya
          categorías asignadas.
        - El BRILLO (value) se modula por la densidad de puntos cercanos:
          negro donde no hay puntos, colores mate donde sí hay.
        """
        RES   = 150
        SIGMA = 0.12
        inv_2s2 = 1.0 / (2.0 * SIGMA ** 2)

        gv = np.linspace(0.0, 1.0, RES, dtype=np.float32)
        GX, GY = np.meshgrid(gv, gv)  # (RES, RES)

        # Densidad: suma de gaussianas centradas en cada punto
        density = np.zeros((RES, RES), dtype=np.float32)
        for pt in self._points:
            dx = GX - float(pt["x"])
            dy = GY - float(pt["y"])
            density += np.exp(-(dx * dx + dy * dy) * inv_2s2)

        d_max = density.max()
        if d_max > 0:
            density /= d_max

        # Hue basado en posición: X da el hue principal, Y lo desplaza levemente
        # → zonas distintas del mapa = colores distintos, siempre
        H = (GX * 0.75 + GY * 0.25) % 1.0
        S = np.full_like(H, 0.70)   # saturación matte
        V = density * 0.30          # oscuro; negro donde no hay puntos

        # HSV → RGB vectorizado
        H6 = H * 6.0
        i6 = np.floor(H6).astype(np.int32) % 6
        f  = H6 - np.floor(H6)
        p  = V * (1.0 - S)
        q  = V * (1.0 - f * S)
        t  = V * (1.0 - (1.0 - f) * S)

        R = np.select([i6==0, i6==1, i6==2, i6==3, i6==4], [V, q, p, p, t], default=V)
        G = np.select([i6==0, i6==1, i6==2, i6==3, i6==4], [t, V, V, q, p], default=p)
        B = np.select([i6==0, i6==1, i6==2, i6==3, i6==4], [p, p, t, V, V], default=q)

        rgb = np.stack([
            np.clip(R * 255, 0, 255).astype(np.uint8),
            np.clip(G * 255, 0, 255).astype(np.uint8),
            np.clip(B * 255, 0, 255).astype(np.uint8),
        ], axis=2)

        rgb_c = np.ascontiguousarray(rgb)
        img = QImage(rgb_c.data, RES, RES, RES * 3, QImage.Format_RGB888)
        return img.copy()

    def _draw_legend(self, painter: QPainter, w: int, h: int):
        painter.setFont(QFont("sans-serif", 9))
        x, y = 12, 12
        for cat, color in CATEGORY_COLORS.items():
            painter.setBrush(QColor(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(x, y, 8, 8)
            painter.setPen(QColor("#888"))
            painter.drawText(x + 12, y + 8, cat)
            y += 16
            if y > h - 20:
                break

    # ------------------------------------------------------------------
    def mouseMoveEvent(self, event: QMouseEvent):
        # Panning (arrastrar espacio vacío)
        if self._drag_start is not None:
            delta = event.position() - self._drag_start
            self._offset = self._drag_offset + delta
            self.update()
            return

        # Drag de un punto hacia el Drop Zone
        if (self._press_point_idx is not None
                and not self._drag_initiated
                and event.buttons() & Qt.LeftButton):
            diff = event.position() - self._press_pos
            if diff.x() ** 2 + diff.y() ** 2 > _DRAG_THRESHOLD_SQ:
                self._drag_initiated = True
                self._start_file_drag(self._press_point_idx)
                return

        # Detección de hover
        mx, my = event.position().x(), event.position().y()
        nearest = None
        nearest_dist = float("inf")
        for idx, pt in enumerate(self._points):
            sx, sy = self._world_to_screen(pt["x"], pt["y"])
            d = (sx - mx) ** 2 + (sy - my) ** 2
            if d < nearest_dist:
                nearest_dist = d
                nearest = idx

        new_hov = nearest if nearest_dist < 400 else None
        if new_hov != self._hovered:
            self._hovered = new_hov
            self.update()

    def mousePressEvent(self, event: QMouseEvent):
        self.setFocus()
        if event.button() == Qt.LeftButton:
            self._drag_initiated = False
            if self._hovered is not None:
                # Registrar press sobre un punto; el click/drag se resuelve en release/move
                self._press_pos = event.position()
                self._press_point_idx = self._hovered
            else:
                # Iniciar pan
                self._press_point_idx = None
                self._press_pos = None
                self._drag_start = event.position()
                self._drag_offset = QPointF(self._offset)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            # Si soltamos sobre el mismo punto sin arrastrar → click / selección
            if self._press_point_idx is not None and not self._drag_initiated:
                self._selected = self._press_point_idx
                self._emit_selected()
            self._drag_start = None
            self._press_pos = None
            self._press_point_idx = None
            self._drag_initiated = False

    def _start_file_drag(self, point_idx: int):
        pt = self._points[point_idx]
        fp = pt.get("file_path", "")
        if not fp:
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(fp)])
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom = max(0.1, min(20.0, self._zoom * factor))
        self.update()

    def keyPressEvent(self, event: QKeyEvent):
        """Flechas: moverse al punto más cercano en esa dirección y reproducirlo."""
        if not self._points:
            return

        key = event.key()
        if key not in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            super().keyPressEvent(event)
            return

        # Dirección como vector unitario (en coordenadas de mundo: Y crece hacia abajo)
        direction = {
            Qt.Key_Right: ( 1,  0),
            Qt.Key_Left:  (-1,  0),
            Qt.Key_Down:  ( 0,  1),
            Qt.Key_Up:    ( 0, -1),
        }[key]

        # Si no hay selección, elegir el punto más cercano al centro
        if self._selected is None:
            cx = sum(p["x"] for p in self._points) / len(self._points)
            cy = sum(p["y"] for p in self._points) / len(self._points)
            self._selected = min(
                range(len(self._points)),
                key=lambda i: (self._points[i]["x"] - cx) ** 2 + (self._points[i]["y"] - cy) ** 2,
            )
            self._emit_selected()
            return

        cur = self._points[self._selected]
        cx, cy = cur["x"], cur["y"]
        dx, dy = direction

        best_idx = None
        best_score = float("inf")

        for i, pt in enumerate(self._points):
            if i == self._selected:
                continue
            vx = pt["x"] - cx
            vy = pt["y"] - cy

            # Producto escalar con la dirección: sólo considerar puntos en ese semiplano
            dot = vx * dx + vy * dy
            if dot <= 0:
                continue

            # Distancia geométrica al punto
            dist = math.sqrt(vx ** 2 + vy ** 2)
            if dist == 0:
                continue

            # Ángulo entre el vector al punto y la dirección deseada (0 = alineado perfecto)
            cos_angle = dot / dist
            # Penalizar puntos que están muy "de lado" (fuera de un cono de ±60°)
            if cos_angle < 0.5:
                continue

            # Score: prioriza cercanía y alineación con la dirección
            score = dist / cos_angle
            if score < best_score:
                best_score = score
                best_idx = i

        if best_idx is not None:
            self._selected = best_idx
            self._center_on_selected()
            self._emit_selected()

    # ------------------------------------------------------------------
    def _emit_selected(self):
        """Emite la señal con el sample seleccionado y redibuja."""
        if self._selected is None:
            return
        fp = self._points[self._selected].get("file_path", "")
        if fp:
            self.sample_clicked.emit(fp)
        self.update()

    def _center_on_selected(self):
        """Desplaza el offset para que el punto seleccionado quede centrado en pantalla."""
        if self._selected is None:
            return
        pt = self._points[self._selected]
        w, h = self.width(), self.height()
        padding = 40
        uw = w - padding * 2
        uh = h - padding * 2
        # Posición en pantalla sin offset
        sx_no_off = padding + uw / 2 + (pt["x"] - 0.5) * uw * self._zoom
        sy_no_off = padding + uh / 2 + (pt["y"] - 0.5) * uh * self._zoom
        # Offset necesario para centrarlo
        self._offset = QPointF(w / 2 - sx_no_off, h / 2 - sy_no_off)

    # ------------------------------------------------------------------
    def _world_to_screen(self, wx: float, wy: float):
        """Map normalised [0,1] world coords to screen pixels."""
        w, h = self.width(), self.height()
        padding = 40
        uw = w - padding * 2
        uh = h - padding * 2
        cx = padding + uw / 2
        cy = padding + uh / 2
        sx = cx + (wx - 0.5) * uw * self._zoom + self._offset.x()
        sy = cy + (wy - 0.5) * uh * self._zoom + self._offset.y()
        return sx, sy


def build_umap_points(embeddings: List[List[float]], metadatas: List[Dict]) -> List[Dict]:
    """Project embeddings to 2D via UMAP and return point dicts."""
    from config import UMAP_MIN_DIST, UMAP_METRIC, UMAP_N_NEIGHBORS
    try:
        import umap
        arr = np.array(embeddings, dtype=np.float32)
        reducer = umap.UMAP(
            n_components=2,
            n_neighbors=min(UMAP_N_NEIGHBORS, len(arr) - 1),
            min_dist=UMAP_MIN_DIST,
            metric=UMAP_METRIC,
            random_state=42,
        )
        proj = reducer.fit_transform(arr)

        # Normalise to [0, 1]
        proj -= proj.min(axis=0)
        rng = proj.max(axis=0) - proj.min(axis=0)
        rng[rng == 0] = 1
        proj /= rng

        points = []
        for i, (x, y) in enumerate(proj):
            meta = metadatas[i] if i < len(metadatas) else {}
            fp = meta.get("file_path", "")
            points.append({
                "x": float(x),
                "y": float(y),
                "label": fp.split("/")[-1] if fp else f"sample_{i}",
                "category": meta.get("category", ""),
                "file_path": fp,
            })
        return points
    except Exception as exc:
        log.error("UMAP projection failed: %s", exc)
        return []
