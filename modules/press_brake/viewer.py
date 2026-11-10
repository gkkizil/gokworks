"""Existing native mesh viewer plus projected bend/collision annotations."""
import numpy as np
from PySide6.QtCore import QPointF, Qt, Slot
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget
from modules.gear_calculator.families.mesh_view import MechanismMeshView
from modules.dxf_dwg.preview.viewer import matrices


class BendAnnotations(QWidget):
    def __init__(self, viewer):
        super().__init__(viewer); self.viewer = viewer
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

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
        if v.frame is not None:
            painter.setPen(QPen(QColor('#e7ad35'), 2, Qt.DashLine))
            painter.drawLine(project(v.frame.axis[0]), project(v.frame.axis[1]))
            # The selected tool assemblies are visibly outlined; underlying
            # bodies remain the actual collision geometry, not bounding boxes.
            for id, b in v.frame.tool_bounds:
                if id.startswith('holder:'):
                    continue
                painter.setPen(QPen(QColor('#68a7d8' if id.startswith('punch:') else '#67b59a'), 1, Qt.DotLine))
                corners = [(b[x], b[1+y], b[2+z]) for x in (0, 3) for y in (0, 3) for z in (0, 3)]
                for i, a in enumerate(corners):
                    for j, c in enumerate(corners):
                        if i < j and sum(x != y for x, y in zip(a, c)) == 1:
                            painter.drawLine(project(a), project(c))
            painter.setPen(QPen(QColor('#f14d4d'), 3))
            for hit in v.frame.hits:
                p = project(hit.location); painter.drawEllipse(p, 10, 10)
                painter.drawLine(p+QPointF(-14, 0), p+QPointF(14, 0))
                painter.drawLine(p+QPointF(0, -14), p+QPointF(0, 14))
        painter.end()


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

    def changed(self):
        super().changed()
        if hasattr(self, 'bend_annotations'):
            self.bend_annotations.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'bend_annotations'):
            self.bend_annotations.setGeometry(self.rect()); self.bend_annotations.raise_()

    @Slot(str)
    def fallback(self, message=''):
        super().fallback(message)
        if hasattr(self, 'bend_annotations'):
            self.bend_annotations.raise_()
