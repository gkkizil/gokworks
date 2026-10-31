"""Contextual Qt inspector; edits bind to the existing nesting form only."""

from dataclasses import replace

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (QWidget,QFrame,QVBoxLayout,QFormLayout,QComboBox,
    QLineEdit,QCheckBox,QSizePolicy,QHBoxLayout)

from gui_qt.components import label,button,scroll,Disclosure,ValueForm
from .ui_widgets import Values
from .models import number,integer
from .accounting import mass
from .geometry import polygons
from .design import CONTROL_HEIGHT


class NestingInspector(QWidget):
    def __init__(self,page):
        super().__init__(); self.page=page; self.setObjectName('inspectorBody')
        self.setStyleSheet('QWidget#inspectorBody QLineEdit, QWidget#inspectorBody QComboBox { min-height:20px; }')
        self._syncing = False; self._active_sheet_id = None; self.sheet_dirty = False
        body=QVBoxLayout(self);body.setContentsMargins(0,0,0,0);body.setSpacing(0)
        content=QWidget();items=QVBoxLayout(content);items.setContentsMargins(0,0,0,0);items.setSpacing(0)
        self.sections={}
        def section(title):
            frame=QFrame();frame.setProperty('inspectorSection',True)
            outer=QVBoxLayout(frame);outer.setContentsMargins(8,4,8,8)
            content=QWidget();layout=QVBoxLayout(content)
            layout.setContentsMargins(0,0,0,0);layout.setSpacing(6)
            disclosure=Disclosure(title,content,expanded=True)
            disclosure.toggle.setProperty('inspectorGroup',True)
            outer.addWidget(disclosure);self.sections[title]=disclosure
            items.addWidget(frame);return layout
        stock=section('SAC VE MALZEME')
        self.sheet=QComboBox();self.sheet.setMinimumWidth(0)
        self.sheet.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.sheet.setMinimumContentsLength(8);self.sheet.setAccessibleName('Özellikleri gösterilen sac')
        self.sheet.currentIndexChanged.connect(self.sheet_changed);stock.addWidget(self.sheet)
        self.sheet.activated.connect(self.activate_sheet)
        self.sheet_info=label('Sac tanımlayın.','muted');stock.addWidget(self.sheet_info)
        self.sheet_form = ValueForm(Values(),'')
        self.sheet_form.form.setSpacing(4)
        self.sheet_material = QComboBox(); self.sheet_material.setMinimumWidth(0)
        self.sheet_material.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.sheet_material.setMinimumContentsLength(6); self.sheet_material.setAccessibleName('Sac malzemesi')
        self.sheet_form.form.addRow(label('Malzeme'),self.sheet_material)
        for key,title in [('thickness','Kalınlık · mm'),('width','Sac eni · mm'),('height','Sac boyu · mm'),('stock','Stok · plaka')]:
            self.sheet_form.text(key,title,'').textChanged.connect(self.mark_sheet_dirty)
            self.sheet_form.fields[key].setAlignment(Qt.AlignRight)
            self.sheet_form.fields[key].setMinimumHeight(CONTROL_HEIGHT)
        # Pair related dimensions without duplicating field values or parsers.
        pairs = []
        for keys in (('width','height'),('thickness','stock')):
            pair = QWidget(); row = QHBoxLayout(pair); row.setContentsMargins(0,0,0,0); row.setSpacing(6)
            for key in keys:
                taken = self.sheet_form.form.takeRow(self.sheet_form.fields[key])
                column = QVBoxLayout(); column.setSpacing(2)
                caption = taken.labelItem.widget(); caption.setWordWrap(False)
                column.addWidget(caption); column.addWidget(taken.fieldItem.widget()); row.addLayout(column,1)
            pairs.append(pair)
        for pair in pairs: self.sheet_form.form.addRow(pair)
        self.sheet_material.currentIndexChanged.connect(self.mark_sheet_dirty)
        stock.addWidget(self.sheet_form)
        self.sheet_error = label('','error'); self.sheet_error.hide(); stock.addWidget(self.sheet_error)
        self.sheet_draft = label('Sac değişikliği bekliyor; Uygula ile kaydedin.','muted'); self.sheet_draft.hide(); stock.addWidget(self.sheet_draft)
        self.sheet_actions = QWidget(); apply_row = QHBoxLayout(self.sheet_actions); apply_row.setContentsMargins(0,0,0,0)
        self.apply_sheet_button = button('Uygula',self.apply_sheet); apply_row.addWidget(self.apply_sheet_button)
        self.revert_sheet_button = button('Geri al',self.revert_sheet); apply_row.addWidget(self.revert_sheet_button)
        stock.addWidget(self.sheet_actions); self.sheet_actions.hide()
        self.edit_sheet_button=button('Fiyat ve diğer bilgiler…',self.edit_sheet);stock.addWidget(self.edit_sheet_button)
        parameters=section('YERLEŞİM')
        self.fields={};basic=QFormLayout();basic.setSpacing(6);basic.setRowWrapPolicy(QFormLayout.WrapLongRows)
        basic.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        parameters.addLayout(basic)
        for key,title in [('gap','Parça aralığı · mm'),('margin','Kenar payı · mm'),
                          ('rotation','Döndürme'),('quality','Kalite')]:
            basic.addRow(label(title),self.mirror(key))
        parameters.addWidget(label('Hesaplama süresi otomatik yönetilir.','muted'))
        advanced=QWidget();extra=QFormLayout(advanced);extra.setContentsMargins(0,0,0,0)
        extra.setRowWrapPolicy(QFormLayout.WrapLongRows)
        for key,title in [('kerf','Kesim genişliği · mm'),('angles','İzinli açılar · °'),('angle_step','Açı adımı · °'),
                          ('grain_locked','Hadde yönü kilidi'),('seed','Deneme sırası')]:
            extra.addRow(label(title),self.mirror(key))
        parameters.addWidget(Disclosure('Gelişmiş yerleşim',advanced))
        selected=section('SEÇİLİ PARÇA')
        self.part_name=label('Parça seçilmedi.','section');self.part_info=label('Listeden veya çizimden seçin.','muted')
        self.part_info.setMinimumHeight(34)
        selected.addWidget(self.part_name);selected.addWidget(self.part_info)
        self.edit_part_button=button('Parça özelliklerini düzenle',page.edit_part);selected.addWidget(self.edit_part_button)
        items.addStretch();body.addWidget(scroll(content),1)
        page.sheet_model.modelReset.connect(self.refresh)
        page.part_model.modelReset.connect(self.refresh_part)
        page.part_table.selectionModel().selectionChanged.connect(self.refresh_part)
        page.sheet_tabs.currentChanged.connect(self.follow_plate)
        self.refresh()

    def mirror(self,key):
        source=self.page.form.fields[key]
        if isinstance(source,QLineEdit):
            target=QLineEdit(source.text());target.setClearButtonEnabled(True)
            target.setAlignment(source.alignment())
            target.textChanged.connect(source.setText)
            def update(text):
                with QSignalBlocker(target):target.setText(text)
            source.textChanged.connect(update)
        elif isinstance(source,QCheckBox):
            target=QCheckBox('Etkin');target.setChecked(source.isChecked())
            target.toggled.connect(source.setChecked)
            def update(checked):
                with QSignalBlocker(target):target.setChecked(checked)
            source.toggled.connect(update)
        else:
            target=QComboBox()
            target.addItems([source.itemText(i) for i in range(source.count())]);target.setCurrentIndex(source.currentIndex())
            target.currentIndexChanged.connect(source.setCurrentIndex)
            def update(index):
                with QSignalBlocker(target):target.setCurrentIndex(index)
            source.currentIndexChanged.connect(update)
        target.setMinimumWidth(80);target.setAccessibleName(source.accessibleName())
        target.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.fields[key]=target;return target

    def refresh(self):
        previous=self.sheet.currentData()
        if self._active_sheet_id not in {s.id for s in self.page.project.sheets}:
            self.sheet_dirty = False; self._active_sheet_id = None
        with QSignalBlocker(self.sheet):
            self.sheet.clear()
            for sheet in self.page.project.sheets:
                self.sheet.addItem(f'{sheet.width:g} × {sheet.height:g} · {self.page.project.material(sheet.material).name}',sheet.id)
            self.sheet.setCurrentIndex(max(0,self.sheet.findData(previous)))
        self.sheet_changed();self.refresh_part()

    def sheet_changed(self):
        key=self.sheet.currentData()
        if self.sheet_dirty and key!=self._active_sheet_id:
            if not self.apply_sheet():
                with QSignalBlocker(self.sheet): self.sheet.setCurrentIndex(self.sheet.findData(self._active_sheet_id))
                return
        sheet=next((s for s in self.page.project.sheets if s.id==key),None)
        self.edit_sheet_button.setEnabled(sheet is not None)
        self.sheet_form.setEnabled(sheet is not None); self.sheet_material.setEnabled(sheet is not None)
        if sheet is None:
            self._active_sheet_id = None; self.sheet_dirty = False
            self.sheet_error.hide(); self.sheet_draft.hide(); self.sheet_actions.hide()
            self.apply_sheet_button.setEnabled(False); self.revert_sheet_button.setEnabled(False)
            self.sheet_material.clear()
            for name in self.sheet_form.fields: self.sheet_form.set_value(name,'')
            self.sheet_info.setText('Sac listesinde + ile stok ekleyin.'); return
        price = f'{sheet.price_sheet:g} TL/plaka' if sheet.pricing=='sheet' else f'{sheet.price_kg:g} TL/kg'
        self.sheet_info.setText(f'{sheet.stock} plaka stok · {price}' + ('\nSac fiyatı girilmedi.' if (sheet.price_sheet if sheet.pricing=='sheet' else sheet.price_kg)==0 else ''))
        if not self.sheet_dirty or key!=self._active_sheet_id:
            self._syncing = True
            try:
                self.sheet_material.clear()
                for material in self.page.project.materials: self.sheet_material.addItem(material.name,material.id)
                self.sheet_material.setCurrentIndex(self.sheet_material.findData(sheet.material))
                for name in ('width','height','thickness','stock'): self.sheet_form.set_value(name,getattr(sheet,name))
                self._active_sheet_id = key; self.sheet_dirty = False
                self.sheet_error.hide(); self.sheet_draft.hide(); self.sheet_actions.hide()
            finally: self._syncing = False
        self.apply_sheet_button.setEnabled(self.sheet_dirty); self.revert_sheet_button.setEnabled(self.sheet_dirty)

    def mark_sheet_dirty(self,*args):
        if self._syncing or self._active_sheet_id is None: return
        self.sheet_dirty = True; self.sheet_draft.show()
        self.sheet_actions.show()
        self.apply_sheet_button.setEnabled(True); self.revert_sheet_button.setEnabled(True)
        # A visible draft must never leave an exportable plan with older stock.
        self.page.invalidate()

    def apply_sheet(self):
        if not self.sheet_dirty: return True
        if self.page.busy: return False
        sheet=next((s for s in self.page.project.sheets if s.id==self._active_sheet_id),None)
        if sheet is None: return False
        try:
            f = self.sheet_form
            material = self.sheet_material.currentData()
            if material not in {m.id for m in self.page.project.materials}: raise ValueError('Geçerli bir sac malzemesi seçin.')
            updated = replace(sheet,material=material,
                thickness=number(f.value('thickness'),'Sac kalınlığı',positive=True),
                width=number(f.value('width'),'Sac eni',positive=True),height=number(f.value('height'),'Sac boyu',positive=True),
                stock=integer(f.value('stock'),'Stok',minimum=0))
        except ValueError as error:
            self.sheet_error.setText(str(error)); self.sheet_error.show()
            self.page.set_status(str(error),True); return False
        self.sheet_dirty = False; self.sheet_draft.hide(); self.sheet_error.hide(); self.sheet_actions.hide()
        self.page.project.sheets[self.page.project.sheets.index(sheet)] = updated
        self.page.invalidate(); self.page.refresh()
        self.page.persist_stock(sheet=updated)
        return True

    def revert_sheet(self):
        self.sheet_dirty = False; self.sheet_changed()

    def follow_plate(self,*args):
        key=self.page.selected_sheet_key()
        if key:
            index=self.sheet.findData(key[0])
            if index>=0:self.sheet.setCurrentIndex(index)

    def activate_sheet(self,*args):
        item=self.page.sheet_tree_model.by_stock.get(self.sheet.currentData())
        if item is not None:
            with QSignalBlocker(self.page.sheet_tree.selectionModel()):
                self.page.sheet_tree.setCurrentIndex(item.index())
            self.page.select_browser_sheet(item.index())

    def edit_sheet(self):
        if not self.apply_sheet(): return
        key=self.sheet.currentData()
        for row,item in enumerate(self.page.sheet_model.rows):
            if item['id']==key:
                self.page.sheet_table.selectRow(row);self.page.edit_sheet();return

    def refresh_part(self,*args):
        rows=self.page.part_table.selectionModel().selectedRows()
        self.edit_part_button.setEnabled(len(rows)==1 and rows[0].data(Qt.UserRole).get('kind')=='part')
        if len(rows)!=1:
            self.part_name.setText(f'{len(rows)} parça seçili' if rows else 'Parça seçilmedi.')
            self.part_info.setText('Listeden veya çizimden seçin.');return
        data=rows[0].data(Qt.UserRole)
        self.part_name.setText(data['code'])
        self.part_name.setToolTip(data.get('source',''))
        if data.get('kind')!='part':
            self.part_info.setText(data.get('detail','Dosya henüz okunmadı.')); return
        part = self.page.project.part(data['id']); x0,y0,x1,y1 = part.polygon.bounds
        outer = sum(p.exterior.length for p in polygons(part.polygon))
        inner = sum(r.length for p in polygons(part.polygon) for r in p.interiors)
        weight = mass(part.area,part.thickness,self.page.project.material(part.material).density)
        self.part_info.setText(f"{data['material']} · {data['thickness']:g} mm · {part.quantity} adet\n"
            f'{x1-x0:g} × {y1-y0:g} mm\nNet alan {part.area:.2f} mm² · {weight:.3f} kg/adet\n'
            f'Dış / iç çevre: {outer:.2f} / {inner:.2f} mm')
        if self.page.result is not None:
            placed = sum(p.part_id==part.id for p in self.page.result.placements)
            self.part_info.setText(self.part_info.text()+f'\nYerleşen: {placed} / {part.quantity}')
