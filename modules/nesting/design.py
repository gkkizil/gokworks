"""Nesting-only logical-pixel metrics, using the application's current palettes."""

from gui_qt.theme import COLORS

PANEL_WIDTH = 240
PROPERTIES_WIDTH = 300
CONTROL_HEIGHT = 30
SPACING = 6


def apply_design(page, appearance):
    c = COLORS[appearance]
    page.setStyleSheet(f'''
        QWidget#nestingWorkspace QToolBar#nestingCommands {{ border:0;
            border-bottom:1px solid {c['border']}; background:transparent; spacing:4px; padding:2px 0 6px; }}
        QWidget#nestingWorkspace QToolBar#nestingCommands QToolButton {{
            padding:4px 7px; min-height:20px; border-radius:4px; }}
        QWidget#nestingWorkspace QFrame[nestingPanel="true"] {{
            background:{c['panel']}; border:1px solid {c['border']}; border-radius:4px; }}
        QWidget#nestingWorkspace QTreeView {{ border:0; border-radius:0; }}
        QWidget#nestingWorkspace QTreeView::item {{ min-height:25px; }}
        QWidget#nestingWorkspace QLineEdit, QWidget#nestingWorkspace QComboBox {{ min-height:20px; }}
        QWidget#nestingWorkspace QStatusBar {{ border-top:1px solid {c['border']}; background:transparent; }}
        QWidget#nestingWorkspace QStatusBar::item {{ border:0; }}
    ''')
    page.title_label.setStyleSheet('font-size:14px;font-weight:600;')
