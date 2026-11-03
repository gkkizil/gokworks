"""Card-style preset list, assembly card and result insight panel for ISO fits.

Colours come from the theme tokens; fit-type colour is used only for meaning
(clearance = success, transition = warning, interference = danger).
"""

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget

from gui_qt.components import label
from gui_qt.theme import COLORS
from . import guidance as g
from . import rules as r


class PresetDelegate(QStyledItemDelegate):
    """Group headers in the fit-type colour; presets as cards with a coloured bar."""

    def __init__(self, appearance, parent=None):
        super().__init__(parent)
        self.appearance = appearance

    def sizeHint(self, option, index):
        row = index.data(Qt.UserRole) or {}
        return QSize(option.rect.width(), 30 if row.get('header') else 46)

    def paint(self, painter, option, index):
        row = index.data(Qt.UserRole) or {}
        c = COLORS[self.appearance()]
        tone = QColor(c[g.TONES.get(row.get('kind'), 'muted')])
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(2, 2, -4, -2)
        base = QFont(option.font)
        if row.get('header'):
            font = QFont(base); font.setPixelSize(10); font.setBold(True); font.setLetterSpacing(QFont.AbsoluteSpacing, .6)
            painter.setFont(font); painter.setPen(tone)
            painter.drawText(rect.adjusted(6, 8, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, row.get('name', ''))
            painter.restore(); return
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        fill = QColor(c['selected'] if selected else c['hover'] if hovered else c['input'])
        painter.setPen(QPen(QColor(c['accent'] if selected else c['border']), 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 3, 3)
        bar = QRectF(rect.left() + 5, rect.top() + 7, 3, rect.height() - 14)
        painter.setPen(Qt.NoPen); painter.setBrush(tone); painter.drawRoundedRect(bar, 1.5, 1.5)
        title = QFont(base); title.setPixelSize(13); title.setBold(True)
        painter.setFont(title); painter.setPen(QColor(c['text']))
        painter.drawText(QRectF(rect.left() + 16, rect.top() + 5, rect.width() - 20, 19), Qt.AlignLeft | Qt.AlignVCenter,
                         row.get('title', ''))
        small = QFont(base); small.setPixelSize(11)
        painter.setFont(small); painter.setPen(QColor(c['muted']))
        text = painter.fontMetrics().elidedText(row.get('label', ''), Qt.ElideRight, int(rect.width() - 22))
        painter.drawText(QRectF(rect.left() + 16, rect.top() + 23, rect.width() - 20, 16), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()


def _pen(color, width=2.2):
    pen = QPen(color, width); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
    return pen


class AssemblyIcon(QWidget):
    """Small vector pictogram for the assembly method (no bitmap, theme aware)."""

    def __init__(self, appearance):
        super().__init__()
        self.appearance = appearance
        self.kind = 'slide'; self.tone = 'success'
        self.setFixedSize(54, 54)

    def set_kind(self, kind, tone):
        self.kind, self.tone = kind, tone; self.update()

    def paintEvent(self, event):
        c = COLORS[self.appearance()]
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        ink, accent = QColor(c['text']), QColor(c[self.tone])
        p.setPen(_pen(ink))
        w = self.width()
        # Hole (sleeve) common to all pictograms.
        p.drawRect(QRectF(8, 30, w - 16, 6)); p.drawRect(QRectF(8, 44, w - 16, 6))
        p.setBrush(accent); p.setPen(Qt.NoPen)
        if self.kind in ('slide', 'push'):
            p.drawRoundedRect(QRectF(14 if self.kind == 'slide' else 18, 37, w - 28, 6), 2, 2)
            p.setPen(_pen(accent)); p.setBrush(Qt.NoBrush)
            p.drawLine(QPointF(10, 18), QPointF(w - 10, 18))
            for x, d in ((10, 1), (w - 10, -1)) if self.kind == 'slide' else ((w - 10, -1),):
                p.drawLine(QPointF(x, 18), QPointF(x + 6 * d, 13)); p.drawLine(QPointF(x, 18), QPointF(x + 6 * d, 23))
        elif self.kind == 'hammer':
            p.drawRoundedRect(QRectF(18, 37, w - 30, 6), 2, 2)
            p.save(); p.translate(w / 2, 14); p.rotate(-25)
            p.setBrush(ink); p.drawRoundedRect(QRectF(-13, -6, 26, 11), 2, 2)
            p.drawRect(QRectF(-2, 5, 4, 16)); p.restore()
        else:  # press
            p.drawRoundedRect(QRectF(16, 37, w - 32, 6), 2, 2)
            p.setBrush(ink); p.drawRect(QRectF(w / 2 - 12, 6, 24, 6)); p.drawRect(QRectF(w / 2 - 3, 12, 6, 10))
            p.setPen(_pen(accent)); p.setBrush(Qt.NoBrush)
            path = QPainterPath(QPointF(w / 2 - 6, 22)); path.lineTo(w / 2, 28); path.lineTo(w / 2 + 6, 22)
            p.drawPath(path)


class AssemblyCard(QFrame):
    def __init__(self, appearance):
        super().__init__()
        self.setObjectName('assemblyCard')
        self.appearance = appearance
        self.setMinimumWidth(190); self.setMaximumWidth(260)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        body = QVBoxLayout(self); body.setContentsMargins(12, 12, 12, 12); body.setSpacing(4)
        body.addStretch()
        self.icon = AssemblyIcon(appearance); body.addWidget(self.icon, alignment=Qt.AlignHCenter)
        caption = label('MONTAJ', 'muted'); caption.setAlignment(Qt.AlignHCenter); caption.setProperty('eyebrow', True)
        body.addWidget(caption)
        self.title = label('', 'section'); self.title.setAlignment(Qt.AlignHCenter); body.addWidget(self.title)
        self.detail = label('', 'muted'); self.detail.setAlignment(Qt.AlignHCenter); body.addWidget(self.detail)
        body.addStretch()

    def set_fit(self, fit):
        method = g.assembly(fit)
        self.icon.set_kind(method.icon, method.tone)
        self.title.setText(method.title); self.detail.setText(method.detail)
        self.title.setStyleSheet(f'font-size: 14px; color: {COLORS[self.appearance()][method.tone]};')
        self.style_frame(method.tone)

    def style_frame(self, tone):
        c = COLORS[self.appearance()]
        self.setStyleSheet(f'QFrame#assemblyCard {{ background: {c["panel"]}; border: 1px solid {c[tone]}; border-radius: 4px; }}')

    def clear(self):
        self.icon.set_kind('slide', 'muted'); self.title.setText('—'); self.detail.setText('Geçerli sınırlar girin.')
        self.title.setStyleSheet(''); self.style_frame('border')


class InsightPanel(QFrame):
    """Signed minimum/maximum clearance, plain-language result and usage examples."""

    def __init__(self, appearance):
        super().__init__()
        self.setObjectName('fitInsight')
        self.appearance = appearance
        body = QVBoxLayout(self); body.setContentsMargins(12, 10, 12, 10); body.setSpacing(6)
        metrics = QHBoxLayout(); metrics.setSpacing(24)
        self.metric_labels = {}
        for key, caption in (('min', 'EN AZ BOŞLUK · Cmin'), ('max', 'EN ÇOK BOŞLUK · Cmax')):
            column = QVBoxLayout(); column.setSpacing(0)
            title = label(caption, 'muted'); title.setProperty('eyebrow', True); column.addWidget(title)
            value = QLabel(''); value.setTextInteractionFlags(Qt.TextSelectableByMouse); column.addWidget(value)
            self.metric_labels[key] = value; metrics.addLayout(column)
        metrics.addStretch(); body.addLayout(metrics)
        rule = QFrame(); rule.setProperty('separator', True); rule.setFixedHeight(1); body.addWidget(rule)
        self.meaning = label(''); body.addWidget(self.meaning)
        usage_title = label('KULLANIM VE ÖRNEKLER', 'success'); usage_title.setProperty('eyebrow', True)
        usage_title.setObjectName('usageTitle'); body.addWidget(usage_title)
        self.usage_title = usage_title
        self.examples = label(''); self.examples.setTextInteractionFlags(Qt.TextSelectableByMouse); body.addWidget(self.examples)
        self.source = label('', 'muted'); body.addWidget(self.source)
        body.addStretch()

    def set_fit(self, fit, unit):
        c = COLORS[self.appearance()]
        for key, value in (('min', fit.minimum_clearance_nm), ('max', fit.maximum_clearance_nm)):
            word = 'boşluk' if value > 0 else 'sıkılık' if value < 0 else 'temas'
            tone = 'success' if value > 0 else 'danger' if value < 0 else 'warning'
            widget = self.metric_labels[key]
            widget.setText(f'{r.format_deviation(value, unit)} ({word})')
            widget.setStyleSheet(f'font-size: 16px; font-weight: 600; color: {c[tone]};')
        self.meaning.setText({'clearance': 'Mil her ölçü sınırında delikten küçük veya eşittir; parça elle takılır.',
                              'transition': 'Gerçekleşen ölçüye göre küçük boşluk veya sıkılık oluşabilir.',
                              'interference': 'Mil her ölçü sınırında delikten büyüktür; montaj ancak pres veya ısıl yöntemle yapılır.'}[fit.kind])
        text, code, exact = g.usage(fit)
        self.examples.setText(text or 'Bu eşleşme için örnek kaydı yok.')
        self.source.setText((f'{code} için ' if exact else f'En yakın hazır geçme {code}: ') + g.USAGE_NOTE)
        self.usage_title.setStyleSheet(f'color: {c["accent"]};')
        self.setStyleSheet(f'QFrame#fitInsight {{ background: {c["panel"]}; border: 1px solid {c["border"]}; border-radius: 4px; }}')

    def clear(self):
        for widget in self.metric_labels.values():
            widget.setText('—'); widget.setStyleSheet('font-size: 16px; font-weight: 600;')
        self.meaning.setText('Geçerli sınırlar girildiğinde sonuç burada görünür.')
        self.examples.clear(); self.source.clear()


__all__ = ['PresetDelegate', 'AssemblyCard', 'InsightPanel']
