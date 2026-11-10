"""Existing native mesh viewer plus projected bend/collision annotations."""
import numpy as np
import shiboken6
from PySide6.QtCore import QPointF, QRectF, Qt, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget
from modules.gear_calculator.families.mesh_view import MechanismMeshView
from modules.dxf_dwg.preview.viewer import matrices

AXIS, PUNCH, DIE, HIT = '#e7ad35', '#5aa2e6', '#4fbf8f', '#f14d4d'
# Colour is never the only signal: every swatch carries its name (and the scene repeats it).
LEGEND = (('Parça', None), ('Üst takım', PUNCH), ('Alt takım', DIE), ('Büküm ekseni', AXIS), ('Çarpışma', HIT))


def pill(painter, rect, text, ink, fill, bounds=None, taken=()):
    if bounds is not None:   # stay inside the scene, below the read-out band, and off earlier labels
        rect.moveLeft(min(max(rect.left(), bounds.left()), bounds.right()-rect.width()))
        rect.moveTop(min(max(rect.top(), bounds.top()), bounds.bottom()-rect.height()))
        for other in taken:
            if rect.intersects(other):
                rect.moveTop(other.bottom()+4)
    painter.setPen(Qt.NoPen); painter.setBrush(fill); painter.drawRoundedRect(rect, 4, 4)
    painter.setPen(ink); painter.drawText(rect, Qt.AlignCenter, text)


