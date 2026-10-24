"""Virtualized Qt tables/trees; no per-row widgets and no CAD/COM objects."""

from dataclasses import dataclass, field
from decimal import Decimal
from PySide6.QtCore import (QAbstractTableModel, QAbstractItemModel, QModelIndex,
                           QSortFilterProxyModel, Qt, Signal, QLocale, QCollator)
from PySide6.QtGui import QColor, QBrush


def search_text(value):
    return str(value).casefold().replace('\u0307', '')


LABELS = {'pending': 'Bekliyor', 'running': 'İşleniyor', 'success': 'Başarılı',
          'partial': 'Kısmen tamamlandı', 'skipped': 'Atlandı', 'error': 'Hata'}


@dataclass(frozen=True)
class Column:
    title: str
    key: str
    format: object = None


class TableModel(QAbstractTableModel):
    edited = Signal(int, str, object)

    def __init__(self, columns, rows=(), parent=None, *, editable=()):
        super().__init__(parent)
        self.columns = tuple(columns)
        self.rows = list(rows)
        self.search_cache = [search_text(' '.join(map(str, row.values()))) for row in self.rows]
        self.editable = set(editable)
        self.positions = {str(row.get('source', i)): i for i, row in enumerate(self.rows)}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self.columns[section].title if orientation == Qt.Horizontal else section + 1
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row, column = self.rows[index.row()], self.columns[index.column()]
        value = row.get(column.key, '')
        if role == Qt.TextAlignmentRole and isinstance(value,(int,float,Decimal)) and not isinstance(value,bool):
            return Qt.AlignRight | Qt.AlignVCenter
        if role == Qt.UserRole:
            return row
        if role == Qt.UserRole + 1:
            return value
        if role == Qt.ToolTipRole:
            return str(value)
        if role in (Qt.DisplayRole, Qt.EditRole):
            if role == Qt.DisplayRole and column.key == 'status' and row.get('_status_label'):
                return row['_status_label']
            return column.format(value) if column.format and role == Qt.DisplayRole else value
        if role == Qt.ForegroundRole and row.get('status') == 'error':
            return QBrush(QColor('#CB6477'))
        return None

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid() and self.columns[index.column()].key in self.editable:
            flags |= Qt.ItemIsEditable
        return flags

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole or not index.isValid() or self.columns[index.column()].key not in self.editable:
            return False
        key = self.columns[index.column()].key
        self.rows[index.row()][key] = str(value)
        self.search_cache[index.row()] = search_text(' '.join(map(str, self.rows[index.row()].values())))
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        self.edited.emit(index.row(), key, value)
        return True

    def replace(self, rows):
        self.beginResetModel()
        self.rows = list(rows)
        self.search_cache = [search_text(' '.join(map(str, row.values()))) for row in self.rows]
        self.positions = {str(row.get('source', i)): i for i, row in enumerate(self.rows)}
        self.endResetModel()

    def append(self, rows):
        rows = list(rows)
        if not rows:
            return
        start = len(self.rows)
        self.beginInsertRows(QModelIndex(), start, start + len(rows) - 1)
        self.rows.extend(rows)
        self.search_cache.extend(search_text(' '.join(map(str, row.values()))) for row in rows)
        for i in range(start, len(self.rows)):
            self.positions[str(self.rows[i].get('source', i))] = i
        self.endInsertRows()

    def upsert(self, row):
        position = self.positions.get(str(row['source']))
        if position is None:
            self.append([row])
        else:
            self.rows[position].update(row)
            self.search_cache[position] = search_text(' '.join(map(str, self.rows[position].values())))
            self.dataChanged.emit(self.index(position, 0), self.index(position, len(self.columns) - 1))


@dataclass(eq=False)
class TreeNode:
    values: dict
    parent_node: object = None
    children: list = field(default_factory=list)
    row: int = 0
    search: str = ''


class TreeModel(QAbstractItemModel):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.columns = tuple(columns)
        self.root = TreeNode({})
        self.nodes = {}

    def replace(self, rows, *, key='id', parent='parent'):
        self.beginResetModel()
        self.root = TreeNode({})
        self.nodes = {str(row[key]): TreeNode(dict(row)) for row in rows}
        for node in self.nodes.values():
            node.search = search_text(' '.join(map(str, node.values.values())))
            parent_node = self.nodes.get(str(node.values.get(parent, '')), self.root)
            if parent_node is node:
                parent_node = self.root
            node.parent_node = parent_node
            node.row = len(parent_node.children)
            parent_node.children.append(node)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid() and parent.column() != 0:
            return 0
        return len((parent.internalPointer() if parent.isValid() else self.root).children)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def index(self, row, column, parent=QModelIndex()):
        node = parent.internalPointer() if parent.isValid() else self.root
        if 0 <= row < len(node.children) and 0 <= column < len(self.columns):
            return self.createIndex(row, column, node.children[row])
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        node = index.internalPointer().parent_node
        if node is None or node is self.root:
            return QModelIndex()
        return self.createIndex(node.row, 0, node)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.columns[section].title
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.internalPointer().values
        column = self.columns[index.column()]
        value = row.get(column.key, '')
        if role == Qt.UserRole:
            return row
        if role == Qt.UserRole + 1:
            return value
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            return column.format(value) if column.format else value
        if role == Qt.ForegroundRole and row.get('status') == 'error':
            return QBrush(QColor('#CB6477'))
        return None


class FilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None, *, tree=False):
        super().__init__(parent)
        self.query = ''
        self.status = None
        self.collator = QCollator(QLocale('tr_TR'))
        self.collator.setNumericMode(True)
        self.setRecursiveFilteringEnabled(tree)
        self.setDynamicSortFilter(True)

    def set_query(self, query):
        self.beginFilterChange()
        self.query = search_text(query)
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def set_status(self, status):
        self.beginFilterChange()
        self.status = status
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        if isinstance(model, TableModel):
            row = model.rows[source_row]
            searchable = model.search_cache[source_row]
        else:
            node = model.index(source_row, 0, source_parent).internalPointer()
            row, searchable = node.values, node.search
        return ((self.status is None or row.get('status') == self.status)
                and (not self.query or self.query in searchable))

    def lessThan(self, left, right):
        a, b = left.data(Qt.UserRole + 1), right.data(Qt.UserRole + 1)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a < b
        return self.collator.compare(str(a), str(b)) < 0
