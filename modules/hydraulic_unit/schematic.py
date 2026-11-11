"""Ünite şeması: hesap sonucunu devre üzerinde gösterir; elemana tıklanınca ayarı açılır.

Yalnız görünüm. Değerleri ``BeginnerView`` verir (çekirdek sonucundan); burada
hesap yapılmaz. Semboller sadeleştirilmiş hidrolik devre işaretleridir, ölçekli
veya üretim şeması değildir.
"""
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from gui_qt.theme import COLORS

WIDTH, HEIGHT = 1000., 356.
# Eleman adı, şemadaki etiket kutusu (x, y, genişlik) ve sembolün tıklanabilir alanı.
NODES = {
    'motor': ('Motor', (14, 170, 128), (54, 224, 52, 52)),
    'pump': ('Pompa', (196, 230, 150), (132, 222, 56, 56)),
    'relief': ('Emniyet valfi', (410, 222, 176), (360, 222, 46, 40)),
    'pipe': ('Basınç hattı', (410, 140, 150), (410, 186, 150, 20)),
    'accumulator': ('Akümülatör', (540, 72, 150), (594, 122, 34, 52)),
    'cylinder': ('Silindir', (478, 14, 212), (700, 16, 250, 50)),
    'cooler': ('Soğutucu', (664, 229, 140), (810, 226, 50, 50)),
    'tank': ('Tank', (396, 314, 420), (40, 300, 920, 48)),
}
ORDER = ('cylinder', 'pump', 'motor', 'relief', 'pipe', 'accumulator', 'cooler', 'tank')
STATE_MARK = {'error': '✕', 'warning': '!', 'success': '✓'}
STATE_WORD = {'error': 'kritik', 'warning': 'kontrol edin', 'success': 'uygun'}


@dataclass
class Node:
    value: str = '—'
    detail: str = ''
    state: str | None = None    # None | 'success' | 'warning' | 'error'
    tip: str = ''
    present: bool = True        # False: eleman projede yok (ör. kapalı akümülatör)