class BendAnnotations(QWidget):
    """Bend axis, assigned tool outlines, collision markers, step read-out and legend.

    Kept separate from the base viewer's own overlay (view cube): that one handles
    hover/click on the cube and must not be replaced.
    """
    def __init__(self, viewer):
        super().__init__(viewer); self.viewer = viewer
        self.hud = ''; self.state = None   # state: None | 'clear' | 'collision' | 'unknown'
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def colours(self):
        light = self.viewer.background.lightness() > 128
        return (QColor('#1F2328') if light else QColor('#E3E5E8'),
                QColor(255, 255, 255, 215) if light else QColor(30, 31, 34, 215))

    def paintEvent(self, event):
        v = self.viewer
        if v.mesh is None:
            return
        low, high = np.array(v.mesh.bounds[:3]), np.array(v.mesh.bounds[3:])
        center = (low+high)/2; scale = 2/max(high-low)
        _, mvp = matrices(v.camera.state(), max(1, v.width())/max(1, v.height()))
        def project(xyz):
            xyz = np.asarray(xyz)[[0, 2, 1]]*np.array([1., 1., -1.])
            normalized = (xyz-np.array(v.mesh.origin)-center)*scale
            p = mvp@np.r_[normalized, 1.]; p = p[:3]/p[3]
            return QPointF((p[0]+1)*self.width()/2, (1-p[1])*self.height()/2)
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        ink, plate = self.colours()
        font = QFont(self.font()); font.setPixelSize(11); font.setBold(True); painter.setFont(font)
        bounds = QRectF(6, 46, self.width()-12, self.height()-82); taken = []
        if v.frame is not None:
            a, b = project(v.frame.axis[0]), project(v.frame.axis[1])
            painter.setPen(QPen(QColor(AXIS), 3, Qt.DashLine)); painter.drawLine(a, b)
            # The selected tool assemblies are visibly outlined; underlying
            # bodies remain the actual collision geometry, not bounding boxes.
            labelled = set()
            for id, box in v.frame.tool_bounds:
                if id.startswith('holder:'):
                    continue
                punch = id.startswith('punch:'); colour = QColor(PUNCH if punch else DIE)
                painter.setPen(QPen(colour, 1.6)); painter.setBrush(Qt.NoBrush)
                corners = [(box[x], box[1+y], box[2+z]) for x in (0, 3) for y in (0, 3) for z in (0, 3)]
                points = [project(c) for c in corners]
                for i, p in enumerate(corners):
                    for j, q in enumerate(corners):
                        if i < j and sum(x != y for x, y in zip(p, q)) == 1:
                            painter.drawLine(points[i], points[j])
                kind = 'punch' if punch else 'die'
                if kind not in labelled:
                    labelled.add(kind)
                    edge = min(points, key=lambda p: p.y()) if punch else max(points, key=lambda p: p.y())
                    text = 'ÜST TAKIM' if punch else 'ALT TAKIM'; width = painter.fontMetrics().horizontalAdvance(text)+12
                    rect = QRectF(edge.x()-width/2, edge.y()-22 if punch else edge.y()+4, width, 18)
                    pill(painter, rect, text, QColor('#0B1626'), colour, bounds, taken); taken.append(rect)
            end = b if b.x() >= a.x() else a; text = 'BÜKÜM EKSENİ'; width = painter.fontMetrics().horizontalAdvance(text)+12
            rect = QRectF(end.x()+8, end.y()-9, width, 18)
            pill(painter, rect, text, QColor('#1B1300'), QColor(AXIS), bounds, taken); taken.append(rect)
            for hit in v.frame.hits:
                p = project(hit.location); painter.setPen(QPen(QColor(HIT), 3)); painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(p, 11, 11)
                painter.drawLine(p+QPointF(-16, 0), p+QPointF(16, 0)); painter.drawLine(p+QPointF(0, -16), p+QPointF(0, 16))
            if v.frame.hits:
                p = project(v.frame.hits[0].location); text = '✕ ÇARPIŞMA'
                width = painter.fontMetrics().horizontalAdvance(text)+12
                rect = QRectF(p.x()-width-16, p.y()-30, width, 18)
                pill(painter, rect, text, QColor('#FFFFFF'), QColor(HIT), bounds, taken); taken.append(rect)
        self.paint_hud(painter, ink, plate); self.paint_legend(painter, ink, plate)
        painter.end()

    def paint_hud(self, painter, ink, plate):
        if not self.hud:
            return
        font = QFont(self.font()); font.setPixelSize(13); font.setBold(True); painter.setFont(font)
        metrics = painter.fontMetrics(); width = max(60, min(self.width()-120, metrics.horizontalAdvance(self.hud)+24))   # room for the view cube
        rect = QRectF(10, 10, width, 28)   # top left: the view cube owns the top right corner
        accent = {'collision': QColor(HIT), 'clear': QColor('#56C08D'), 'unknown': QColor(AXIS)}.get(self.state, QColor('#9DA2AB'))
        painter.setPen(QPen(accent, 1.5)); painter.setBrush(plate); painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(ink)
        painter.drawText(rect.adjusted(12, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft,
                         metrics.elidedText(self.hud, Qt.ElideRight, int(rect.width())-20))

    def paint_legend(self, painter, ink, plate):
        font = QFont(self.font()); font.setPixelSize(11); painter.setFont(font); metrics = painter.fontMetrics()
        part = QColor('#8A929C' if self.viewer.background.lightness() > 128 else '#B5BBC4')
        items = [(text, QColor(colour) if colour else part) for text, colour in LEGEND]
        widths = [metrics.horizontalAdvance(t)+24 for t, _ in items]
        if sum(widths)+110 > self.width():          # narrow scene: the read-out and markers matter more
            return
        x, y = self.width()-sum(widths)-14, self.height()-30   # bottom right: the axis triad is bottom left
        painter.setPen(Qt.NoPen); painter.setBrush(plate)
        painter.drawRoundedRect(QRectF(x-4, y-3, sum(widths)+8, 24), 5, 5)
        for (text, colour), width in zip(items, widths):
            painter.setPen(Qt.NoPen); painter.setBrush(colour); painter.drawRoundedRect(QRectF(x+2, y+4, 11, 11), 2, 2)
            painter.setPen(ink); painter.drawText(QRectF(x+17, y, width-17, 18), Qt.AlignVCenter | Qt.AlignLeft, text)
            x += width


class SceneView(MechanismMeshView):
    def __init__(self):
        super().__init__(); self.frame = None
        # MeshView owns `overlay` for its interactive view cube. Replacing it
        # breaks inherited leave/move/click handlers when branches are combined.
        self.bend_annotations = BendAnnotations(self)
        self.setAccessibleName('Sac, büküm ekseni ve atanmış takımların 3B sahnesi')
        self.frameReady.connect(self.bend_annotations.update)

    def set_frame(self, frame):
        self.frame = frame
        self.set_mesh(frame.mesh); self.bend_annotations.update()

    @property
    def annotations(self):
        """Keep the UI's HUD accessor without replacing MeshView.overlay."""
        return self.bend_annotations

    @Slot(int, object)
    def rendered(self, generation, image):
        if shiboken6.isValid(self):
            super().rendered(generation, image)

    def set_hud(self, text, state=None):
        self.bend_annotations.hud, self.bend_annotations.state = text, state
        self.setAccessibleDescription(text); self.bend_annotations.update()

    def changed(self):
        super().changed()
        if hasattr(self, 'bend_annotations'):
            self.bend_annotations.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'bend_annotations'):
            self.bend_annotations.setGeometry(self.rect()); self.bend_annotations.raise_()
            self.overlay.raise_()

    @Slot(str)
    def fallback(self, message=''):
        super().fallback(message)
        if hasattr(self, 'bend_annotations'):
            self.bend_annotations.raise_()
            self.overlay.raise_()
