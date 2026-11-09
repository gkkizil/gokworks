"""GOKWORKS design system: colour tokens, type/spacing scale and one stylesheet.

Every page reads colours from ``COLORS[appearance]``; no module defines its own
palette. Keys are stable public API (modules and tests use them). See
docs/UI_DESIGN_SYSTEM.md for the rules behind each token.
"""

from pathlib import Path
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QProxyStyle, QStyle

# Neutral graphite surfaces, one controlled blue accent, semantic states only
# where they carry meaning. ``bg`` is the workspace, ``panel`` a pane/table,
# ``input`` an editable field, ``canvas`` a drawing/preview surface.
COLORS = {
    'dark': dict(bg='#1E1F22', sidebar='#18191B', panel='#25262A', input='#2C2E33',
                 border='#3A3C42', border_strong='#4C4F57', hover='#30333A',
                 text='#E3E5E8', muted='#9DA2AB', accent='#4C9DFF', on_accent='#0B1626',
                 selected='#233A5C', focus='#4C9DFF',
                 danger='#F07A7A', warning='#E2B04A', success='#56C08D',
                 canvas='#1A1B1E', grid='#2A2C31'),
    'light': dict(bg='#EDEEF0', sidebar='#E4E6E9', panel='#FFFFFF', input='#FFFFFF',
                  border='#CDD1D6', border_strong='#AEB4BC', hover='#E6E9ED',
                  text='#1F2328', muted='#5B636E', accent='#1767C6', on_accent='#FFFFFF',
                  selected='#D8E5F7', focus='#1767C6',
                  danger='#B8323E', warning='#8A5D00', success='#1E7A4C',
                  canvas='#F7F8F9', grid='#E3E6EA'),
}

# Type scale (logical px; Windows applies 100/125/150 % scaling). Segoe UI on
# Windows; Inter/DejaVu keep metrics close on the Linux test runner.
FONT_FAMILY = '"Segoe UI", "DejaVu Sans"'
FONT_SIZES = dict(caption=11, body=12, section=12, title=15, result=20)

# Spacing scale and shared metrics. Layout code should use these values
# instead of new literals: 2, 4, 6, 8, 12, 16.
SPACING = dict(xxs=2, xs=4, s=6, m=8, l=12, xl=16)
ROW_HEIGHT = 26
CONTROL_RADIUS = 3
PANEL_RADIUS = 2


def palette_colors(appearance):
    """Resolved tokens plus theme asset paths for the stylesheet."""
    c = dict(COLORS[appearance])
    assets = Path(__file__).resolve().parents[1] / 'assets/qt'
    c['chevron'] = (assets / f'chevron-{appearance}.png').as_posix()
    c['chevron_up'] = (assets / f'chevron-up-{appearance}.png').as_posix()
    c.update(font=FONT_FAMILY, radius=CONTROL_RADIUS, panel_radius=PANEL_RADIUS,
             **{f'size_{k}': v for k, v in FONT_SIZES.items()})
    return c


