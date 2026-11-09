from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsSimpleTextItem

from gui_qt.theme import COLORS
from modules.nesting.render import painter_path, CANVAS_PALETTE


class SplitCanvas(QGraphicsView):
    """Source contour, split preview, split centre and forbidden zones (normalized source mm)."""

    EMPTY = ('Bölünecek parçayı seçin\n\n“DXF/DWG ekle…” ile bir veya birden çok dosya açın veya Nesting’de tek parça seçip '
             '“Nesting’den al” düğmesini kullanın.')

    def __init__(self):
        super().__init__(); self.setScene(QGraphicsScene(self)); self.theme='dark'; self.auto_fit=True
        self.setRenderHint(QPainter.Antialiasing); self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setMinimumSize(160,140); self.empty=True
        self.setAccessibleName('Parça konturları ve bölme önizlemesi')
        self.setToolTip('Tekerlek: yakınlaştır · Sürükle: kaydır · Sığdır: tüm konturlar')

    def colours(self):
        return COLORS[self.theme]

    def label(self, text, x, y, colour, bold=False):
        item = QGraphicsSimpleTextItem(text); item.setBrush(QColor(colour))
        if bold:
            font = QFont(item.font()); font.setBold(True); font.setPointSizeF(font.pointSizeF()*1.2); item.setFont(font)
        item.setFlag(item.GraphicsItemFlag.ItemIgnoresTransformations)
        item.setPos(x, -y); self.scene().addItem(item)
        return item

    def show_geometry(self, source, solution=None, original=False, center=None, forbidden=()):
        c = self.colours(); scene = self.scene(); scene.clear()
        self.setBackgroundBrush(QColor(c['canvas'])); self.empty = source is None
        if source is None:
            scene.setSceneRect(QRectF()); self.viewport().update(); return
        pen = QPen(QColor(c['text'])); pen.setCosmetic(True); pen.setWidthF(1.2)
        if original or solution is None:
            fill = QColor(CANVAS_PALETTE[0]); fill.setAlpha(150)
            scene.addPath(painter_path(source.polygon), pen, QBrush(fill))
        else:
            for segment in solution.segments:
                colour = QColor(CANVAS_PALETTE[(segment.number-1) % len(CANVAS_PALETTE)]); colour.setAlpha(150)
                scene.addPath(painter_path(segment.blank), pen, QBrush(colour))
            seam_pen = QPen(QColor(c['accent'])); seam_pen.setCosmetic(True); seam_pen.setWidthF(2); seam_pen.setStyle(Qt.DashLine)
            for segment in solution.segments:
                for edge in segment.seam_edges:
                    for line in (list(edge.geoms) if hasattr(edge, 'geoms') else [edge]):
                        if line.geom_type not in ('LineString', 'LinearRing'): continue
                        coords = list(line.coords)
                        for a, b in zip(coords, coords[1:]): scene.addLine(a[0], -a[1], b[0], -b[1], seam_pen)
            for segment in solution.segments:
                point = segment.nominal.representative_point()
                self.label(str(segment.number), point.x, point.y, c['text'], bold=True)
        danger = QColor(c['danger']); hatch = QColor(danger); hatch.setAlpha(90)
        zone_pen = QPen(danger); zone_pen.setCosmetic(True); zone_pen.setWidthF(1.5)
        for polygon in forbidden:
            scene.addPath(painter_path(polygon), zone_pen, QBrush(hatch, Qt.BDiagPattern))
        if center is not None:
            x0, y0, x1, y1 = source.polygon.bounds; size = max(x1-x0, y1-y0) * .03; x, y = center
            mark = QPen(QColor(c['warning'])); mark.setCosmetic(True); mark.setWidthF(2)
            scene.addLine(x-size, -y, x+size, -y, mark); scene.addLine(x, -y-size, x, -y+size, mark)
            scene.addEllipse(x-size*.45, -y-size*.45, size*.9, size*.9, mark)
        scene.setSceneRect(scene.itemsBoundingRect()); self.fit()

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        if not self.empty:
            return
        painter.save(); painter.resetTransform()
        painter.setPen(QColor(self.colours()['muted']))
        painter.drawText(self.viewport().rect().adjusted(32, 24, -32, -24), Qt.AlignCenter | Qt.TextWordWrap, self.EMPTY)
        painter.restore()

    def fit(self):
        self.auto_fit=True
        if not self.sceneRect().isEmpty(): self.fitInView(self.sceneRect().adjusted(-10,-10,10,10),Qt.KeepAspectRatio)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.auto_fit: self.fit()

    def wheelEvent(self,event):
        self.auto_fit=False; factor=1.15 if event.angleDelta().y()>0 else 1/1.15
        if .00001<abs(self.transform().m11())*factor<1000: self.scale(factor,factor)
        event.accept()
