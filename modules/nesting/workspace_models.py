"""Qt presentation adapters for the existing parts, stock and verified results.

No CAD geometry, placement or accounting is calculated here. The flat import
model remains the source of truth; tree leaves map back to those exact rows.
"""

from dataclasses import dataclass, field

from PySide6.QtCore import QAbstractProxyModel, QModelIndex, Qt, Signal, QItemSelectionModel
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QTreeView, QAbstractItemView, QHeaderView


@dataclass
class Node:
    row: int
    source_row: int = -1
    parent_node: object = None
    title: str = ''
    count: int = 0
    children: list = field(default_factory=list)
    identifier: str = ''


class PartTreeModel(QAbstractProxyModel):
    """Group filtered parts by actual material and thickness, without copying them."""
    def __init__(self, source, parent=None):
        super().__init__(parent)
        self.groups = []; self.by_source_row = {}; self.by_id = {}
        self.setSourceModel(source)
        for signal in (source.modelReset, source.layoutChanged, source.rowsInserted,
                       source.rowsRemoved, source.dataChanged):
            signal.connect(self.rebuild)
        self.rebuild()

    def rebuild(self, *args):
        self.beginResetModel()
        groups = {}; self.by_source_row = {}; self.by_id = {}
        source = self.sourceModel()
        for row in range(source.rowCount()):
            data = source.index(row, 0).data(Qt.UserRole)
            imported = data.get('kind') != 'part'
            key = ('imports',) if imported else (data['material'], data['thickness'])
            if key not in groups:
                title = 'Dosya durumları' if imported else f"{key[0]} · {key[1]:g} mm"
                groups[key] = Node(len(groups), title=title)
            group = groups[key]
            leaf = Node(len(group.children), row, group, identifier=data['id'])
            group.children.append(leaf); group.count += data.get('quantity') or 0
            self.by_source_row[row] = leaf; self.by_id[data['id']] = leaf
        self.groups = list(groups.values())
        self.endResetModel()

    def index(self, row, column, parent=QModelIndex()):
        if row < 0 or column < 0 or column >= self.columnCount(): return QModelIndex()
        if not parent.isValid():
            return self.createIndex(row, column, self.groups[row]) if row < len(self.groups) else QModelIndex()
        node = parent.internalPointer()
        if parent.column() or node.parent_node is not None or row >= len(node.children): return QModelIndex()
        return self.createIndex(row, column, node.children[row])

    def parent(self, index):
        if not index.isValid(): return QModelIndex()
        node = index.internalPointer().parent_node
        return self.createIndex(node.row, 0, node) if node is not None else QModelIndex()

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid(): return len(self.groups)
        return len(parent.internalPointer().children) if parent.column() == 0 else 0

    def columnCount(self, parent=QModelIndex()):
        return self.sourceModel().columnCount() if self.sourceModel() is not None else 0

    def mapToSource(self, index):
        if not index.isValid(): return QModelIndex()
        node = index.internalPointer()
        return self.sourceModel().index(node.source_row, index.column()) if node.source_row >= 0 else QModelIndex()

    def mapFromSource(self, index):
        node = self.by_source_row.get(index.row()) if index.isValid() else None
        return self.createIndex(node.row, index.column(), node) if node else QModelIndex()

    def index_for_id(self, part_id):
        node = self.by_id.get(part_id)
        return self.createIndex(node.row, 0, node) if node else QModelIndex()

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        node = index.internalPointer()
        if node.source_row >= 0: return self.sourceModel().data(self.mapToSource(index), role)
        if role == Qt.DisplayRole:
            return node.title if index.column() == 0 else node.count if index.column() == 1 and node.count else None
        if role == Qt.FontRole:
            font = QFont(); font.setBold(True); return font
        if role == Qt.ToolTipRole: return f'{node.title}\n{len(node.children)} kayıt · {node.count} kesilecek parça'
        if role == Qt.UserRole: return dict(kind='group', title=node.title)
        return None

    def flags(self, index):
        if not index.isValid(): return Qt.NoItemFlags
        return Qt.ItemIsEnabled if index.internalPointer().source_row < 0 else Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        return self.sourceModel().headerData(section, orientation, role)

    def sort(self, column, order=Qt.AscendingOrder):
        self.sourceModel().sort(column, order)


