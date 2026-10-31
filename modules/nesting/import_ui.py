"""Native editable import preview. Geometry remains in the background job."""

from copy import deepcopy

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox,
    QHBoxLayout, QHeaderView, QLineEdit, QSplitter, QTableView, QVBoxLayout, QWidget)

from gui_qt.components import button, configure_view, label
from .import_plan import ImportDraft, normalize_options
from .ui_widgets import Editor


class ImportPreviewModel(QAbstractTableModel):
    invalid = Signal(str)
    changed = Signal()
    headers = ('Dosya adı','Kalınlık · mm','Adet','Durum')

    def __init__(self, drafts, defaults, parent=None):
        super().__init__(parent)
        self.drafts = drafts; self.defaults = defaults; self.automatic = True
        self.invalid_edits = {}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.drafts)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 4

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self.headers[section] if orientation == Qt.Horizontal else section+1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        draft = self.drafts[index.row()]
        row_errors = [message for (row,_),message in self.invalid_edits.items() if row==index.row()]
        if role == Qt.ToolTipRole:
            options = draft.options(self.defaults,self.automatic)
            return '\n'.join(filter(None, (draft.source, ' '.join(row_errors), draft.issues(self.automatic),
                'Kural: '+', '.join(draft.detected.rules),
                'Elle düzenlenen: '+', '.join(draft.manual),
                f"Malzeme: {options['material']} · DXF birimi: {options['unit'] or 'dosyadan'}",
                'Birden fazla bağımsız parça varsa adet dağılımı okumadan sonra ayrıca onaylanır.')))
        if role == Qt.TextAlignmentRole and index.column() in (1,2):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role in (Qt.DisplayRole, Qt.EditRole):
            if index.column()==0: return draft.detected.filename
            if index.column()==3: return 'Kontrol gerekli' if row_errors else draft.status(self.automatic)
            key = ('thickness','quantity')[index.column()-1]
            if (role==Qt.DisplayRole and self.automatic and key not in draft.manual
                    and getattr(draft.detected,key+'_issue')):
                return '—'
            value = draft.options(self.defaults,self.automatic)[key]
            return f'{value:g}' if role==Qt.DisplayRole else str(value)

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid() and index.column() in (1,2): flags |= Qt.ItemIsEditable
        return flags

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole or not index.isValid() or index.column() not in (1,2): return False
        try: self.drafts[index.row()].edit(('thickness','quantity')[index.column()-1],value)
        except ValueError as error:
            self.invalid_edits[index.row(),index.column()] = str(error)
            self.dataChanged.emit(self.index(index.row(),3),self.index(index.row(),3))
            self.changed.emit(); self.invalid.emit(str(error)); return False
        self.invalid_edits.pop((index.row(),index.column()),None)
        self.dataChanged.emit(self.index(index.row(),1),self.index(index.row(),3))
        self.changed.emit(); return True

    def refresh(self):
        if self.drafts: self.dataChanged.emit(self.index(0,0),self.index(len(self.drafts)-1,3))
        self.changed.emit()


