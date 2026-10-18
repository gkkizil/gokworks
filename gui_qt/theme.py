"""Native Qt palettes and one restrained stylesheet for both appearances."""

from PySide6.QtGui import QColor, QPalette

COLORS = {
    'dark': dict(bg='#141923', panel='#1C2431', input='#222D3D', border='#344155',
                 text='#E8EEF7', muted='#A5B3C8', accent='#80B6F5', selected='#263E5B',
                 danger='#F0A5B1', warning='#E6C18A', sidebar='#101620'),
    'light': dict(bg='#EFF4FA', panel='#FFFFFF', input='#F5F8FC', border='#D7E0EC',
                  text='#20344F', muted='#5D718D', accent='#2466B2', selected='#E0EDFC',
                  danger='#B23D53', warning='#8D631F', sidebar='#F8FAFD'),
}


def apply_theme(app, appearance):
    c = COLORS[appearance]
    palette = QPalette()
    for role, key in ((QPalette.Window, 'bg'), (QPalette.WindowText, 'text'),
                      (QPalette.Base, 'input'), (QPalette.AlternateBase, 'panel'),
                      (QPalette.Text, 'text'), (QPalette.Button, 'panel'),
                      (QPalette.ButtonText, 'text'), (QPalette.Highlight, 'selected'),
                      (QPalette.HighlightedText, 'text'), (QPalette.ToolTipBase, 'panel'),
                      (QPalette.ToolTipText, 'text'), (QPalette.PlaceholderText, 'muted')):
        palette.setColor(role, QColor(c[key]))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(c['muted']))
    app.setPalette(palette)
    app.setStyleSheet('''
        QWidget { color: %(text)s; font-family: "Segoe UI", "DejaVu Sans"; font-size: 13px; }
        QMainWindow, QDialog { background: %(bg)s; }
        QFrame#sidebar { background: %(sidebar)s; border-right: 1px solid %(border)s; }
        QFrame[card="true"] { background: %(panel)s; border: 1px solid %(border)s; border-radius: 12px; }
        QLabel[role="title"] { font-size: 25px; font-weight: 650; }
        QLabel[role="subtitle"], QLabel[role="muted"] { color: %(muted)s; }
        QLabel[role="result"] { font-size: 29px; font-weight: 700; color: %(accent)s; }
        QLabel[role="error"] { color: %(danger)s; }
        QLabel[role="section"] { font-size: 15px; font-weight: 650; }
        QPushButton, QToolButton { background: %(input)s; border: 1px solid %(border)s;
            border-radius: 7px; padding: 8px 13px; min-height: 18px; }
        QPushButton:hover, QToolButton:hover { background: %(selected)s; border-color: %(accent)s; }
        QPushButton:pressed { background: %(selected)s; }
        QPushButton:disabled { color: %(muted)s; }
        QPushButton[primary="true"] { background: %(accent)s; color: %(sidebar)s; font-weight: 700; border: 0; }
        QPushButton[nav="true"] { text-align: left; background: transparent; border: 0; padding: 11px 12px; }
        QPushButton[nav="true"]:checked { background: %(selected)s; color: %(accent)s; font-weight: 650; }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: %(input)s;
            border: 1px solid %(border)s; border-radius: 6px; padding: 7px; min-height: 20px; }
        QLineEdit:focus, QComboBox:focus { border-color: %(accent)s; }
        QComboBox::drop-down { border: 0; width: 22px; }
        QComboBox QAbstractItemView { background: %(panel)s; selection-background-color: %(selected)s; }
        QCheckBox { spacing: 8px; padding: 5px 0; }
        QCheckBox::indicator { width: 17px; height: 17px; }
        QTableView, QTreeView, QListView, QPlainTextEdit, QTextBrowser { background: %(panel)s;
            alternate-background-color: %(input)s; border: 1px solid %(border)s; border-radius: 7px;
            selection-background-color: %(selected)s; selection-color: %(text)s; }
        QHeaderView::section { background: %(input)s; border: 0; border-bottom: 1px solid %(border)s;
            color: %(muted)s; padding: 10px; text-align: left; font-weight: 600; }
        QAbstractItemView::item { padding: 5px; }
        QAbstractItemView::item:selected { background: %(selected)s; }
        QTabWidget::pane { border: 0; }
        QTabBar::tab { background: transparent; color: %(muted)s; padding: 10px 17px;
            border-bottom: 2px solid transparent; }
        QTabBar::tab:selected { color: %(accent)s; border-bottom: 2px solid %(accent)s; }
        QScrollArea { border: 0; background: transparent; }
        QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
        QScrollBar::handle:vertical { background: %(border)s; min-height: 26px; border-radius: 4px; }
        QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
        QProgressBar { border: 0; background: %(input)s; border-radius: 3px; height: 6px; }
        QProgressBar::chunk { background: %(accent)s; border-radius: 3px; }
        QSplitter::handle { background: %(bg)s; width: 8px; height: 8px; }
        QStatusBar { background: %(sidebar)s; border-top: 1px solid %(border)s; }
        QMenu { background: %(panel)s; border: 1px solid %(border)s; }
        QMenu::item:selected { background: %(selected)s; }
    ''' % c)
