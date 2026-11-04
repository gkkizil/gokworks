"""2D DFM viewer: real drawing coordinates (mm, Y up), findings drawn on the geometry."""

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush, QFont, QPolygonF
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsEllipseItem

from gui_qt.theme import COLORS
from ..models import ERROR, WARNING


class DfmView(QGraphicsView):
    """Wheel zooms at the cursor, drag pans, double-click fits."""
    findingClicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setAccessibleName('DFM geometri önizlemesi')
        self.setToolTip('Tekerlek: yakınlaştır · Sürükle: kaydır · Çift tık: sığdır')
        self.appearance = 'dark'
        self.result = None
        self.selected = None
        self.show_findings = True
        self.marker_items = {}
        self.setBackgroundBrush(QColor(COLORS[self.appearance]['canvas']))

    # ---- drawing ---------------------------------------------------------------------
    def colours(self):
        c = COLORS[self.appearance]
        return dict(geometry=QColor(c['text']), raw=QColor(c['muted']), ERROR=QColor(c['danger']),
                    WARNING=QColor(c['warning']), INFO=QColor(c['muted']), selected=QColor(c['accent']))

    def set_appearance(self, appearance):
        self.appearance = appearance
        self.setBackgroundBrush(QColor(COLORS[appearance]['canvas']))
        self.redraw(fit=False)

    def set_result(self, result):
        self.result, self.selected = result, None
        self.redraw(fit=True)

    def set_show_findings(self, visible):
        self.show_findings = bool(visible)
        self.redraw(fit=False)

    @staticmethod
    def _point(p):
        return QPointF(p[0], -p[1])          # scene Y down, drawing Y up

    def _path(self, points, closed=False):
        path = QPainterPath()
        if points:
            path.moveTo(self._point(points[0]))
            for p in points[1:]:
                path.lineTo(self._point(p))
            if closed:
                path.closeSubpath()
        return path

    def redraw(self, fit=False):
        scene = self.scene()
        scene.clear(); self.marker_items = {}
        if self.result is None:
            return
        colours = self.colours()
        raw = QPen(colours['raw'], 0); raw.setCosmetic(True); raw.setStyle(Qt.DashLine)
        geometry = QPen(colours['geometry'], 1.2); geometry.setCosmetic(True)
        drawn = set()
        for part in self.result.parts:
            scene.addPath(self._path(part['outline'], True), geometry)
            for hole in part['holes']:
                scene.addPath(self._path(hole, True), geometry)
            drawn.add(tuple(map(tuple, part['outline'])))
        for contour in self.result.contours:              # everything read, incl. open pieces
            scene.addPath(self._path(contour['points']), raw)
        if self.show_findings:
            for index, finding in enumerate(self.result.findings):
                self.marker_items[index] = self._markers(finding, colours, index == self.selected)
        if fit:
            self.fit()

    def _markers(self, finding, colours, selected):
        scene = self.scene()
        colour = colours['selected'] if selected else colours.get(finding.severity, colours['INFO'])
        pen = QPen(colour, 3 if selected else 2); pen.setCosmetic(True)
        fill = QColor(colour); fill.setAlpha(70 if selected else 40)
        items = []
        for mark in finding.marks:
            points = [tuple(p) for p in mark.points]
            if mark.kind == 'area' and len(points) > 2:
                items.append(scene.addPolygon(QPolygonF([self._point(p) for p in points]), pen, QBrush(fill)))
            elif mark.kind in ('path', 'line') and len(points) > 1:
                items.append(scene.addPath(self._path(points), pen))
                for p in (points[0], points[-1]) if mark.kind == 'line' else ():
                    items.append(self._dot(p, colour, 5))
            elif points:
                items.append(self._dot(points[0], colour, 9 if selected else 7))
            if mark.label and points:
                text = QGraphicsSimpleTextItem(mark.label)
                text.setBrush(QBrush(colour)); font = QFont(); font.setPointSizeF(8.5); text.setFont(font)
                text.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations)
                xs = [p[0] for p in points]; ys = [p[1] for p in points]
                text.setPos(self._point(((min(xs) + max(xs)) / 2, max(ys))))
                scene.addItem(text); items.append(text)
        for item in items:
            item.setData(0, finding)
            item.setZValue(10 if selected else 5)
        return items

    def _dot(self, p, colour, size):
        dot = QGraphicsEllipseItem(-size / 2, -size / 2, size, size)
        dot.setPos(self._point(p)); dot.setBrush(QBrush(colour)); dot.setPen(QPen(Qt.NoPen))
        dot.setFlag(QGraphicsEllipseItem.ItemIgnoresTransformations)
        self.scene().addItem(dot)
        return dot

    # ---- navigation ------------------------------------------------------------------
    def fit(self, rect=None):
        rect = rect or self.scene().itemsBoundingRect()
        if rect.isEmpty():
            return
        margin = max(rect.width(), rect.height()) * .06 + 1
        self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.KeepAspectRatio)

    def select(self, index):
        """Highlight finding ``index`` and zoom to its geometry (None clears)."""
        self.selected = index
        self.redraw(fit=False)
        if index is None or self.result is None or not 0 <= index < len(self.result.findings):
            return
        bounds = self.result.findings[index].bounds()
        if bounds is None:
            return
        x0, y0, x1, y1 = bounds
        size = max(x1 - x0, y1 - y0, 4.0)
        cx, cy = (x0 + x1) / 2, -(y0 + y1) / 2
        self.fit(QRectF(cx - size * 1.6, cy - size * 1.6, size * 3.2, size * 3.2))

    def wheelEvent(self, event):
        factor = 1.2 ** (event.angleDelta().y() / 120)
        scale = self.transform().m11() * factor
        if 1e-4 < scale < 1e5:
            self.scale(factor, factor)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self.fit()
        event.accept()

    def mousePressEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item is not None and item.data(0) is not None and self.result is not None:
            finding = item.data(0)
            for index, f in enumerate(self.result.findings):
                if f is finding:
                    self.findingClicked.emit(index); break
        super().mousePressEvent(event)
