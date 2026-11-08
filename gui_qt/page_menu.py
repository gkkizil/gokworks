"""Classic drop-down menu bar for a workbench page (Dosya · … · Görünüm).

The menus only reach commands and settings the page already has: an item calls
the same method as its button, and a check item mirrors the same checkbox (both
directions). Nothing is stored twice.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMenuBar


class PageMenuBar(QMenuBar):
    def __init__(self, page):
        super().__init__(page)
        self.setObjectName('pageMenuBar'); self.setNativeMenuBar(False)
        self.setAccessibleName(page.title_label.text() + ' menüsü')
        self.page = page
        self.items = {}          # 'Menü/Komut' -> QAction, for tests and keyboard users
        layout = page.layout
        layout.insertWidget(layout.indexOf(page.header_rule) + 1, self)

    def command(self, menu, title, callback, *, shortcut=None, tip='', key=None):
        action = QAction(title, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut)); action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            self.page.addAction(action)
        if tip:
            action.setStatusTip(tip); action.setToolTip(tip)
        action.triggered.connect(lambda checked=False: callback())
        menu.addAction(action)
        self.items[key or f"{menu.title().replace('&', '')}/{title}"] = action
        return action

    def check(self, menu, title, box, *, tip='', key=None):
        """A check item that mirrors an existing QCheckBox / checkable button."""
        action = QAction(title, self); action.setCheckable(True); action.setChecked(box.isChecked())
        if tip:
            action.setStatusTip(tip)
        action.toggled.connect(lambda on: box.isChecked() != on and box.setChecked(on))
        box.toggled.connect(lambda on: action.isChecked() != on and action.setChecked(on))
        menu.addAction(action)
        self.items[key or f"{menu.title().replace('&', '')}/{title}"] = action
        return action

    def choice(self, menu, combo, *, key=None):
        """Radio items for every entry of an existing QComboBox."""
        group = QActionGroup(self); group.setExclusive(True); actions = []
        for index in range(combo.count()):
            action = QAction(combo.itemText(index), self); action.setCheckable(True)
            action.setChecked(index == combo.currentIndex())
            action.triggered.connect(lambda checked=False, i=index: combo.setCurrentIndex(i))
            group.addAction(action); menu.addAction(action); actions.append(action)
            self.items[(key or menu.title().replace('&', '')) + '/' + combo.itemText(index)] = action
        combo.currentIndexChanged.connect(lambda i: 0 <= i < len(actions) and actions[i].setChecked(True))
        return actions

    def sync_enabled(self, pairs):
        """Disable menu items together with their buttons (busy state, invalid input)."""
        for action, widget in pairs:
            action.setEnabled(widget.isEnabled())
