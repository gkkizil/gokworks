"""Painted step cards for the bend sequence list (display only; data stays in the plan)."""
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate
from gui_qt.theme import COLORS

CARD = Qt.UserRole + 1
# Text + symbol + colour: the three check results never rely on colour alone.
STATES = {'clear': ('✓', 'Kontrol edilen hareketlerde çarpışma yok', 'success'),
          'collision': ('✕', 'Çarpışma var', 'danger'),
          'unknown': ('?', 'Kontrol edilemedi', 'warning'),
          None: ('○', 'Kontrol bekliyor', 'muted')}
PAD, BADGE, CHIP_H = 10, 24, 20


def chips_of(card):
    return [text for text, on in (('Takım değişimi', card.get('change')), ('Yeniden tutuş', card.get('regrip')),
                                  ('Çevir 180°', card.get('flip'))) if on]


class StepCardDelegate(QStyledItemDelegate):
    def __init__(self, view, appearance):
        super().__init__(view); self.view = view; self.appearance = appearance

    def fonts(self, base):
        # The application font may be pixel-sized (point size -1): scale whichever is set.
        title = QFont(base); title.setBold(True); small = QFont(base)
        if base.pointSizeF() > 0:
            title.setPointSizeF(base.pointSizeF()+.5); small.setPointSizeF(max(7.5, base.pointSizeF()-1))
        else:
            title.setPixelSize(base.pixelSize()+1); small.setPixelSize(max(10, base.pixelSize()-1))
        return title, small

    def layout(self, card, width, base):
        """Text block rectangles for a card of ``width``; shared by sizeHint and paint."""
        from PySide6.QtGui import QFontMetrics
        title, small = self.fonts(base)
        left = PAD+BADGE+8; text_w = max(40, width-left-PAD)
        y = PAD; rows = []
        rows.append(('title', QRectF(left, y, text_w, QFontMetrics(title).height()), card['title'])); y += QFontMetrics(title).height()+1
        rows.append(('detail', QRectF(left, y, text_w, QFontMetrics(small).height()), card['detail'])); y += QFontMetrics(small).height()+5
        symbol, text, _ = STATES[card.get('status')]
        status = QFontMetrics(small).boundingRect(0, 0, text_w-16, 400, Qt.TextWordWrap, text)
        rows.append(('status', QRectF(left, y, text_w, status.height()), text)); y += status.height()+4
        x = left; metrics = QFontMetrics(small)
        for chip in chips_of(card):
            w = metrics.horizontalAdvance(chip)+14
            if x > left and x+w > left+text_w:
                x = left; y += CHIP_H+4
            rows.append(('chip', QRectF(x, y, w, CHIP_H), chip)); x += w+6
        if chips_of(card):
            y += CHIP_H
        return rows, y+PAD

    def sizeHint(self, option, index):
        card = index.data(CARD)
        if not card:
            return super().sizeHint(option, index)
        width = self.view.viewport().width()-4
        return QSize(width, int(self.layout(card, width, option.font)[1])+6)

    def paint(self, painter, option, index):
        card = index.data(CARD)
        if not card:
            return super().paint(painter, option, index)
        c = COLORS[self.appearance]; painter.save(); painter.setRenderHint(painter.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(2, 3, -2, -3)
        selected = bool(option.state & QStyle.State_Selected)
        painter.setPen(QPen(QColor(c['accent'] if selected else c['border']), 1.5 if selected else 1))
        painter.setBrush(QColor(c['selected'] if selected else c['panel'])); painter.drawRoundedRect(rect, 6, 6)
        if selected:   # active step: left accent bar in addition to the fill
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(c['accent']))
            painter.drawRoundedRect(QRectF(rect.left(), rect.top()+6, 4, rect.height()-12), 2, 2)
        title, small = self.fonts(option.font)
        badge = QRectF(rect.left()+PAD-2, rect.top()+PAD-2, BADGE, BADGE)
        painter.setPen(Qt.NoPen); painter.setBrush(QColor(c['accent'] if selected else c['input']))
        painter.drawEllipse(badge)
        painter.setPen(QColor(c['on_accent'] if selected else c['text'])); painter.setFont(title)
        painter.drawText(badge, Qt.AlignCenter, str(card['number']))
        rows, _ = self.layout(card, rect.width(), option.font)
        symbol, _, tone = STATES[card.get('status')]
        for kind, box, text in rows:
            box = box.translated(rect.left(), rect.top())
            if kind in ('title', 'detail'):   # one line each; never clipped mid-glyph, the tooltip has the rest
                painter.setFont(title if kind == 'title' else small); painter.setPen(QColor(c['text' if kind == 'title' else 'muted']))
                painter.drawText(box, Qt.AlignLeft | Qt.AlignVCenter, painter.fontMetrics().elidedText(text, Qt.ElideRight, int(box.width())))
            elif kind == 'status':
                painter.setFont(title); painter.setPen(QColor(c[tone])); painter.drawText(QRectF(box.left(), box.top(), 14, box.height()), Qt.AlignLeft | Qt.AlignTop, symbol)
                painter.setFont(small); painter.drawText(box.adjusted(16, 0, 0, 0), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, text)
            else:
                change = text == 'Takım değişimi'; colour = QColor(c['warning'] if change else c['muted'])
                painter.setPen(QPen(colour, 1)); painter.setBrush(Qt.NoBrush); painter.drawRoundedRect(box, 9, 9)
                painter.setFont(small); painter.drawText(box, Qt.AlignCenter, text)
        painter.restore()