class UnitSchematic(QWidget):
    """Tank → pompa/motor → emniyet valfi → hat → yön valfi → silindir → soğutucu → tank."""
    nodeClicked = Signal(str)

    def __init__(self, appearance):
        super().__init__(); self.appearance = appearance
        self.nodes = {key: Node() for key in NODES}; self.nodes['accumulator'].present = False
        self.hover = None; self.empty_text = ''
        self.setMouseTracking(True); self.setFocusPolicy(Qt.StrongFocus)
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed); policy.setHeightForWidth(True); self.setSizePolicy(policy)
        self.setMinimumWidth(520)
        self.setAccessibleName('Ünite şeması')

    # ------------------------------------------------------------------ data
    def set_nodes(self, nodes):
        self.empty_text = ''
        for key, node in nodes.items():
            self.nodes[key] = node
        self.setAccessibleDescription('; '.join(self.summary(key) for key in ORDER if self.nodes[key].present))
        self.update()

    def clear(self, text):
        """No valid result: keep the circuit, drop the numbers."""
        self.empty_text = text
        for key in NODES:
            self.nodes[key] = Node(present=self.nodes[key].present)
        self.setAccessibleDescription(text); self.update()

    def summary(self, key):
        node = self.nodes[key]
        return f'{NODES[key][0]}: {node.value}' + (f' ({STATE_WORD[node.state]})' if node.state else '')

    # ------------------------------------------------------------------ geometry
    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return int(HEIGHT * self.factor(width)) + 8

    def resizeEvent(self, event):
        # Scroll-area layouts do not ask heightForWidth; keep the whole circuit visible ourselves.
        height = self.heightForWidth(self.width())
        if height != self.height():
            self.setFixedHeight(height)

    def sizeHint(self):
        return QSize(900, self.heightForWidth(900))

    def factor(self, width=None):
        return max(.52, min(1., (width or self.width()) / WIDTH))

    def origin(self):
        return QPointF((self.width() - WIDTH * self.factor()) / 2, 4)

    def label_rect(self, key):
        x, y, w = NODES[key][1]
        return QRectF(x, y, w, 30 if key == 'tank' else 44)

    def hit_rects(self, key):
        return [self.label_rect(key), QRectF(*NODES[key][2])]

    def node_at(self, position):
        f, o = self.factor(), self.origin()
        point = QPointF((position.x() - o.x()) / f, (position.y() - o.y()) / f)
        for key in ORDER:
            if self.nodes[key].present and any(r.adjusted(-4, -4, 4, 4).contains(point) for r in self.hit_rects(key)):
                return key
        return None

    def node_center(self, key):
        """Widget coordinates of a node's label (for tests and keyboard focus)."""
        f, o = self.factor(), self.origin(); c = self.label_rect(key).center()
        return QPointF(o.x() + c.x() * f, o.y() + c.y() * f).toPoint()

    # ------------------------------------------------------------------ interaction
    def mouseMoveEvent(self, event):
        key = self.node_at(event.position())
        if key != self.hover:
            self.hover = key; self.setCursor(Qt.PointingHandCursor if key else Qt.ArrowCursor); self.update()
        if key and self.nodes[key].tip:
            QToolTip.showText(event.globalPosition().toPoint(), self.nodes[key].tip, self)

    def leaveEvent(self, event):
        self.hover = None; self.setCursor(Qt.ArrowCursor); self.update()

    def mouseReleaseEvent(self, event):
        key = self.node_at(event.position()) if event.button() == Qt.LeftButton else None
        if key:
            self.hover = key; self.nodeClicked.emit(key)

    def keyPressEvent(self, event):
        keys = [k for k in ORDER if self.nodes[k].present]
        if event.key() in (Qt.Key_Right, Qt.Key_Down, Qt.Key_Left, Qt.Key_Up):
            step = 1 if event.key() in (Qt.Key_Right, Qt.Key_Down) else -1
            self.hover = keys[(keys.index(self.hover) + step) % len(keys)] if self.hover in keys else keys[0]
            self.update()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and self.hover in keys:
            self.nodeClicked.emit(self.hover)
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        if self.hover is None:
            self.hover = 'cylinder'
        self.update()

    def focusOutEvent(self, event):
        self.hover = None; self.update()

    # ------------------------------------------------------------------ painting
    def paintEvent(self, event):
        c = COLORS[self.appearance]
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(c['border']), 1)); p.setBrush(QColor(c['canvas']))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 8, 8)
        f, o = self.factor(), self.origin()
        p.translate(o); p.scale(f, f)
        ink, muted = QColor(c['text']), QColor(c['muted'])
        pressure, back = QColor(c['accent']), QColor(c['muted'])
        tone = lambda key: QColor(c[{'error': 'danger', 'warning': 'warning', 'success': 'success'}[self.nodes[key].state]]) \
            if self.nodes[key].state else ink
        line = lambda colour, width=2.4, style=Qt.SolidLine: QPen(colour, width, style, Qt.RoundCap, Qt.RoundJoin)

        def path(points, pen):
            shape = QPainterPath(QPointF(*points[0]))
            for point in points[1:]:
                shape.lineTo(QPointF(*point))
            p.setPen(pen); p.setBrush(Qt.NoBrush); p.drawPath(shape)

        # Tank: open-top reservoir with oil level.
        p.setPen(Qt.NoPen); oil = QColor(pressure); oil.setAlpha(34); p.setBrush(oil); p.drawRect(QRectF(40, 314, 920, 34))
        path([(40, 300), (40, 348), (960, 348), (960, 300)], line(tone('tank')))
        path([(52, 314), (948, 314)], line(muted, 1, Qt.DashLine))
        # Suction and return lines (grey; returns dashed), then pressure lines (accent).
        path([(160, 276), (160, 332)], line(back))
        path([(380, 262), (380, 332)], line(back, 2, Qt.DashLine))
        path([(835, 154), (835, 226)], line(back, 2, Qt.DashLine)); path([(835, 276), (835, 332)], line(back, 2, Qt.DashLine))
        path([(160, 224), (160, 196), (785, 196), (785, 154)], line(pressure, 3))
        path([(380, 196), (380, 222)], line(pressure))
        path([(785, 108), (785, 84), (725, 84), (725, 62)], line(pressure))        # A: cap end
        path([(835, 108), (835, 84), (900, 84), (900, 62)], line(back))            # B: rod end
        for x in (380, 160):                                                     # junction dots
            p.setPen(Qt.NoPen); p.setBrush(pressure); p.drawEllipse(QPointF(x, 196), 4, 4)

        # Motor + pump.
        p.setBrush(QColor(c['panel'])); p.setPen(line(tone('motor'))); p.drawEllipse(QPointF(80, 250), 24, 24)
        font = QFont(self.font()); font.setPixelSize(17); font.setBold(True); p.setFont(font)
        p.drawText(QRectF(56, 226, 48, 48), Qt.AlignCenter, 'M')
        path([(104, 250), (134, 250)], line(ink, 3))
        p.setBrush(QColor(c['panel'])); p.setPen(line(tone('pump'))); p.drawEllipse(QPointF(160, 250), 26, 26)
        p.setBrush(tone('pump')); p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(160, 226), QPointF(151, 241), QPointF(169, 241)]))
        # Relief valve: box, arrow, spring.
        p.setBrush(QColor(c['panel'])); p.setPen(line(tone('relief'))); p.drawRect(QRectF(362, 222, 36, 40))
        path([(380, 254), (380, 232)], line(tone('relief'), 1.8)); path([(375, 239), (380, 231), (385, 239)], line(tone('relief'), 1.8))
        path([(398, 234), (405, 230), (398, 240), (405, 246), (398, 250)], line(tone('relief'), 1.4))
        # Pipe tag on the pressure line.
        p.setBrush(QColor(c['canvas'])); p.setPen(line(tone('pipe'), 1.6)); p.drawRoundedRect(QRectF(452, 187, 66, 18), 9, 9)
        font.setPixelSize(10); font.setBold(True); p.setFont(font); p.setPen(tone('pipe'))
        p.drawText(QRectF(452, 187, 66, 18), Qt.AlignCenter, 'HAT')
        # Accumulator (only when the project has one).
        if self.nodes['accumulator'].present:
            path([(611, 196), (611, 172)], line(pressure)); p.setPen(Qt.NoPen); p.setBrush(pressure); p.drawEllipse(QPointF(611, 196), 4, 4)
            p.setBrush(QColor(c['panel'])); p.setPen(line(tone('accumulator'))); p.drawRoundedRect(QRectF(597, 124, 28, 48), 14, 14)
            path([(597, 150), (625, 150)], line(tone('accumulator'), 1.4))
        # Directional valve: two envelopes.
        p.setBrush(QColor(c['panel'])); p.setPen(line(ink, 2)); p.drawRect(QRectF(760, 108, 100, 46)); path([(810, 108), (810, 154)], line(ink, 1.4))
        path([(785, 148), (785, 116)], line(ink, 1.4)); path([(780, 124), (785, 115), (790, 124)], line(ink, 1.4))
        path([(835, 116), (835, 148)], line(ink, 1.4)); path([(830, 140), (835, 149), (840, 140)], line(ink, 1.4))
        # Cooler: diamond with flow arrow.
        p.setBrush(QColor(c['panel'])); p.setPen(line(tone('cooler')))
        p.drawPolygon(QPolygonF([QPointF(835, 226), QPointF(860, 251), QPointF(835, 276), QPointF(810, 251)]))
        path([(819, 251), (851, 251)], line(tone('cooler'), 1.4)); path([(845, 246), (851, 251), (845, 256)], line(tone('cooler'), 1.4))
        # Cylinder: barrel, piston, rod.
        p.setBrush(QColor(c['panel'])); p.setPen(line(tone('cylinder'))); p.drawRect(QRectF(700, 16, 210, 46))
        p.setBrush(tone('cylinder')); p.setPen(Qt.NoPen); p.drawRect(QRectF(790, 18, 12, 42)); p.drawRect(QRectF(802, 33, 150, 12))

        # Line legend: colour is backed by line style and words.
        font.setPixelSize(12); font.setBold(False); p.setFont(font)
        for y, pen, text in ((26, line(pressure, 3), 'Basınç hattı'), (46, line(back, 2, Qt.DashLine), 'Dönüş hattı (tanka)')):
            path([(20, y), (60, y)], pen); p.setPen(muted); p.drawText(QRectF(68, y - 9, 220, 18), Qt.AlignLeft | Qt.AlignVCenter, text)
        for key in ORDER:
            if self.nodes[key].present:
                self.paint_label(p, c, key)
        if self.empty_text:
            font.setPixelSize(13); font.setBold(False); p.setFont(font); p.setPen(QColor(c['danger']))
            p.drawText(QRectF(196, 92, 200, 44), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, self.empty_text)
        p.end()

    def paint_label(self, p, c, key):
        node, rect = self.nodes[key], self.label_rect(key)
        active = key == self.hover
        state = {'error': 'danger', 'warning': 'warning', 'success': 'success'}.get(node.state)
        tank = key == 'tank'
        if not tank:
            p.setPen(QPen(QColor(c['accent'] if active else c['border']), 1.6 if active else 1)); p.setBrush(QColor(c['panel']))
            p.drawRoundedRect(rect, 6, 6)
            if state:
                p.setPen(Qt.NoPen); p.setBrush(QColor(c[state])); p.drawRoundedRect(QRectF(rect.left(), rect.top() + 5, 3.5, rect.height() - 10), 1.5, 1.5)
        small = QFont(self.font()); small.setPixelSize(12)
        strong = QFont(self.font()); strong.setPixelSize(16); strong.setBold(True)
        mark = STATE_MARK.get(node.state, '')
        inner = rect.adjusted(10, 3, -8, -3)
        if tank:                      # one line inside the reservoir
            p.setFont(strong); p.setPen(QColor(c[state]) if state else QColor(c['text']))
            text = f'{mark + "  " if mark else ""}Tank · {node.value}' + (f' · {node.detail}' if node.detail else '')
            if active:
                strong.setUnderline(True); p.setFont(strong)
            p.drawText(inner, Qt.AlignLeft | Qt.AlignVCenter, p.fontMetrics().elidedText(text, Qt.ElideRight, int(inner.width())))
            return
        p.setFont(small); p.setPen(QColor(c['muted']))
        title = NODES[key][0] + (f' · {node.detail}' if node.detail else '')
        p.drawText(QRectF(inner.left(), inner.top(), inner.width() - 14, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(title, Qt.ElideRight, int(inner.width()) - 14))
        if mark:
            small.setBold(True); p.setFont(small); p.setPen(QColor(c[state]))
            p.drawText(QRectF(inner.right() - 14, inner.top(), 14, 16), Qt.AlignRight | Qt.AlignVCenter, mark)
        p.setFont(strong); p.setPen(QColor(c['text']))
        p.drawText(QRectF(inner.left(), inner.top() + 17, inner.width(), 21), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(node.value, Qt.ElideRight, int(inner.width())))