STYLESHEET = '''
/* ---- Base ------------------------------------------------------------- */
QWidget { color: %(text)s; font-family: %(font)s; font-size: %(size_body)spx; }
QMainWindow, QDialog { background: %(bg)s; }
QToolTip { background: %(panel)s; color: %(text)s; border: 1px solid %(border_strong)s; padding: 4px 6px; }

/* ---- Text roles ------------------------------------------------------- */
QLabel[role="title"] { font-size: %(size_title)spx; font-weight: 600; }
QLabel[role="subtitle"], QLabel[role="muted"] { color: %(muted)s; }
QLabel[role="subtitle"] { font-size: %(size_caption)spx; }
QLabel[role="result"] { font-size: %(size_result)spx; font-weight: 600; color: %(text)s; }
QLabel[role="error"] { color: %(danger)s; }
QLabel[role="warning"] { color: %(warning)s; }
QLabel[role="success"] { color: %(success)s; }
QLabel[role="section"] { font-size: %(size_section)spx; font-weight: 600; }
QLabel[eyebrow="true"] { font-size: 10px; letter-spacing: 1px; color: %(muted)s; padding: 4px 2px 2px 2px; }
QFrame[separator="true"] { background: %(border)s; border: 0; max-height: 1px; min-height: 1px; }

/* ---- Panes (flat, separated by 1 px rules, no shadows) ----------------- */
QFrame#sidebar { background: %(sidebar)s; border: 0; border-right: 1px solid %(border)s; }
QFrame[card="true"] { background: %(panel)s; border: 1px solid %(border)s; border-radius: %(panel_radius)spx; }

/* ---- Buttons: secondary (default), primary, destructive, flat ---------- */
QPushButton, QToolButton { background: %(input)s; border: 1px solid %(border)s;
    border-radius: %(radius)spx; padding: 3px 10px; min-height: 18px; }
QPushButton:hover, QToolButton:hover { background: %(hover)s; border-color: %(border_strong)s; }
QPushButton:pressed, QToolButton:pressed, QToolButton:checked { background: %(selected)s; }
QPushButton:focus, QToolButton:focus { border-color: %(focus)s; }
QPushButton:disabled, QToolButton:disabled { color: %(muted)s; background: %(panel)s; border-color: %(border)s; }
QPushButton::menu-indicator { image: url("%(chevron)s"); width: 9px; height: 9px;
    subcontrol-origin: padding; subcontrol-position: right center; right: -4px; }
QPushButton[primary="true"] { background: %(accent)s; color: %(on_accent)s; font-weight: 600;
    border: 1px solid %(accent)s; }
QPushButton[primary="true"]:hover { border-color: %(text)s; }
QPushButton[primary="true"]:disabled { background: %(input)s; color: %(muted)s; border-color: %(border)s; }
QPushButton[toggle="true"] { color: %(muted)s; padding: 3px 12px 3px 8px; }
QPushButton[toggle="true"]:hover { color: %(text)s; }
QPushButton[toggle="true"]:checked { background: %(selected)s; color: %(text)s; border: 1px solid %(accent)s; }
QPushButton[toggle="true"]:checked:hover { border-color: %(text)s; }
QPushButton[destructive="true"] { color: %(danger)s; }
QPushButton[destructive="true"]:hover { border-color: %(danger)s; }
QPushButton[destructive="true"]:disabled { color: %(muted)s; border-color: %(border)s; }
QPushButton[flat="true"] { background: transparent; border: 1px solid transparent; color: %(muted)s; padding: 3px 6px; }
QPushButton[flat="true"]:hover { background: %(hover)s; color: %(text)s; }
QPushButton[flat="true"]:focus { border-color: %(focus)s; }
QPushButton[flat="true"]:checked { background: %(selected)s; color: %(text)s; }
QToolButton[popupMode="1"], QToolButton[popupMode="2"] { padding-right: 16px; }
QToolButton::menu-indicator { image: url("%(chevron)s"); width: 9px; height: 9px;
    subcontrol-origin: padding; subcontrol-position: right center; right: 4px; }
QToolButton::menu-button { border: 0; width: 14px; }

/* ---- Sidebar navigation ----------------------------------------------- */
QPushButton[nav="true"] { text-align: left; background: transparent; border: 0;
    border-left: 2px solid transparent; border-radius: 0; padding: 4px 8px; color: %(text)s; }
QPushButton[nav="true"]:hover { background: %(hover)s; }
QPushButton[nav="true"]:checked { background: %(selected)s; color: %(text)s;
    border-left-color: %(accent)s; font-weight: 600; }
QPushButton[nav="true"]:focus { border: 1px solid %(focus)s; border-left: 2px solid %(accent)s; padding: 3px 7px; }
QToolButton[navigationGroup="true"] { background: transparent; border: 0; border-radius: 0;
    color: %(muted)s; font-size: 10px; font-weight: 600; letter-spacing: 1px; padding: 8px 2px 3px 2px; text-align: left; }
QToolButton[navigationGroup="true"]:hover { color: %(text)s; }
QToolButton[ribbonTab="true"] { background: transparent; border: 0; border-bottom: 2px solid transparent;
    border-radius: 0; padding: 5px 10px; color: %(muted)s; font-weight: 600; }
QToolButton[ribbonTab="true"]:hover { color: %(text)s; background: %(hover)s; }
QToolButton[ribbonTab="true"]:checked { color: %(text)s; background: transparent; border-bottom-color: %(accent)s; }
QToolButton[ribbonCommand="true"] { background: transparent; border: 1px solid transparent; border-radius: 3px;
    padding: 3px 10px; color: %(text)s; }
QToolButton[ribbonCommand="true"]:hover { background: %(hover)s; border-color: %(border)s; }
QToolButton[ribbonCommand="true"]:checked { background: %(selected)s; border-color: %(accent)s; }
QWidget#shaftRibbon { background: %(panel)s; border-bottom: 1px solid %(border)s; }
QWidget#shaftEditor { background: %(bg)s; }
QWidget#shaftEditor QStackedWidget > QWidget { background: %(bg)s; }
QWidget#dxfRibbon { background: %(panel)s; border-bottom: 1px solid %(border)s; }
QToolButton[disclosure="true"] { background: transparent; border: 0; padding: 3px 0; min-height: 20px;
    color: %(accent)s; text-align: left; }
QToolButton[disclosure="true"]:hover { color: %(text)s; }
QToolButton#sidebarToggle { background: transparent; border: 1px solid transparent; color: %(muted)s; padding: 0; }
QToolButton#sidebarToggle:hover { background: %(hover)s; color: %(text)s; }

/* ---- Inputs ----------------------------------------------------------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit { background: %(input)s;
    border: 1px solid %(border)s; border-radius: %(radius)spx; padding: 3px 6px; min-height: 18px;
    selection-background-color: %(selected)s; selection-color: %(text)s; }
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: %(border_strong)s; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: %(focus)s; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background: %(panel)s; color: %(muted)s; }
QLineEdit:read-only { background: %(panel)s; }
QLineEdit[invalid="true"], QSpinBox[invalid="true"], QDoubleSpinBox[invalid="true"] { border-color: %(danger)s; }
QComboBox::drop-down { border: 0; width: 20px; }
QComboBox::down-arrow { image: url("%(chevron)s"); width: 10px; height: 10px; }
QComboBox QAbstractItemView { background: %(panel)s; border: 1px solid %(border_strong)s;
    selection-background-color: %(selected)s; selection-color: %(text)s; outline: 0; }
QSpinBox, QDoubleSpinBox { padding-right: 18px; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right;
    width: 16px; border: 0; border-left: 1px solid %(border)s; border-top-right-radius: %(radius)spx; background: transparent; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right;
    width: 16px; border: 0; border-left: 1px solid %(border)s; border-bottom-right-radius: %(radius)spx; background: transparent; }
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover { background: %(hover)s; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url("%(chevron_up)s"); width: 8px; height: 8px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url("%(chevron)s"); width: 8px; height: 8px; }
QCheckBox, QRadioButton { spacing: 6px; padding: 2px 0; }
QCheckBox::indicator, QRadioButton::indicator { width: 14px; height: 14px; }

/* ---- Data views: compact rows, hairline rules, quiet headers ----------- */
QTableView, QTreeView, QListView, QTableWidget, QListWidget { background: %(panel)s;
    alternate-background-color: %(bg)s; border: 1px solid %(border)s; border-radius: 0;
    gridline-color: %(border)s; selection-background-color: %(selected)s; selection-color: %(text)s; outline: 0; }
QPlainTextEdit, QTextBrowser, QTextEdit { background: %(panel)s; border: 1px solid %(border)s; border-radius: 0;
    selection-background-color: %(selected)s; selection-color: %(text)s; }
QHeaderView { background: %(panel)s; border: 0; }
QHeaderView::section { background: %(panel)s; border: 0; border-bottom: 1px solid %(border_strong)s;
    border-right: 1px solid %(border)s; color: %(muted)s; padding: 4px 6px; font-weight: 600; }
QHeaderView::section:last { border-right: 0; }
QHeaderView::section:hover { color: %(text)s; }
QTableCornerButton::section { background: %(panel)s; border: 0; }
QAbstractItemView::item { padding: 2px 4px; }
QAbstractItemView::item:hover { background: %(hover)s; }
QAbstractItemView::item:selected { background: %(selected)s; color: %(text)s; }

/* ---- Tabs ------------------------------------------------------------- */
QTabWidget::pane { border: 0; border-top: 1px solid %(border)s; top: -1px; }
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab { background: transparent; color: %(muted)s; padding: 5px 12px; border: 0;
    border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: %(text)s; border-bottom: 2px solid %(accent)s; }
QTabBar::tab:hover:!selected { color: %(text)s; background: %(hover)s; }

/* ---- Scroll, split, progress ----------------------------------------- */
QScrollArea { border: 0; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: %(border_strong)s; min-height: 28px; border-radius: 3px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: %(border_strong)s; min-width: 28px; border-radius: 3px; margin: 2px; }
QScrollBar::handle:hover { background: %(muted)s; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { height: 0; width: 0; background: none; }
QProgressBar { border: 0; background: %(input)s; border-radius: 2px; max-height: 6px; }
QProgressBar::chunk { background: %(accent)s; border-radius: 2px; }
QSplitter::handle { background: %(bg)s; }
QSplitter::handle:horizontal { width: 5px; }
QSplitter::handle:vertical { height: 5px; }
QSplitter::handle:hover { background: %(accent)s; }

/* ---- Shell: status bar, toolbars, docks, menus ------------------------ */
QStatusBar { background: %(sidebar)s; border-top: 1px solid %(border)s; min-height: 24px; }
QStatusBar::item { border: 0; }
QStatusBar QLabel { font-size: %(size_caption)spx; color: %(muted)s; padding: 0 4px; }
QStatusBar QLabel[role="error"] { color: %(danger)s; }
QStatusBar QLabel[role="warning"] { color: %(warning)s; }
QStatusBar QLabel[role="success"] { color: %(success)s; }
QStatusBar QPushButton { border: 0; background: transparent; font-size: %(size_caption)spx; padding: 2px 8px; color: %(muted)s; }
QStatusBar QPushButton:hover { background: %(hover)s; color: %(text)s; }
QLabel#connectionIndicator { font-size: 10px; padding: 0 0 0 6px; }
QLabel#connectionIndicator[state="unknown"] { color: %(muted)s; }
QLabel#connectionIndicator[state="connected"] { color: %(success)s; }
QLabel#connectionIndicator[state="offline"] { color: %(danger)s; }
QToolBar { background: %(panel)s; border: 0; spacing: 4px; padding: 3px; }
QToolBar#applicationTools { border-bottom: 1px solid %(border)s; padding: 6px 10px; spacing: 6px; }
QToolBar#moduleCommands { background: transparent; padding: 0; }
QToolBar::separator { background: %(border)s; width: 1px; margin: 3px 5px; }
QToolBar QComboBox { min-height: 18px; font-weight: 600; }
QDockWidget { color: %(muted)s; font-size: %(size_caption)spx; }
QDockWidget::title { background: %(sidebar)s; padding: 6px 8px; border-bottom: 1px solid %(border)s; }
QDockWidget QWidget#inspectorBody { background: %(panel)s; }
QFrame[inspectorSection="true"] { border: 0; border-bottom: 1px solid %(border)s; border-radius: 0; }
QToolButton[inspectorGroup="true"] { color: %(muted)s; font-size: 10px; font-weight: 600; }
QMenuBar#pageMenuBar { background: transparent; border: 0; padding: 0; spacing: 2px; }
QMenuBar#pageMenuBar::item { background: transparent; padding: 4px 10px; border-radius: 3px; color: %(text)s; }
QMenuBar#pageMenuBar::item:selected { background: %(hover)s; }
QMenuBar#pageMenuBar::item:pressed { background: %(selected)s; color: %(text)s; }
QMenu { background: %(panel)s; border: 1px solid %(border_strong)s; padding: 3px 0; }
QMenu::item { padding: 5px 20px 5px 12px; }
QMenu::item:selected { background: %(selected)s; }
QMenu::item:disabled { color: %(muted)s; }
QMenu::separator { height: 1px; background: %(border)s; margin: 3px 0; }
QDialogButtonBox QPushButton { min-width: 72px; }
QGroupBox { border: 1px solid %(border)s; border-radius: %(panel_radius)spx; margin-top: 14px; padding-top: 6px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: %(muted)s; font-weight: 600; }
'''