class ImportDialog(Editor):
    def __init__(self, parent, files, defaults, build, parse, *, retained=None, review=None, detail=''):
        self.parse_options = parse; self.build_options = build
        self.review = review
        self.drafts = [ImportDraft.create(path,retained=retained) for path in files]
        super().__init__(parent,'DXF/DWG dosyalarını kontrol et',lambda f:build(f,defaults),self.make_plan)
        available = self.screen().availableGeometry()
        self.resize(min(1000,available.width()-48),min(790,available.height()-48))
        for widget in self.form.fields.values():
            caption = self.form.form.labelForField(widget)
            if caption is not None: caption.setWordWrap(False)
        self.preview_model = ImportPreviewModel(self.drafts,normalize_options(defaults),self)
        self.preview_model.invalid.connect(self.error.setText)
        self.preview_model.changed.connect(self.update_summary)
        self.auto = QCheckBox('Dosya adından kalınlık ve adet oku'); self.auto.setChecked(True)
        self.auto.setAccessibleName(self.auto.text())
        self.auto.toggled.connect(self.automatic_changed)
        panel = QWidget(); panel_layout = QVBoxLayout(panel); panel_layout.setContentsMargins(0,0,0,0)
        panel_layout.addWidget(self.auto)
        self.summary = label('', 'muted'); panel_layout.addWidget(self.summary)
        if detail and not review: panel_layout.addWidget(label(detail,'muted'))
        self.table = configure_view(QTableView()); self.table.setModel(self.preview_model)
        self.table.setAccessibleName('DXF dosyaları: kalınlık ve adet önizlemesi')
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)
        self.table.setSortingEnabled(False)
        header = self.table.horizontalHeader(); header.setStretchLastSection(False)
        header.setSectionResizeMode(0,QHeaderView.Stretch)
        for column,width in ((1,125),(2,80),(3,155)):
            self.table.setColumnWidth(column,width)
        panel_layout.addWidget(self.table,1)
        row = QHBoxLayout(); row.addWidget(label('Seçili satırlara:'))
        self.bulk_thickness = QLineEdit(); self.bulk_thickness.setPlaceholderText('Kalınlık · mm')
        self.bulk_thickness.setAccessibleName('Seçili DXF kalınlığı')
        self.bulk_quantity = QLineEdit(); self.bulk_quantity.setPlaceholderText('Adet')
        self.bulk_quantity.setAccessibleName('Seçili DXF adedi')
        row.addWidget(self.bulk_thickness); row.addWidget(self.bulk_quantity)
        row.addWidget(button('Uygula',self.apply_selected)); panel_layout.addLayout(row)
        panel_layout.addWidget(button('Seçili dosyanın diğer seçenekleri…',self.edit_source_options))
        panel_layout.addWidget(label('Adet, her bağımsız parça içindir. Delikler ayrı parça sayılmaz. '
            'Birden fazla parça bulunursa içe aktarma ayrıca onay ister.', 'muted'))
        self.contour_summary = label('', 'section'); panel_layout.addWidget(self.contour_summary)
        self.contour_summary.setVisible(review is not None); self._review_signature = None
        self.confirm_contours = QCheckBox('Bu adedi her bağımsız parçaya uygulamayı onaylıyorum.')
        self.confirm_contours.setVisible(review is not None); panel_layout.addWidget(self.confirm_contours)
        # Keep native form controls, but reserve most room for selected sources.
        layout = self.layout(); form_scroll = layout.itemAt(0).widget()
        layout.removeWidget(form_scroll)
        splitter = QSplitter(Qt.Vertical); splitter.addWidget(panel); splitter.addWidget(form_scroll)
        splitter.setChildrenCollapsible(False); splitter.setSizes([450,180])
        layout.insertWidget(0,splitter,1)
        self.form.changed.connect(self.defaults_changed)
        self.buttons = self.findChild(QDialogButtonBox)
        self.buttons.button(QDialogButtonBox.Ok).setText('Kontrol ettim · İçe aktar')
        self.update_summary()

    def defaults_changed(self):
        try: defaults = self.parse_options(self.form)
        except ValueError as error:
            self.error.setText(str(error)); return
        self.preview_model.defaults = defaults; self.preview_model.refresh()

    def automatic_changed(self, enabled):
        self.preview_model.automatic = enabled; self.preview_model.refresh()

    def update_summary(self):
        automatic = self.preview_model.automatic
        invalid_rows = {row for row,_ in self.preview_model.invalid_edits}
        full = sum(d.status(automatic)=='Algılandı' and i not in invalid_rows for i,d in enumerate(self.drafts))
        review = sum(bool(d.issues(automatic)) or i in invalid_rows for i,d in enumerate(self.drafts))
        self.summary.setText(f'{len(self.drafts)} dosya · {full} tam algılandı / düzenlendi · {review} kontrol gerekli')
        if self.review:
            options = self.drafts[0].options(self.preview_model.defaults,automatic)
            quantity, grouped = options['quantity'],options['grouped']
            signature = quantity,grouped
            if self._review_signature is not None and signature != self._review_signature:
                self.confirm_contours.setChecked(False)
            self._review_signature = signature
            count = self.review['count']
            self.contour_summary.setText(f'Tek grup: {quantity} set · {count} kontur birlikte taşınır.' if grouped else
                f'{count} bağımsız parça × {quantity} adet = {count*quantity} kesim parçası.')
            self.confirm_contours.setVisible(not grouped)
        self.error.clear()

    def selected_rows(self):
        return sorted({index.row() for index in self.table.selectionModel().selectedRows()})

    def apply_selected(self):
        rows = self.selected_rows()
        if not rows: return self.error.setText('Önce bir veya birden fazla dosya satırı seçin.')
        changes = {k:v.text().strip() for k,v in (('thickness',self.bulk_thickness),('quantity',self.bulk_quantity)) if v.text().strip()}
        if not changes: return self.error.setText('Uygulamak için kalınlık veya adet girin.')
        try:
            # Validate the whole edit before touching any row.
            sample = deepcopy(self.drafts[rows[0]])
            for key,value in changes.items(): sample.edit(key,value)
        except ValueError as error: return self.error.setText(str(error))
        for row in rows:
            for key,value in changes.items():
                self.drafts[row].edit(key,value)
                self.preview_model.invalid_edits.pop((row,1 if key=='thickness' else 2),None)
        self.preview_model.refresh()

    def edit_source_options(self):
        rows = self.selected_rows()
        if len(rows)!=1: return self.error.setText('Diğer seçenekler için tek dosya seçin.')
        draft = self.drafts[rows[0]]
        options = draft.options(self.preview_model.defaults,self.preview_model.automatic)
        dialog = Editor(self,draft.detected.filename,lambda f:self.build_options(f,options),self.parse_options)
        try:
            if dialog.exec()==QDialog.Accepted:
                draft.manual.update(dialog.value)
                for column in (1,2): self.preview_model.invalid_edits.pop((rows[0],column),None)
                self.preview_model.refresh()
        finally: dialog.deleteLater()

    def make_plan(self, form):
        defaults = self.parse_options(form)
        if self.preview_model.invalid_edits:
            raise ValueError('Hatalı hücreyi düzeltin: '+next(iter(self.preview_model.invalid_edits.values())))
        automatic = self.preview_model.automatic
        plans = []
        for draft in self.drafts:
            if draft.issues(automatic):
                raise ValueError(draft.detected.filename+': '+draft.issues(automatic)+' Kalınlık/adet hücresini düzenleyin.')
            options = draft.options(defaults,automatic)
            plan = dict(source=draft.source,options=options,
                        part_code=draft.detected.code if automatic else '')
            if self.review and not options['grouped']:
                if not self.confirm_contours.isChecked():
                    raise ValueError('Bağımsız parçalara uygulanacak adetleri onaylayın veya tek grup seçin.')
                plan['contour_approval'] = dict(self.review,quantity=options['quantity'])
            plans.append(plan)
        if sum(p['options']['quantity'] for p in plans)>10000:
            raise ValueError('Seçilen dosyalarda 10000 üzerinde parça var; adetleri azaltın.')
        return plans
