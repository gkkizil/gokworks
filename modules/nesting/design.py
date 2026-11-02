"""Nesting-only metrics and scoped rules, built from the shared theme tokens.

Colours, radii and font sizes come from ``gui_qt.theme``; this module only
adds the workstation layout: a flat command/menu bar, flush panes separated by
splitter gaps and hairlines, a compact results strip and plate tabs.
"""

from gui_qt.theme import COLORS, FONT_SIZES, CONTROL_RADIUS

PANEL_WIDTH = 260
PROPERTIES_WIDTH = 300
CONTROL_HEIGHT = 24
SPACING = 4


def apply_design(page, appearance):
    c = dict(COLORS[appearance]); c.update(radius=CONTROL_RADIUS, caption=FONT_SIZES['caption'])
    page.setStyleSheet('''
        QWidget#nestingWorkspace QToolBar#nestingCommands { background: transparent; border: 0;
            border-bottom: 1px solid %(border)s; spacing: 0; padding: 0 0 4px 0; }
        QWidget#nestingWorkspace QToolButton[nestingMenu="true"] { background: transparent;
            border: 1px solid transparent; border-radius: %(radius)spx; padding: 3px 9px; min-height: 18px; }
        QWidget#nestingWorkspace QToolButton[nestingMenu="true"]:hover { background: %(hover)s; }
        QWidget#nestingWorkspace QToolButton[nestingMenu="true"]:pressed,
        QWidget#nestingWorkspace QToolButton[nestingMenu="true"]:open { background: %(selected)s; }
        QWidget#nestingWorkspace QToolButton[nestingMenu="true"]:focus { border-color: %(focus)s; }
        QWidget#nestingWorkspace QToolButton[nestingMenu="true"]::menu-indicator { image: none; width: 0; }
        QWidget#nestingWorkspace QToolButton[nestingMenu="true"]:disabled { background: transparent; }
        QWidget#nestingWorkspace QFrame[nestingPane="true"] { background: %(panel)s; border: 0; }
        QWidget#nestingWorkspace QFrame[nestingPane="true"] QTreeView,
        QWidget#nestingWorkspace QFrame[nestingPane="true"] QTableView { border: 0; border-top: 1px solid %(border)s; }
        QWidget#nestingWorkspace QFrame[nestingPane="true"] QTabWidget::pane { border: 0; border-top: 1px solid %(border)s; }
        QWidget#nestingWorkspace QFrame[nestingPane="true"] QLineEdit { min-height: 16px; }
        QWidget#nestingWorkspace QFrame[nestingPane="true"] QPushButton { padding: 2px 8px; }
        QWidget#nestingWorkspace QFrame[nestingPane="true"] QPushButton[flat="true"] { padding: 2px 6px; }
        QWidget#nestingWorkspace QFrame[nestingPane="true"] QToolButton { padding: 2px 4px; }
        QWidget#nestingWorkspace QWidget#nestingResults { background: %(panel)s; border-top: 1px solid %(border)s; }
        QWidget#nestingWorkspace QWidget#nestingResults QLabel[role="section"] { font-weight: 600; }
        QWidget#nestingWorkspace QGraphicsView { border: 0; border-top: 1px solid %(border)s; }
        QWidget#nestingWorkspace QTreeView::item { min-height: 22px; }
        QWidget#nestingWorkspace QStatusBar { background: transparent; border: 0; min-height: 20px; }
        QWidget#nestingWorkspace QStatusBar::item { border: 0; }
    ''' % c)
    page.title_label.setStyleSheet('')


def plate_tabs_style(appearance):
    """Underlined plate tabs, identical to the shared QTabBar rule but denser."""
    c = COLORS[appearance]
    return f'''
        QTabBar#nestingPlates::tab {{ background: transparent; color: {c['muted']}; border: 0;
            border-bottom: 2px solid transparent; margin-right: 2px; padding: 4px 10px; }}
        QTabBar#nestingPlates::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
        QTabBar#nestingPlates::tab:hover:!selected {{ color: {c['text']}; background: {c['hover']}; }}
        QTabBar#nestingPlates::tab:disabled {{ color: {c['muted']}; }}
    '''
