"""Checkable, virtualized body inventory using the shared results table."""

from PySide6.QtCore import Qt, Signal
from gui_qt.models import TableModel, Column, LABELS


class SheetTableModel(TableModel):
    selectionEdited = Signal(object, bool)

    def __init__(self):
        super().__init__((Column('Seç', 'selected'), Column('Parça / kod', 'source_label'),
                          Column('Gövde', 'body_name'), Column('Kalınlık · mm', 'thickness_mm', lambda v:f'{v:g}' if isinstance(v,(float,int)) else ''),
                          Column('Malzeme', 'material'), Column('Adet', 'quantity'),
                          Column('Açınım durumu', 'status', lambda v:LABELS.get(v,v)), Column('Açıklama', 'detail')))
        self.locked = False

    @staticmethod
    def token(row):
        return str(row.get('row_id') or row['source'])

    def reindex(self):
        self.positions = {self.token(row): i for i,row in enumerate(self.rows)}

    def replace(self, rows):
        super().replace(rows); self.reindex()

    def append(self, rows):
        super().append(rows); self.reindex()

    def upsert(self, row):
        position = self.positions.get(self.token(row))
        if position is None:
            self.append([row])
        else:
            from gui_qt.models import search_text
            self.rows[position].update(row)
            self.search_cache[position] = search_text(' '.join(map(str,self.rows[position].values())))
            self.dataChanged.emit(self.index(position,0),self.index(position,len(self.columns)-1))

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            row = self.rows[index.row()]
            if index.column() == 0:
                if role == Qt.CheckStateRole:
                    state = row.get('selected', True)
                    return Qt.PartiallyChecked if state is None else Qt.Checked if state else Qt.Unchecked
                if role == Qt.DisplayRole:
                    return ''
            if role == Qt.DisplayRole and index.column()==1:
                return row.get('code') or row.get('source_label') or row['source']
            if role == Qt.DisplayRole and index.column()==6 and row.get('sheet_id') and row.get('status')=='pending':
                return 'Hazır'
            if role == Qt.ToolTipRole:
                if not row.get('sheet_id'):return row['source']
                return row['source']+'\n'+row.get('configuration','')+'\n'+row.get('cut_list','')+'\n'+row.get('detail','')
        return super().data(index,role)

    def flags(self,index):
        flags = super().flags(index)
        if index.isValid() and index.column()==0 and not self.locked and self.rows[index.row()].get('exportable',True):
            flags |= Qt.ItemIsUserCheckable
        return flags

    def setData(self,index,value,role=Qt.EditRole):
        if not index.isValid() or index.column()!=0 or role!=Qt.CheckStateRole or self.locked:
            return False
        row = self.rows[index.row()]
        if not row.get('exportable',True):
            return False
        checked = value in (Qt.Checked,Qt.Checked.value)
        row['selected'] = checked
        self.selectionEdited.emit(dict(row), checked)
        self.dataChanged.emit(index,index,[Qt.CheckStateRole])
        return True
