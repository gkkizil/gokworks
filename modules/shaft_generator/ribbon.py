"""Top command ribbon of the shaft page: categories, their commands and small line icons.

A CAD-style strip (SOLIDWORKS CommandManager / Fusion toolbar): one row of
categories, one row with the commands of the selected category. Each command
opens an existing editor page; no shaft logic lives here.
"""

from functools import lru_cache

from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QToolButton, QWidget

# key, title, tooltip, [(command title, editor page key, tooltip)]
CATEGORIES = (
    ('stages', 'Kademeler', 'Milin çaplarını ve boylarını girin.',
     (('Çap ve boy', 'stages', 'Kademeleri tabloya yazın; soldan sağa sıralanır.'),)),
    ('channels', 'Kanallar', 'Segman ve kama kanalı ekleyin.',
     (('Segman kanalı', 'groove', 'DIN 471 segman kanalı; ölçüler standarttan gelir.'),
      ('Kama kanalı', 'keyway', 'DIN 6885 kama kanalı; ölçüler standarttan gelir.'))),
    ('edges', 'Kenarlar', 'Pah ve radyüs.',
     (('Tüm kenarlara', 'bulk', 'Mil uçlarına ve bütün omuzlara tek seferde pah veya radyüs.'),
      ('Tek kenara pah', 'chamfer', 'Seçilen kademenin bir kenarına 45° pah.'),
      ('Tek kenara radyüs', 'fillet', 'Seçilen kademenin bir kenarına radyüs.'))),
    ('thread', 'Diş', 'Metrik kozmetik diş.',
     (('Kozmetik diş', 'cosmetic_thread', 'Metrik sağ diş gösterimi; katı hacmi değişmez.'),)),
    ('bore', 'İç delik', 'Eksenel delik.',
     (('Eksenel iç delik', 'bore', 'Boydan boya veya kör delik.'),)),
    ('drawing', 'Teknik resim', 'Sayfa, görünüş, tolerans ve yüzey.',
     (('Tolerans ve yüzey', 'drawing', 'SOLIDWORKS teknik resmi için ayarlar.'),)),
)


@lru_cache(maxsize=64)
def ribbon_icon(name, color):
    """Small line icon (20 px logical) drawn with QPainter; follows the theme colour."""
    pixmap = QPixmap(40, 40); pixmap.setDevicePixelRatio(2); pixmap.fill(Qt.transparent)
    p = QPainter(pixmap); p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(color), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); p.setBrush(Qt.NoBrush)
    if name == 'stages':
        p.drawPolyline([QPointF(2, 8), QPointF(7, 8), QPointF(7, 5), QPointF(13, 5), QPointF(13, 7), QPointF(18, 7),
                        QPointF(18, 13), QPointF(13, 13), QPointF(13, 15), QPointF(7, 15), QPointF(7, 12), QPointF(2, 12), QPointF(2, 8)])
    elif name == 'channels':
        p.drawRect(QRectF(2, 6, 16, 8)); p.drawLine(QPointF(9, 6), QPointF(9, 9)); p.drawLine(QPointF(11, 6), QPointF(11, 9))
        p.drawLine(QPointF(9, 9), QPointF(11, 9))
    elif name == 'edges':
        p.drawPolyline([QPointF(3, 17), QPointF(3, 8), QPointF(8, 3), QPointF(17, 3)])
    elif name == 'thread':
        p.drawRect(QRectF(2, 6, 16, 8))
        for x in (5, 9, 13):
            p.drawLine(QPointF(x, 6), QPointF(x + 2, 14))
    elif name == 'bore':
        p.drawRect(QRectF(2, 4, 16, 12)); p.drawLine(QPointF(2, 8), QPointF(18, 8)); p.drawLine(QPointF(2, 12), QPointF(18, 12))
    elif name == 'drawing':
        p.drawRect(QRectF(3, 2, 14, 16)); p.drawLine(QPointF(6, 7), QPointF(14, 7)); p.drawLine(QPointF(6, 11), QPointF(14, 11))
        p.drawLine(QPointF(10, 14), QPointF(14, 14))
    p.end()
    return QIcon(pixmap)


class CommandRibbon(QWidget):
    """Category row and command row; emits the editor page key to open."""
    commandChosen = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('shaftRibbon')
        self.category_buttons, self.command_buttons, self.command_of = {}, {}, {}
        self.category_row = QHBoxLayout(); self.category_row.setContentsMargins(0, 0, 0, 0); self.category_row.setSpacing(2)
        self.categories = QButtonGroup(self); self.categories.setExclusive(True)
        for key, title, tip, commands in CATEGORIES:
            button = QToolButton(); button.setText(title); button.setCheckable(True); button.setAutoRaise(True)
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); button.setIconSize(QSize(20, 20))
            button.setToolTip(title + ' · ' + tip); button.setAccessibleName('Mil bölümü: ' + title); button.setProperty('ribbonTab', True)
            button.setMinimumWidth(34)        # icon-only below 640 px (set_compact); never forces the page wider
            button.clicked.connect(lambda checked=False, k=key: self.choose_category(k))
            self.categories.addButton(button); self.category_buttons[key] = button; self.category_row.addWidget(button)
            for command_title, page, command_tip in commands:
                command = QToolButton(); command.setText(command_title); command.setCheckable(True)
                command.setToolButtonStyle(Qt.ToolButtonTextOnly); command.setToolTip(command_tip)
                command.setAccessibleName(title + ' · ' + command_title); command.setProperty('ribbonCommand', True)
                command.setMinimumWidth(40)
                command.clicked.connect(lambda checked=False, pg=page: self.commandChosen.emit(pg))
                self.command_buttons[page] = command; self.command_of[page] = key
        self.command_row = QHBoxLayout(); self.command_row.setContentsMargins(0, 0, 0, 0); self.command_row.setSpacing(4)
        for page, command in self.command_buttons.items():
            self.command_row.addWidget(command)
        self.current_page = None

    def choose_category(self, key):
        """Open the first command of a category (or keep its current one)."""
        if self.current_page is not None and self.command_of[self.current_page] == key:
            return
        first = next(commands for k, _, _, commands in CATEGORIES if k == key)[0][1]
        self.commandChosen.emit(first)

    def show_page(self, page):
        """Reflect the open editor page: its category is checked, its commands are shown."""
        self.current_page = page
        category = self.command_of.get(page)
        for key, button in self.category_buttons.items():
            button.setChecked(key == category)
        for name, command in self.command_buttons.items():
            command.setVisible(self.command_of[name] == category)
            command.setChecked(name == page)

    def set_appearance(self, colors):
        for key, button in self.category_buttons.items():
            button.setIcon(ribbon_icon(key, colors['accent'] if button.isChecked() else colors['muted']))

    def set_compact(self, compact):
        style = Qt.ToolButtonIconOnly if compact else Qt.ToolButtonTextBesideIcon
        for button in self.category_buttons.values():
            button.setToolButtonStyle(style)
