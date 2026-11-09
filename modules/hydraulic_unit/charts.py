"""Hidrolik ekranının küçük, bağımsız grafikleri; değerler hesap sonucundan gelir."""

import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from gui_qt.theme import COLORS


def nice_ticks(top, count=4):
    """Rounded axis steps (1, 2, 2.5, 5 × 10^n) from zero to at least ``top``."""
    if top <= 0 or not math.isfinite(top):
        return [0, 1]
    raw = top / count
    power = 10 ** math.floor(math.log10(raw))
    step = next(m * power for m in (1, 2, 2.5, 5, 10) if m * power >= raw)
    ticks = [0.]
    while ticks[-1] < top - 1e-9:
        ticks.append(ticks[-1] + step)
    return ticks


def tick_text(value):
    text = f'{value:.2f}'.rstrip('0').rstrip('.') if abs(value) < 10 else f'{value:.0f}'
    return text.replace('.', ',')


class _Plot(QWidget):
    """Shared frame: title, unit, y ticks, time axis and phase boundaries."""

    def __init__(self, title, unit, minimum=150):
        super().__init__()
        self.title, self.unit, self.appearance, self.names = title, unit, 'dark', []
        self.setMinimumHeight(minimum)

    def colours(self):
        return COLORS[self.appearance]

    def frame(self, p, durations, top):
        c = self.colours()
        p.fillRect(self.rect(), QColor(c['canvas']))
        bold = QFont(self.font()); bold.setBold(True); p.setFont(bold); p.setPen(QColor(c['text']))
        p.drawText(QRectF(10, 4, self.width() - 20, 18), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        small = QFont(self.font()); small.setPixelSize(max(9, self.font().pixelSize() - 1 if self.font().pixelSize() > 0 else 10))
        p.setFont(small); p.setPen(QColor(c['muted']))
        p.drawText(QRectF(10, 4, self.width() - 20, 18), Qt.AlignRight | Qt.AlignVCenter, self.unit)
        ticks = nice_ticks(top)
        width = max(p.fontMetrics().horizontalAdvance(tick_text(t)) for t in ticks)
        left, top_y, right, bottom = width + 16, 30, self.width() - 12, self.height() - 34
        if right - left < 40 or bottom - top_y < 30:
            return None
        total = sum(durations) or 1.
        sy = (bottom - top_y) / ticks[-1]; sx = (right - left) / total
        for t in ticks:
            y = bottom - t * sy
            p.setPen(QPen(QColor(c['grid']), 1)); p.drawLine(QPointF(left, y), QPointF(right, y))
            p.setPen(QColor(c['muted'])); p.drawText(QRectF(2, y - 8, left - 8, 16), Qt.AlignRight | Qt.AlignVCenter, tick_text(t))
        # time axis: phase boundaries with their cumulative time
        p.setPen(QPen(QColor(c['border_strong']), 1)); p.drawLine(QPointF(left, bottom), QPointF(right, bottom))
        elapsed, last_x = 0., -100.
        for i, duration in enumerate([0.] + list(durations)):
            elapsed += duration; x = left + elapsed * sx
            if i:
                p.setPen(QPen(QColor(c['grid']), 1, Qt.DashLine)); p.drawLine(QPointF(x, top_y), QPointF(x, bottom))
            if x - last_x > 34 or i == len(durations):
                p.setPen(QColor(c['muted'])); p.drawText(QRectF(x - 30, bottom + 3, 60, 14), Qt.AlignHCenter | Qt.AlignTop, tick_text(elapsed))
                last_x = x
        p.drawText(QRectF(left, bottom + 17, right - left, 14), Qt.AlignHCenter | Qt.AlignTop, 'zaman · s (faz sınırları kesikli)')
        return left, top_y, right, bottom, sx, sy

    def empty(self, p, text='Geçerli sonuç yok'):
        c = self.colours(); p.fillRect(self.rect(), QColor(c['canvas']))
        p.setPen(QColor(c['muted'])); p.drawText(self.rect(), Qt.AlignCenter, text)


class StepChart(_Plot):
    """Cumulative-time step curve of one phase quantity (requirement, not supply)."""

    def __init__(self, title, unit):
        super().__init__(title, unit)
        self.points = []

    def set_values(self, durations, values, names=()):
        self.points = list(zip(durations, values)); self.names = list(names); self.update()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        try:
            if not self.points:
                self.empty(p); return
            top = max(v for _, v in self.points) * 1.1 or 1.
            geometry = self.frame(p, [d for d, _ in self.points], top)
            if geometry is None:
                return
            left, top_y, right, bottom, sx, sy = geometry
            c = self.colours(); accent = QColor(c['accent'])
            outline, t = [QPointF(left, bottom)], 0.
            for duration, value in self.points:
                y = bottom - value * sy
                outline += [QPointF(left + t * sx, y), QPointF(left + (t + duration) * sx, y)]; t += duration
            outline.append(QPointF(left + t * sx, bottom))
            fill = QColor(accent); fill.setAlpha(40)
            p.setPen(Qt.NoPen); p.setBrush(fill); p.drawPolygon(QPolygonF(outline))
            p.setBrush(Qt.NoBrush); p.setPen(QPen(accent, 2)); p.drawPolyline(QPolygonF(outline[1:-1]))
        finally:
            p.end()


class MotionStrip(_Plot):
    """Rod position over the cycle: what the machine does, phase by phase."""

    def __init__(self):
        super().__init__('Hareket sırası · milin konumu', 'mm', minimum=160)
        self.segments = []      # (name, duration, start mm, end mm, feasible)

    def set_segments(self, segments):
        self.segments = list(segments); self.update()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        try:
            if not self.segments:
                self.empty(p, 'Hareketler geçerli olduğunda burada gösterilir'); return
            top = max(max(s[2], s[3]) for s in self.segments) * 1.1 or 1.
            geometry = self.frame(p, [s[1] for s in self.segments], top)
            if geometry is None:
                return
            left, top_y, right, bottom, sx, sy = geometry
            c = self.colours(); t = 0.
            for name, duration, start, end, feasible in self.segments:
                x0, x1 = left + t * sx, left + (t + duration) * sx
                colour = QColor(c['accent'] if feasible else c['danger'])
                p.setPen(QPen(colour, 2.5)); p.drawLine(QPointF(x0, bottom - start * sy), QPointF(x1, bottom - end * sy))
                if x1 - x0 > 40:
                    p.setPen(QColor(c['text'] if feasible else c['danger']))
                    p.drawText(QRectF(x0 + 2, top_y - 2, x1 - x0 - 4, 14), Qt.AlignHCenter | Qt.AlignTop,
                               p.fontMetrics().elidedText(name + ('' if feasible else ' · yetersiz'), Qt.ElideRight, int(x1 - x0 - 4)))
                t += duration
        finally:
            p.end()
