"""2D belt route view: draws the analytic BeltPath (lines + arcs), nothing fitted.

Drawing coordinates are millimetres with +Y up; the widget flips Y. The optional
animation is nominal kinematics only: belt speed v, ω₁ = v/R₁, ω₂ = v/R₂, both
pulleys turning in the same direction (open belt), driven by wall-clock time.
"""

import math
import time

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush, QFont
from PySide6.QtWidgets import QWidget

from gui_qt.theme import COLORS

MARKERS = 24  # belt markers along the route; visual only


def _fmt(value, digits=1):
    return f'{value:.{digits}f}'.replace('.', ',')


class BeltCanvas(QWidget):
    """Read-only route preview. ``set_drive`` takes a BeltDriveResult or None."""
    animationChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.appearance = 'dark'
        self.result = None
        self.message = 'Geçerli bir tasarım yok.'
        self.animating = False
        self._started = 0.
        self.visual_scale = 1.
        self.timer = QTimer(self); self.timer.setInterval(33); self.timer.timeout.connect(self.update)
        self.setMinimumSize(260, 220)
        self.setAccessibleName('Kayış güzergâhı 2B görünümü')
        self.setToolTip('Gerçek teğet çizgi ve yay geometrisi; ölçek otomatik sığdırılır.')

    # ---- state ------------------------------------------------------------------------
    def set_appearance(self, appearance):
        self.appearance = appearance if appearance in COLORS else 'dark'
        self.update()

    def set_drive(self, result, message=''):
        self.result = result
        self.message = message or 'Geçerli bir tasarım yok.'
        if result is None:
            self.set_animating(False)
        else:
            # Slow the nominal motion so a marker needs ≥ ~6 s per lap; the scale is shown.
            speed_mm_s = result.speed_m_s * 1000.
            self.visual_scale = min(1., result.geometry.length_mm / 6. / speed_mm_s)
        self.update()

    def set_animating(self, on):
        on = bool(on) and self.result is not None
        if on == self.animating:
            return
        self.animating = on
        if on:
            self._started = time.monotonic(); self.timer.start()
        else:
            self.timer.stop()
        self.animationChanged.emit(on)
        self.update()

    def elapsed(self):
        return time.monotonic() - self._started if self.animating else 0.

    def kinematic_state(self, seconds):
        """(route distance mm, driver angle rad, driven angle rad) at ``seconds``.

        Positive route distance is clockwise; a CCW driver moves the belt backwards.
        Both pulleys share the belt surface speed, so ω₂/ω₁ = R₁/R₂ = 1/i.
        """
        result = self.result
        sign = 1. if result.specification.rotation == 'ccw' else -1.
        travel = result.speed_m_s * 1000. * self.visual_scale * seconds
        path = result.geometry
        return (-sign * travel, sign * travel / path.driver_radius_mm, sign * travel / path.driven_radius_mm)

    # ---- painting ---------------------------------------------------------------------
    def _transform(self, path):
        r1, r2 = path.driver_radius_mm, path.driven_radius_mm
        xs = (path.driver_center.x - r1, path.driver_center.x + r1, path.driven_center.x - r2, path.driven_center.x + r2)
        ys = (path.driver_center.y - r1, path.driver_center.y + r1, path.driven_center.y - r2, path.driven_center.y + r2)
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        margin = 34.
        width, height = max(self.width() - 2 * margin, 10.), max(self.height() - 2 * margin - 36., 10.)
        scale = min(width / max(x1 - x0, 1e-9), height / max(y1 - y0, 1e-9))
        ox = margin + (width - (x1 - x0) * scale) / 2. - x0 * scale
        oy = margin + (height - (y1 - y0) * scale) / 2. + y1 * scale
        return scale, (lambda p: QPointF(ox + p.x * scale, oy - p.y * scale))

    def paintEvent(self, event):
        colors = COLORS[self.appearance]
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(colors['canvas']))
        if self.result is None:
            painter.setPen(QColor(colors['muted']))
            painter.drawText(self.rect().adjusted(16, 16, -16, -16), Qt.AlignCenter | Qt.TextWordWrap, self.message)
            return
        path = self.result.geometry
        scale, to = self._transform(path)
        # Reference circles of both pulleys (datum / pitch line).
        pulley_pen = QPen(QColor(colors['muted']), 1.2, Qt.DashLine)
        fill = QColor(colors['accent']); fill.setAlpha(28)
        for center, radius, name in ((path.driver_center, path.driver_radius_mm, 'Sürücü'),
                                     (path.driven_center, path.driven_radius_mm, 'Sürülen')):
            c = to(center)
            painter.setPen(pulley_pen); painter.setBrush(QBrush(fill))
            painter.drawEllipse(c, radius * scale, radius * scale)
            painter.setPen(QPen(QColor(colors['muted']), 1)); painter.setBrush(Qt.NoBrush)
            painter.drawLine(c + QPointF(-5, 0), c + QPointF(5, 0)); painter.drawLine(c + QPointF(0, -5), c + QPointF(0, 5))
        # Belt route: one QPainterPath from the exact line and arc segments.
        route = QPainterPath(); route.moveTo(to(path.segments[0].start))
        for segment in path.segments:
            if segment.kind == 'line':
                route.lineTo(to(segment.end))
            else:
                r = segment.radius_mm * scale; c = to(segment.center)
                route.arcTo(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r),
                            math.degrees(segment.start_rad), math.degrees(segment.sweep_rad))
        painter.setPen(QPen(QColor(colors['text']), 2.2)); painter.setBrush(Qt.NoBrush)
        painter.drawPath(route)
        # Tight span marker from the driver's rotation (nominal F₁ side).
        tight = path.segments[0] if self.result.specification.rotation == 'ccw' else path.segments[2]
        painter.setPen(QPen(QColor(colors['warning']), 3.2)); painter.drawLine(to(tight.start), to(tight.end))
        seconds = self.elapsed()
        distance, a1, a2 = self.kinematic_state(seconds) if self.animating else (0., 0., 0.)
        # Pulley spokes rotate with the nominal angular speeds (same direction, ω ratio 1/i).
        painter.setPen(QPen(QColor(colors['accent']), 1.6))
        for center, radius, angle in ((path.driver_center, path.driver_radius_mm, a1), (path.driven_center, path.driven_radius_mm, a2)):
            c = to(center)
            for k in range(3):
                phi = angle + k * 2 * math.pi / 3
                painter.drawLine(c, c + QPointF(math.cos(phi) * radius * scale * .8, -math.sin(phi) * radius * scale * .8))
        if self.animating:
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(colors['accent']))
            step = path.length_mm / MARKERS
            for k in range(MARKERS):
                painter.drawEllipse(to(path.point_at_distance(distance + k * step)), 2.6, 2.6)
        # Labels.
        painter.setPen(QColor(colors['text'])); font = QFont(self.font()); font.setPointSizeF(8.5); painter.setFont(font)
        r = self.result
        for center, radius, title, diameter in ((path.driver_center, path.driver_radius_mm, 'D₁', r.driver_reference_diameter_mm),
                                                (path.driven_center, path.driven_radius_mm, 'D₂', r.driven_reference_diameter_mm)):
            c = to(center)
            painter.drawText(QPointF(c.x() - 30, c.y() + radius * scale + 16), f'{title} {_fmt(diameter)} mm')
        mid = (to(path.driver_center) + to(path.driven_center)) / 2.
        painter.setPen(QColor(colors['muted']))
        painter.drawText(QPointF(mid.x() - 40, mid.y() - 6), f'C {_fmt(r.center_mm, 2)} mm')
        caption = (f'L {_fmt(r.length_exact_mm, 2)} mm · referans çizgisi ({"datum" if r.reference_line == "datum" else "bölüm"}) · '
                   'turuncu: gergin kol (nominal)')
        if self.animating:
            caption += f' · nominal kinematik, görsel hız ×{self.visual_scale:.3g}'.replace('.', ',')
        painter.drawText(QRectF(8, self.height() - 38, self.width() - 16, 34), Qt.AlignLeft | Qt.AlignBottom | Qt.TextWordWrap, caption)
