"""Grouped, symbol-led characteristic picker for the GD&T page (Qt only).

Symbols come from ``diagram.symbol`` drawn on a small ``VectorScene``; no
second set of symbol drawings exists. Group titles and order are display
choices only: ``catalog.GROUPS`` and every characteristic stay unchanged.
"""

from PySide6.QtCore import Qt, QRectF, QSize, QModelIndex
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTreeView

from gui_qt.diagrams import VectorScene, TEXT, MUTED, ACCENT
from gui_qt.models import Column, TreeModel
from gui_qt.theme import ROW_HEIGHT
from modules.geometric_tolerances.catalog import CATALOG
from modules.geometric_tolerances.diagram import symbol

LEGACY_GROUP = 'Eski işaretler'
# (catalog group, shown title) in the order the picker lists them.
GROUP_TITLES = (('Şekil', 'Şekil'), ('Yön', 'Yönelim'), ('Konum', 'Konum'), ('Salgı', 'Salgı'),
                ('Profil', 'Profil'), (LEGACY_GROUP, 'Kaldırılmış semboller (ASME 2018)'))
ICON = 22


def symbol_icon(key, appearance, size=ICON, ratio=2):
    """The ASME symbol of ``key`` from diagram.symbol, as a crisp transparent icon."""
    dark = appearance == 'Dark'
    scene = VectorScene(size, size)
    symbol(scene, key, size / 2, size / 2, size * .64, TEXT[dark], 1.6)
    pixmap = QPixmap(size * ratio, size * ratio)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    scene.render(painter, QRectF(0, 0, size, size), QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)


class CatalogModel(TreeModel):
    def __init__(self, parent=None):
        super().__init__((Column('Tolerans türü', 'name'),), parent)
        self.icons = {}
        rows = [dict(id=group, parent='', name=title, group=True) for group, title in GROUP_TITLES]
        rows += [dict(id=item.key, parent=item.group, name=item.name.replace(' (eski)', ''), english=item.english,
                      key=item.key, example=item.example, active=item.active)
                 for group, _ in GROUP_TITLES for item in CATALOG if item.group == group]
        self.replace(rows)

    def set_appearance(self, appearance):
        self.icons = {item.key: symbol_icon(item.key, appearance) for item in CATALOG}
        if self.root.children:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.root.children) - 1, 0))
            for row, group in enumerate(self.root.children):
                parent = self.index(row, 0)
                if group.children:
                    self.dataChanged.emit(self.index(0, 0, parent), self.index(len(group.children) - 1, 0, parent))

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role == Qt.DecorationRole:
            return self.icons.get(index.internalPointer().values.get('key'))
        if index.isValid() and role == Qt.ToolTipRole:
            row = index.internalPointer().values
            return None if row.get('group') else f'{row["name"]} · {row["english"]}\nÖrnek: {row["example"]}'
        return super().data(index, role)

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        if index.internalPointer().values.get('group'):
            return Qt.ItemIsEnabled              # group headings open/close, they are not a choice
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def index_of(self, key):
        node = self.nodes.get(str(key))
        return self.createIndex(node.row, 0, node) if node is not None else QModelIndex()


class CatalogDelegate(QStyledItemDelegate):
    """Symbol, Turkish name, then the English name in a smaller muted face; a bar marks the choice."""

    def __init__(self, view):
        super().__init__(view)
        self.appearance = 'Dark'

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), max(hint.height(), ROW_HEIGHT + 6))

    def paint(self, painter, option, index):
        row = index.data(Qt.UserRole) or {}
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ''
        style = opt.widget.style() if opt.widget else None
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)
        dark = self.appearance == 'Dark'
        rect = style.subElementRect(QStyle.SE_ItemViewItemText, opt, opt.widget).adjusted(4, 0, -2, 0)
        painter.save()
        selected = bool(option.state & QStyle.State_Selected)
        if selected:
            painter.fillRect(QRectF(option.rect.left(), option.rect.top() + 2, 3, option.rect.height() - 4), QColor(ACCENT[dark]))
        font = QFont(opt.font)
        if row.get('group') or selected:
            font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QPen(QColor(TEXT[dark] if row.get('active', True) else MUTED[dark])))
        metrics = painter.fontMetrics()
        name = metrics.elidedText(text, Qt.ElideRight, rect.width())
        painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, name)
        english = row.get('english')
        if english:
            left = rect.left() + metrics.horizontalAdvance(name) + 8
            small = QFont(opt.font)
            small.setPointSizeF(max(7., opt.font.pointSizeF() * .85))
            painter.setFont(small)
            painter.setPen(QPen(QColor(MUTED[dark])))
            room = QRectF(left, rect.top(), max(0, rect.right() - left), rect.height())
            painter.drawText(room, Qt.AlignVCenter | Qt.AlignLeft,
                             painter.fontMetrics().elidedText(english, Qt.ElideRight, int(room.width())))
        painter.restore()


class CatalogView(QTreeView):
    def __init__(self):
        super().__init__()
        from gui_qt.components import configure_view
        configure_view(self)
        self.setSortingEnabled(False)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(True)
        self.setIconSize(QSize(ICON, ICON))
        self.setSelectionMode(QTreeView.SingleSelection)
        self.setAccessibleName('Tolerans türü')
        self.delegate = CatalogDelegate(self)
        self.setItemDelegate(self.delegate)
