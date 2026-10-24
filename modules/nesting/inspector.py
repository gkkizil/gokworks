"""Contextual Qt inspector; edits bind to the existing nesting form only."""

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (QWidget,QFrame,QVBoxLayout,QFormLayout,QComboBox,
    QLineEdit,QCheckBox,QSizePolicy)

from gui_qt.components import label,button,scroll,Disclosure


class NestingInspector(QWidget):
    def __init__(self,page):
        super().__init__(); self.page=page; self.setObjectName('inspectorBody')
        body=QVBoxLayout(self);body.setContentsMargins(0,0,0,0);body.setSpacing(0)
        content=QWidget();items=QVBoxLayout(content);items.setContentsMargins(0,0,0,0);items.setSpacing(0)
        self.sections={}
        def section(title):
            frame=QFrame();frame.setProperty('inspectorSection',True)
            outer=QVBoxLayout(frame);outer.setContentsMargins(10,5,10,8)
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
        self.sheet_info=label('Sac tanımlayın.','muted');self.sheet_info.setMinimumHeight(34);stock.addWidget(self.sheet_info)
        self.edit_sheet_button=button('Sac özelliklerini düzenle',self.edit_sheet);stock.addWidget(self.edit_sheet_button)
        selected=section('SEÇİLİ PARÇA')
        self.part_name=label('Parça seçilmedi.','section');self.part_info=label('Listeden veya çizimden seçin.','muted')
        self.part_info.setMinimumHeight(34)
        selected.addWidget(self.part_name);selected.addWidget(self.part_info)
        self.edit_part_button=button('Parça özelliklerini düzenle',page.edit_part);selected.addWidget(self.edit_part_button)
        parameters=section('YERLEŞİM')
        self.fields={};basic=QFormLayout();basic.setSpacing(6);basic.setRowWrapPolicy(QFormLayout.WrapLongRows)
        basic.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        parameters.addLayout(basic)
        for key,title in [('gap','Parça aralığı · mm'),('margin','Kenar payı · mm'),
                          ('rotation','Döndürme'),('quality','Kalite')]:
            basic.addRow(label(title),self.mirror(key))
        advanced=QWidget();extra=QFormLayout(advanced);extra.setContentsMargins(0,0,0,0)
        extra.setRowWrapPolicy(QFormLayout.WrapLongRows)
        for key,title in [('kerf','Kerf · mm'),('seconds','Azami süre · sn'),('seed','Deneme sırası')]:
            extra.addRow(label(title),self.mirror(key))
        parameters.addWidget(Disclosure('Gelişmiş yerleşim',advanced))
        parameters.addWidget(button('Tüm sac ve maliyet ayarları…',page.show_settings))
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
        with QSignalBlocker(self.sheet):
            self.sheet.clear()
            for sheet in self.page.project.sheets:self.sheet.addItem(sheet.name,sheet.id)
            self.sheet.setCurrentIndex(max(0,self.sheet.findData(previous)))
        self.sheet_changed();self.refresh_part()

    def sheet_changed(self):
        key=self.sheet.currentData()
        sheet=next((s for s in self.page.project.sheets if s.id==key),None)
        self.edit_sheet_button.setEnabled(sheet is not None)
        if sheet is None:self.sheet_info.setText('Sac ve ayarlardan stok ekleyin.');return
        material=self.page.project.material(sheet.material)
        self.sheet_info.setText(f'{sheet.width:g} × {sheet.height:g} × {sheet.thickness:g} mm\n'
                               f'{material.name} · {sheet.stock} plaka stok')

    def follow_plate(self,*args):
        key=self.page.selected_sheet_key()
        if key:
            index=self.sheet.findData(key[0])
            if index>=0:self.sheet.setCurrentIndex(index)

    def edit_sheet(self):
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
        self.part_info.setText(f"{data['material']} · t={data['thickness']:g} mm\n{data['quantity'] or '—'} adet")
