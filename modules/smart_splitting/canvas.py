from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsSimpleTextItem

from gui_qt.theme import COLORS
from modules.nesting.render import painter_path, CANVAS_PALETTE


class SplitCanvas(QGraphicsView):
    def __init__(self):
        super().__init__(); self.setScene(QGraphicsScene(self)); self.theme='dark'; self.auto_fit=True
        self.setRenderHint(QPainter.Antialiasing); self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setMinimumSize(160,140)
        self.setAccessibleName('Parça konturları ve bölme önizlemesi')
        self.setToolTip('Tekerlek: yakınlaştır · Sürükle: kaydır · Sığdır: tüm konturlar')

    def show_geometry(self, source, solution=None, original=False):
        self.scene().clear(); self.setBackgroundBrush(QColor(COLORS[self.theme]['canvas']))
        if source is None: return
        pen=QPen(QColor(COLORS[self.theme]['muted'])); pen.setCosmetic(True)
        if original or solution is None:
            self.scene().addPath(painter_path(source.polygon),pen,QBrush(QColor(CANVAS_PALETTE[0])))
        else:
            for segment in solution.segments:
                color=QColor(CANVAS_PALETTE[(segment.number-1)%len(CANVAS_PALETTE)]); color.setAlpha(140)
                self.scene().addPath(painter_path(segment.blank),pen,QBrush(color))
                center=segment.blank.representative_point()
                label=QGraphicsSimpleTextItem(str(segment.number)); label.setBrush(QColor(COLORS[self.theme]['text']))
                label.setFlag(label.GraphicsItemFlag.ItemIgnoresTransformations)
                label.setPos(center.x,-center.y); self.scene().addItem(label)
            seam_pen=QPen(QColor(COLORS[self.theme]['accent'])); seam_pen.setCosmetic(True); seam_pen.setStyle(Qt.DashLine)
            for segment in solution.segments:
                for edge in segment.seam_edges:
                    lines=list(edge.geoms) if hasattr(edge,'geoms') else [edge]
                    for line in lines:
                        if line.geom_type not in ('LineString','LinearRing'): continue
                        coords=list(line.coords)
                        for a,b in zip(coords,coords[1:]): self.scene().addLine(a[0],-a[1],b[0],-b[1],seam_pen)
        self.scene().setSceneRect(self.scene().itemsBoundingRect()); self.fit()

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
