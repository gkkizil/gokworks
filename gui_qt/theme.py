"""Native Qt palettes and one restrained stylesheet for both appearances."""

from pathlib import Path
from PySide6.QtGui import QColor, QPalette

COLORS = {
    'dark': dict(bg='#242629', panel='#2B2D30', input='#34363A', border='#474B51',
                 text='#ECEEF1', muted='#B5BBC5', accent='#78B5F0', selected='#35475A',
                 danger='#F3A2A0', warning='#E4C38A', sidebar='#292B2E', canvas='#202225'),
    'light': dict(bg='#ECEDEF', panel='#FAFAFB', input='#FFFFFF', border='#CBCFD5',
                  text='#262B32', muted='#59616C', accent='#1769AE', selected='#DFEBF7',
                  danger='#AE3444', warning='#805B16', sidebar='#E6E8EB', canvas='#F5F6F7'),
}

# Shared logical pixel metrics; Qt applies the selected Windows DPI scale.
ROW_HEIGHT = 28
PANEL_RADIUS = 3


def apply_theme(app, appearance):
    c = dict(COLORS[appearance])
    c['chevron'] = (Path(__file__).resolve().parents[1] / 'assets/qt' / f'chevron-{appearance}.png').as_posix()
    palette = QPalette()
    for role, key in ((QPalette.Window, 'bg'), (QPalette.WindowText, 'text'),
                      (QPalette.Base, 'input'), (QPalette.AlternateBase, 'panel'),
                      (QPalette.Text, 'text'), (QPalette.Button, 'panel'),
                      (QPalette.ButtonText, 'text'), (QPalette.Highlight, 'selected'),
                      (QPalette.HighlightedText, 'text'), (QPalette.ToolTipBase, 'panel'),
                      (QPalette.ToolTipText, 'text'), (QPalette.PlaceholderText, 'muted'),
                      (QPalette.Link, 'accent'), (QPalette.LinkVisited, 'accent')):
        palette.setColor(role, QColor(c[key]))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(c['muted']))
    app.setPalette(palette)
    app.setStyleSheet('''
        QWidget { color: %(text)s; font-family: "Segoe UI", "DejaVu Sans"; font-size: 12px; }
        QMainWindow, QDialog { background: %(bg)s; }
        QFrame#sidebar { background: %(sidebar)s; border-right: 1px solid %(border)s; }
        QFrame[card="true"] { background: %(panel)s; border: 1px solid %(border)s; border-radius: 3px; }
        QLabel[role="title"] { font-size: 18px; font-weight: 600; }
        QLabel[role="subtitle"], QLabel[role="muted"] { color: %(muted)s; }
        QLabel[role="subtitle"] { font-size: 12px; }
        QLabel[role="result"] { font-size: 24px; font-weight: 650; color: %(accent)s; }
        QLabel[role="error"] { color: %(danger)s; }
        QLabel[role="section"] { font-size: 12px; font-weight: 650; }
        QLabel[eyebrow="true"] { font-size: 10px; letter-spacing: 1px; padding: 5px 3px 2px 3px; }
        QPushButton, QToolButton { background: %(input)s; border: 1px solid %(border)s;
            border-radius: 4px; padding: 4px 9px; min-height: 18px; }
        QPushButton:hover, QToolButton:hover { background: %(selected)s; border-color: %(accent)s; }
        QPushButton:pressed { background: %(selected)s; }
        QPushButton:focus, QToolButton:focus { border-color: %(accent)s; }
        QPushButton:disabled, QToolButton:disabled { color: %(muted)s; }
        QPushButton[primary="true"] { background: %(accent)s; color: %(sidebar)s; font-weight: 700; border: 0; }
        QPushButton[primary="true"]:hover { border:1px solid %(text)s; padding:3px 8px; }
        QPushButton[primary="true"]:disabled { background:%(input)s; color:%(muted)s; border:1px solid %(border)s; }
        QPushButton[nav="true"] { text-align: left; background: transparent; border: 0;
            border-left: 3px solid transparent; border-radius: 4px; padding: 5px 7px; }
        QPushButton[nav="true"]:hover { background: %(input)s; }
        QPushButton[nav="true"]:checked { background: %(selected)s; color: %(accent)s;
            border-left-color: %(accent)s; font-weight: 600; }
        QPushButton[nav="true"]:focus { border:1px solid %(accent)s; border-left:3px solid %(accent)s; padding:4px 6px; }
        QToolButton[navigationGroup="true"] { background: transparent; border:0; border-radius:0;
            color: %(muted)s; font-size:10px; font-weight:600; padding:5px 2px; text-align:left; }
        QToolButton[disclosure="true"] { background: transparent; border: 0; padding: 3px 2px; min-height: 22px;
            color: %(accent)s; text-align: left; }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: %(input)s;
            border: 1px solid %(border)s; border-radius: 4px; padding: 4px 6px; min-height: 18px; }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: %(accent)s; }
        QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: %(muted)s; }
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
            background:%(panel)s; color:%(muted)s; }
        QComboBox::drop-down { border: 0; width: 22px; }
        QComboBox::down-arrow { image: url("%(chevron)s"); width: 12px; height: 12px; }
        QComboBox QAbstractItemView { background: %(panel)s; selection-background-color: %(selected)s; }
        QCheckBox { spacing: 6px; padding: 2px 0; }
        QCheckBox::indicator { width: 15px; height: 15px; }
        QTableView, QTreeView, QListView, QPlainTextEdit, QTextBrowser { background: %(panel)s;
            alternate-background-color: %(input)s; border: 1px solid %(border)s; border-radius: 2px;
            selection-background-color: %(selected)s; selection-color: %(text)s; }
        QHeaderView::section { background: %(input)s; border: 0; border-bottom: 1px solid %(border)s;
            color: %(muted)s; padding: 5px 6px; text-align: left; font-weight: 600; }
        QAbstractItemView::item { padding: 3px; }
        QAbstractItemView::item:selected { background: %(selected)s; }
        QTabWidget::pane { border: 0; }
        QTabBar::tab { background: transparent; color: %(muted)s; padding: 6px 10px;
            border-bottom: 2px solid transparent; }
        QTabBar::tab:selected { color: %(accent)s; border-bottom: 2px solid %(accent)s; }
        QTabBar::tab:hover { background:%(selected)s; color:%(text)s; }
        QScrollArea { border: 0; background: transparent; }
        QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
        QScrollBar::handle:vertical { background: %(border)s; min-height: 26px; border-radius: 4px; }
        QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
        QScrollBar::handle:horizontal { background: %(border)s; min-width: 26px; border-radius: 4px; }
        QScrollBar::handle:hover { background:%(muted)s; }
        QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
        QProgressBar { border: 0; background: %(input)s; border-radius: 3px; height: 6px; }
        QProgressBar::chunk { background: %(accent)s; border-radius: 3px; }
        QSplitter::handle { background: %(bg)s; width: 5px; height: 5px; }
        QSplitter::handle:hover { background: %(border)s; }
        QStatusBar { background: %(sidebar)s; border-top: 1px solid %(border)s; }
        QStatusBar QLabel { font-size:11px; }
        QStatusBar QPushButton { border:0; background:transparent; font-size:11px; padding:2px 6px; }
        QToolBar { background: %(panel)s; border:0; spacing:4px; padding:3px; }
        QToolBar#applicationTools { border-bottom:1px solid %(border)s; padding:6px 10px; spacing:6px; }
        QToolBar#moduleCommands { background:transparent; padding:0; }
        QToolBar::separator { background:%(border)s; width:1px; margin:3px 5px; }
        QToolBar QComboBox { min-height:18px; font-weight:600; }
        QDockWidget { color:%(text)s; font-size:11px; }
        QDockWidget::title { background:%(sidebar)s; padding:7px; border-bottom:1px solid %(border)s; }
        QDockWidget QWidget#inspectorBody { background:%(panel)s; }
        QFrame[inspectorSection="true"] { border:0; border-bottom:1px solid %(border)s; border-radius:0; }
        QToolButton[inspectorGroup="true"] { color:%(muted)s; font-size:10px; font-weight:600; }
        QMenu { background: %(panel)s; border: 1px solid %(border)s; }
        QMenu::item { padding: 6px 12px; }
        QMenu::item:selected { background: %(selected)s; }
    ''' % c)