class PartTree(QTreeView):
    """Native grouped view, with a flat-row bridge for existing module integrations."""
    selectionRestored = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self._restoring = False; self._selection_ids = []; self._current_id = ''
        self.setUniformRowHeights(True); self.setIndentation(14)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(False)
        self.setSortingEnabled(True)
        self.setAccessibleName('Parça ağacı: malzeme ve kalınlığa göre gruplanmış DXF parçaları')

    def setModel(self,model):
        super().setModel(model)
        model.modelAboutToBeReset.connect(self.remember_selection)
        model.modelReset.connect(self.restore_selection)

    def remember_selection(self):
        self._restoring = True
        self._selection_ids = [i.internalPointer().identifier for i in self.selectionModel().selectedRows()]
        current = self.currentIndex()
        self._current_id = current.internalPointer().identifier if current.isValid() else ''

    def restore_selection(self):
        self.expandAll()
        for key in self._selection_ids:
            index = self.model().index_for_id(key)
            if index.isValid(): self.selectionModel().select(index,QItemSelectionModel.Select|QItemSelectionModel.Rows)
        index = self.model().index_for_id(self._current_id)
        if index.isValid(): self.selectionModel().setCurrentIndex(index,QItemSelectionModel.NoUpdate)
        self._restoring = False; self.selectionRestored.emit()

    def selectRow(self, source_row):
        index = self.model().mapFromSource(self.model().sourceModel().index(source_row, 0))
        self.select_index(index)

    def select_index(self, index):
        from PySide6.QtCore import QItemSelectionModel
        if index.isValid():
            self.expand(index.parent())
            self.selectionModel().setCurrentIndex(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
            self.scrollTo(index)


class SheetTreeModel(QStandardItemModel):
    """Configured stocks contain only the real physical sheets in the current result."""
    def __init__(self, parent=None):
        super().__init__(parent); self.by_key = {}; self.by_stock = {}

    def rebuild(self, project, totals):
        self.clear(); self.setHorizontalHeaderLabels(['Sac / plaka', 'Stok'])
        self.by_key = {}; self.by_stock = {}
        for sheet in project.sheets:
            material = project.material(sheet.material).name
            title = f'{sheet.width:g} × {sheet.height:g} · {sheet.thickness:g} mm'
            item = QStandardItem(title); stock = QStandardItem(str(sheet.stock))
            data = dict(kind='stock', id=sheet.id)
            for cell in (item, stock):
                cell.setEditable(False); cell.setData(data, Qt.UserRole)
                cell.setToolTip(f'{sheet.name}\n{material} · {title}\n{sheet.stock} plaka stok')
            item.setFont(self._bold())
            self.appendRow([item, stock]); self.by_stock[sheet.id] = item
            for row in totals:
                if row['id'] != sheet.id: continue
                key = (row['id'], row['number'])
                plate = QStandardItem(f"{row['plate']}. plaka · %"+f"{row['efficiency']:.1f}".replace('.',','))
                plate.setEditable(False); plate.setData(dict(kind='plate', key=key), Qt.UserRole)
                plate.setToolTip(f"{row['plate']}. plaka · {material}\nVerim %{row['efficiency']:.1f}\nNet {row['net_weight']:.3f} kg")
                item.appendRow([plate, QStandardItem('')]); self.by_key[key] = plate

    @staticmethod
    def _bold():
        font = QFont(); font.setBold(True); return font


def configure_sheet_tree(view):
    view.setUniformRowHeights(True); view.setIndentation(14)
    view.setEditTriggers(QAbstractItemView.NoEditTriggers)
    view.setSelectionBehavior(QAbstractItemView.SelectRows)
    view.setAccessibleName('Sac listesi: stoklar ve hesaplanan fiziksel plakalar')
    view.header().setStretchLastSection(False)
    view.header().setSectionResizeMode(0, QHeaderView.Stretch)
    view.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
