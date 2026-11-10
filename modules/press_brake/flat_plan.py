"""2D flat pattern of the plan: numbered, coloured bend lines in bending order; click selects a step."""
from math import hypot
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget
from gui_qt.theme import COLORS

# Step colours (cycled); each line also carries its step number, so colour is never the only signal.
STEP_COLOURS = ('#E8833A', '#3FA7D6', '#9B6BDF', '#4CB782', '#E25A7B', '#C9A227', '#4A7BE0', '#8C9A3D')
HIT_RADIUS = 10   # px around a bend line that selects its step


def step_colour(number):
    return QColor(STEP_COLOURS[(number-1) % len(STEP_COLOURS)])


class FlatPlan(QWidget):
    stepClicked = Signal(int)

    def __init__(self, appearance):
        super().__init__(); self.appearance = appearance; self.plan = None; self.current = -1
        self.setMinimumHeight(120); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed); self.setFixedHeight(150)
        self.setMouseTracking(True); self.setCursor(Qt.ArrowCursor)
        self.setAccessibleName('Açınım planı: büküm çizgileri sıra numarasıyla')
        self.setToolTip('Açınım: büküm çizgileri büküm sırasıyla numaralı ve renkli. Bir çizgiye tıklayınca o adım seçilir.')

    def set_plan(self, plan, current=-1):
        self.plan, self.current = plan, current; self.update()

    def set_current(self, index):
        if index != self.current:
            self.current = index; self.update()

    def lines(self):
        """(step index, bend, (a, b)) with the line along the middle of the bend zone, flat mm."""
        if not self.plan:
            return []
        bends = {b.id: b for b in self.plan.part.bends}; result = []
        for i, step in enumerate(self.plan.steps):
            bend = bends[step.bend]
            (x0, y0), (x1, y1) = bend.start, bend.end
            length = hypot(x1-x0, y1-y0) or 1
            nx, ny = -(y1-y0)/length*bend.width/2, (x1-x0)/length*bend.width/2   # left normal points to the child
            result.append((i, bend, ((x0+nx, y0+ny), (x1+nx, y1+ny))))
        return result

    def mapping(self):
        part = self.plan.part
        points = [p for f in part.flanges for p in f.region.outer] + [p for b in part.bends for p in b.region.outer]
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        margin = 18
        scale = min((self.width()-2*margin)/max(1e-9, max(xs)-min(xs)), (self.height()-2*margin)/max(1e-9, max(ys)-min(ys)))
        ox = (self.width()-(max(xs)-min(xs))*scale)/2; oy = (self.height()-(max(ys)-min(ys))*scale)/2
        return lambda p: QPointF(ox+(p[0]-min(xs))*scale, self.height()-oy-(p[1]-min(ys))*scale)

    def paintEvent(self, event):
        c = COLORS[self.appearance]
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(c['border']), 1)); painter.setBrush(QColor(c['canvas']))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 6, 6)
        if not self.plan:
            painter.setPen(QColor(c['muted'])); painter.drawText(self.rect(), Qt.AlignCenter, 'Açınım: parça yüklenince görünür')
            return
        to = self.mapping()
        def path(region):
            shape = QPainterPath()
            for ring in (region.outer, *region.holes):
                shape.moveTo(to(ring[0]))
                for p in ring[1:]:
                    shape.lineTo(to(p))
                shape.closeSubpath()
            return shape
        painter.setPen(QPen(QColor(c['text']), 1.1)); painter.setBrush(QColor(c['panel']))
        for region in [f.region for f in self.plan.part.flanges]+[b.region for b in self.plan.part.bends]:
            painter.drawPath(path(region))
        font = QFont(self.font()); font.setPixelSize(10); font.setBold(True); painter.setFont(font)
        for i, bend, (a, b) in self.lines():
            colour = step_colour(i+1); selected = i == self.current
            painter.setPen(Qt.NoPen); zone = QColor(colour); zone.setAlpha(70 if selected else 40); painter.setBrush(zone)
            painter.drawPath(path(bend.region))
            painter.setPen(QPen(colour, 3.2 if selected else 2, Qt.SolidLine if selected else Qt.DashLine, Qt.RoundCap))
            pa, pb = to(a), to(b); painter.drawLine(pa, pb)
            mid = (pa+pb)/2; badge = QRectF(mid.x()-9, mid.y()-9, 18, 18)
            painter.setPen(QPen(QColor(c['text']), 1.4) if selected else Qt.NoPen); painter.setBrush(colour); painter.drawEllipse(badge)
            painter.setPen(QColor('#FFFFFF')); painter.drawText(badge, Qt.AlignCenter, str(i+1))
        painter.end()

    def step_at(self, position):
        if not self.plan:
            return None
        to = self.mapping(); best = None
        for i, _, (a, b) in self.lines():
            pa, pb = to(a), to(b); d = pb-pa; length2 = d.x()**2+d.y()**2 or 1
            t = max(0, min(1, ((position.x()-pa.x())*d.x()+(position.y()-pa.y())*d.y())/length2))
            distance = hypot(position.x()-pa.x()-t*d.x(), position.y()-pa.y()-t*d.y())
            if distance <= HIT_RADIUS and (best is None or distance < best[0]):
                best = distance, i
        return None if best is None else best[1]

    def mouseMoveEvent(self, event):
        self.setCursor(Qt.PointingHandCursor if self.step_at(event.position()) is not None else Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        index = self.step_at(event.position()) if event.button() == Qt.LeftButton else None
        if index is not None and self.isEnabled():
            self.stepClicked.emit(index)