class GokworksStyle(QProxyStyle):
    """Fusion with quieter standard icons; everything else stays native Fusion."""

    _clear_icon = None

    def standardIcon(self, standard, option=None, widget=None):
        if standard == QStyle.SP_LineEditClearButton:
            if GokworksStyle._clear_icon is None:
                GokworksStyle._clear_icon = _cross_icon()
            return GokworksStyle._clear_icon
        return super().standardIcon(standard, option, widget)


def _cross_icon():
    icon = QIcon()
    for size in (16, 24, 32):
        pixmap = QPixmap(size, size); pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor('#8A9099'), size / 10); pen.setCapStyle(Qt.RoundCap); painter.setPen(pen)
        a, b = size * .32, size * .68
        painter.drawLine(QPointF(a, a), QPointF(b, b)); painter.drawLine(QPointF(b, a), QPointF(a, b))
        painter.end(); icon.addPixmap(pixmap)
    return icon


def apply_theme(app, appearance):
    c = palette_colors(appearance)
    palette = QPalette()
    for role, key in ((QPalette.Window, 'bg'), (QPalette.WindowText, 'text'),
                      (QPalette.Base, 'input'), (QPalette.AlternateBase, 'bg'),
                      (QPalette.Text, 'text'), (QPalette.Button, 'input'),
                      (QPalette.ButtonText, 'text'), (QPalette.Highlight, 'selected'),
                      (QPalette.HighlightedText, 'text'), (QPalette.ToolTipBase, 'panel'),
                      (QPalette.ToolTipText, 'text'), (QPalette.PlaceholderText, 'muted'),
                      (QPalette.Link, 'accent'), (QPalette.LinkVisited, 'accent'),
                      (QPalette.Mid, 'border'), (QPalette.Dark, 'border_strong'), (QPalette.Light, 'panel')):
        palette.setColor(role, QColor(c[key]))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor(c['muted']))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET % c)
