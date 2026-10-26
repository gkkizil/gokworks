"""GOKWORKS BasePage: stage editor, native operations and two linked views."""

from copy import deepcopy
from dataclasses import fields
from pathlib import Path

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QSplitter,
    QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QTabWidget,
    QLineEdit,QComboBox,QDoubleSpinBox,QListWidget,QListWidgetItem,QFileDialog,QMessageBox)
from gui_qt.components import BasePage, label, button, scroll
from . import controller, storage
from .geometry import operation_plan
from .models import Project, Groove, Keyway, Chamfer, Fillet
from .preview import ShaftPreview
from .standard_picker import ChannelStandardPicker
from .validation import validate


TITLES = {'groove':'Segman kanalı','keyway':'Kama kanalı','chamfer':'Pah','fillet':'Radyüs'}
FIELD_TITLES = {'offset':'Başlangıç · mm','width':'Genişlik · mm','length':'Boy · mm','depth':'Radyal derinlik · mm',
                'angle':'Açı · °','distance':'Mesafe · mm','radius':'Radyüs · mm'}


class ShaftPage(BasePage):
    def __init__(self,context):
        super().__init__(context,'Parametrik mil','Kademeleri ve operasyonları düzenleyin; iki görünüş aynı ölçüleri kullanır.')
        # Reserve native Windows font/frame overhead at 550×450 without
        # reducing either technical view's 170 px minimum or clipping commands.
        self.layout.setContentsMargins(10,2,10,2);self.layout.setSpacing(2)
        self.project=Project(); self.selected_stage=self.project.stages[0].id
        self.selected_operation=''; self.project_path=None; self.dirty=False
        self.plan=[]; self.last_result=None
        self.open_button=self.action('Proje aç',self.open_dialog)
        self.save_button=self.action('Proje kaydet',self.save_dialog)
        self.splitter=QSplitter(Qt.Horizontal); self.splitter.setChildrenCollapsible(False)
        self.editor=QWidget(); self.editor.setMinimumWidth(280); self.editor.setMaximumWidth(480)
        edit=QVBoxLayout(self.editor); edit.setContentsMargins(0,0,0,0); edit.setSpacing(6)
        form=QFormLayout(); self.name=QLineEdit(self.project.name); self.name.setAccessibleName('Mil parça adı')
        form.addRow('Parça adı',self.name); edit.addLayout(form)
        self.summary=label('', 'subtitle'); edit.addWidget(self.summary)
        self.tabs=QTabWidget(); self.tabs.setUsesScrollButtons(True)
        stage_page=QWidget(); stages=QVBoxLayout(stage_page); stages.setContentsMargins(4,6,4,4)
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(['Kademe','Çap · mm','Boy · mm'])
        self.table.verticalHeader().hide(); self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setMinimumHeight(150); self.table.setAccessibleName('Düzenlenebilir mil kademeleri')
        stages.addWidget(self.table,1)
        commands=QHBoxLayout(); commands.setSpacing(3)
        for text,callback in (('+',lambda:self.add_stage()),('Kopyala',lambda:self.add_stage(copy=True)),
                               ('Sil',self.delete_stage),('↑',lambda:self.move_stage(-1)),('↓',lambda:self.move_stage(1))):
            control=button(text,callback); control.setMinimumWidth(0)
            control.setAccessibleName({'+':'Kademe ekle','↑':'Kademeyi yukarı taşı','↓':'Kademeyi aşağı taşı'}.get(text,'Kademe '+text.lower()))
            commands.addWidget(control)
        stages.addLayout(commands); self.tabs.addTab(stage_page,'Kademeler')
        self.operation_fields={}; self.operation_targets={}; self.standard_pickers={}; self.loading_operation=False
        for kind,constructor in (('groove',Groove),('keyway',Keyway),('chamfer',Chamfer),('fillet',Fillet)):
            page=QWidget(); box=QVBoxLayout(page); box.setContentsMargins(6,6,6,6)
            form=QFormLayout(); form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            target=QComboBox(); target.setAccessibleName(TITLES[kind]+' hedef kademesi')
            self.operation_targets[kind]=target; form.addRow('Hedef kademe',target)
            if kind in ('groove','keyway'):
                picker=ChannelStandardPicker(kind,context.appearance)
                picker.valuesSelected.connect(lambda values,k=kind:self.apply_standard(k,values))
                self.standard_pickers[kind]=picker;form.addRow(picker)
            prototype=constructor(self.selected_stage); controls={}
            for field in fields(prototype):
                key=field.name
                if key in ('id','kind','stage_id'):continue
                if key=='edge':
                    control=QComboBox();control.addItem('Sol kenar','left');control.addItem('Sağ kenar','right')
                    form.addRow('Hedef kenar',control)
                else:
                    control=QDoubleSpinBox();control.setDecimals(4);control.setRange(0,1_000_000)
                    title='Toplam boy · mm' if kind=='keyway' and key=='length' else FIELD_TITLES[key]
                    control.setValue(getattr(prototype,key));form.addRow(title,control)
                    if key=='angle':
                        # Unsupported orientations/angles cannot masquerade as working CAD.
                        control.setEnabled(False)
                control.setAccessibleName(TITLES[kind]+' '+FIELD_TITLES.get(key,'Hedef kenar'))
                controls[key]=control
            self.operation_fields[kind]=controls;box.addLayout(form)
            if kind=='keyway':box.addWidget(label('İki uç yarım daire: R = genişlik / 2. Boy, uçtan uca toplamdır. Açı 0°.','muted'))
            if kind=='chamfer':box.addWidget(label('Bu sürümde 45° eş mesafeli pah.','muted'))
            actions=QHBoxLayout();actions.addWidget(button('Ekle',lambda checked=False,k=kind:self.add_operation(k)))
            actions.addWidget(button('Seçileni güncelle',lambda checked=False,k=kind:self.update_operation(k)))
            box.addLayout(actions);box.addStretch()
            self.tabs.addTab(scroll(page),TITLES[kind])
        advanced=label('Merkez deliği, diş, freze düzlüğü, delik ve omuz boşaltması henüz desteklenmiyor.','muted')
        self.tabs.addTab(advanced,'İleri'); self.tabs.setTabEnabled(self.tabs.count()-1,False)
        edit.addWidget(self.tabs,2)
        edit.addWidget(label('OPERASYONLAR','section'))
        self.operations=QListWidget();self.operations.setMinimumHeight(60);self.operations.setMaximumHeight(140)
        self.operations.setAccessibleName('Mil operasyonları');edit.addWidget(self.operations,1)
        self.remove_operation_button=button('Seçili operasyonu sil',self.delete_operation);edit.addWidget(self.remove_operation_button)
        wall=QFormLayout();self.minimum_wall=QDoubleSpinBox();self.minimum_wall.setDecimals(3)
        self.minimum_wall.setRange(.001,100000);self.minimum_wall.setValue(self.project.minimum_wall)
        self.minimum_wall.setAccessibleName('En az kalan radyal et kalınlığı');wall.addRow('En az radyal et · mm',self.minimum_wall)
        edit.addLayout(wall)
        self.source_scroll=scroll(self.editor);self.source_scroll.setMinimumWidth(290)
        self.source_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.source_scroll.setMaximumWidth(490);self.splitter.addWidget(self.source_scroll)
        views=QWidget();view_box=QVBoxLayout(views);view_box.setContentsMargins(0,0,0,0);view_box.setSpacing(2)
        self.top_view=ShaftPreview();self.section_view=ShaftPreview(section=True)
        for view in (self.top_view,self.section_view):
            view.stageSelected.connect(self.select_stage);view.operationSelected.connect(self.select_operation)
            view_box.addWidget(view,1)
        self.splitter.addWidget(views);self.splitter.setStretchFactor(1,1);self.splitter.setSizes([370,850])
        self.layout.addWidget(self.splitter,1)
        self.validation_label=label('','muted');self.validation_label.setMaximumHeight(60);self.layout.addWidget(self.validation_label)
        footer=QHBoxLayout();self.create_button=button("SOLIDWORKS'TE ÇİZ",self.create_model,primary=True)
        self.create_button.setAccessibleName('Yeni parametrik SOLIDWORKS parçası oluştur')
        self.save_part_button=button('SLDPRT oluştur ve kaydet…',self.create_and_save)
        self.stop_button=button('Durdur',self.jobs.cancel);self.stop_button.hide()
        footer.addWidget(self.create_button);footer.addWidget(self.save_part_button);footer.addStretch();footer.addWidget(self.stop_button)
        self.layout.addLayout(footer);self.finish_layout()
        self.controls.extend([self.source_scroll,self.create_button,self.save_part_button])
        self.name.textChanged.connect(self.name_changed);self.minimum_wall.valueChanged.connect(self.wall_changed)
        self.table.cellChanged.connect(self.cell_changed);self.table.itemSelectionChanged.connect(self.table_selected)
        self.operations.currentItemChanged.connect(self.operation_selected)
        for kind,controls in self.operation_fields.items():
            for control in (self.operation_targets[kind],*controls.values()):
                signal=control.currentIndexChanged if isinstance(control,QComboBox) else control.valueChanged
                signal.connect(lambda *args,k=kind:self.operation_form_changed(k))
        self.populate();self.refresh()

    def populate(self):
        with QSignalBlocker(self.name):self.name.setText(self.project.name)
        with QSignalBlocker(self.minimum_wall):self.minimum_wall.setValue(self.project.minimum_wall)
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(self.project.stages))
            for row,stage in enumerate(self.project.stages):
                for col,value in enumerate((row+1,stage.diameter,stage.length)):
                    item=QTableWidgetItem(f'{value:g}');item.setData(Qt.UserRole,stage.id)
                    if col==0:item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignCenter);self.table.setItem(row,col,item)
        for target in self.operation_targets.values():
            previous=target.currentData()
            with QSignalBlocker(target):
                target.clear()
                for i,stage in enumerate(self.project.stages,1):target.addItem(f'{i}. kademe · Ø{stage.diameter:g}',stage.id)
                index=target.findData(previous or self.selected_stage);target.setCurrentIndex(max(index,0))
        with QSignalBlocker(self.operations):
            self.operations.clear()
            for op in self.project.operations:
                index=next(i for i,s in enumerate(self.project.stages,1) if s.id==op.stage_id)
                item=QListWidgetItem(f'{TITLES[op.kind]} · {index}. kademe');item.setData(Qt.UserRole,op.id)
                self.operations.addItem(item)
        self.select_stage(self.selected_stage)
        if self.selected_operation:self.select_operation(self.selected_operation)

    def refresh(self, *, changed=False):
        if changed:self.dirty=True;self.last_result=None
        errors=validate(self.project)
        self.plan=[] if errors else operation_plan(self.project)
        self.create_button.setEnabled(not self.busy and not errors)
        self.save_part_button.setEnabled(not self.busy and not errors)
        self.save_button.setEnabled(not self.busy and not errors)
        self.summary.setText('Ölçü hatası' if errors else f'{len(self.project.stages)} kademe · L {self.project.total_length:g} mm · Ømaks {self.project.maximum_diameter:g} mm')
        self.validation_label.setText('\n'.join(errors) if errors else 'Ölçüler geçerli · Yeni parça oluşturulur · Önizleme boyut oranlarını korur')
        self.validation_label.setToolTip('\n'.join(errors));self.validation_label.setProperty('role','error' if errors else 'muted')
        self.validation_label.style().unpolish(self.validation_label);self.validation_label.style().polish(self.validation_label)
        for view in (self.top_view,self.section_view):view.set_project(self.project,self.selected_stage,self.selected_operation)
        self.refresh_standards()

    def refresh_standards(self):
        for kind,picker in self.standard_pickers.items():
            values=self.operation_values(kind)
            stage=next((s for s in self.project.stages if s.id==values['stage_id']),None)
            if stage is not None:picker.set_context(stage.diameter,stage.length,values)

    def apply_standard(self,kind,values):
        # Apply the related dimensions as one edit, never transient half-presets.
        for key,value in values.items():
            control=self.operation_fields[kind][key]
            with QSignalBlocker(control):control.setValue(value)
        self.operation_form_changed(kind)
        self.refresh_standards()

    def name_changed(self,value):self.project.name=value;self.refresh(changed=True)
    def wall_changed(self,value):self.project.minimum_wall=value;self.refresh(changed=True)

    def cell_changed(self,row,col):
        if col not in (1,2):return
        text=self.table.item(row,col).text().replace(',','.').strip()
        try:value=float(text)
        except ValueError:value=float('nan')
        setattr(self.project.stages[row],'diameter' if col==1 else 'length',value)
        self.refresh(changed=True)

    def table_selected(self):
        row=self.table.currentRow()
        if 0<=row<len(self.project.stages):self.select_stage(self.project.stages[row].id)

    def select_stage(self,stage_id):
        row=next((i for i,s in enumerate(self.project.stages) if s.id==stage_id),None)
        if row is None:return
        op=next((o for o in self.project.operations if o.id==self.selected_operation),None)
        if op is not None and op.stage_id!=stage_id:
            self.selected_operation=''
            with QSignalBlocker(self.operations):self.operations.setCurrentRow(-1)
        self.selected_stage=stage_id
        with QSignalBlocker(self.table):self.table.selectRow(row)
        for target in self.operation_targets.values():
            with QSignalBlocker(target):target.setCurrentIndex(target.findData(stage_id))
        self.refresh()

    def add_stage(self, *, copy=False):
        self.selected_stage=self.project.add_stage(self.selected_stage,copy=copy)
        self.populate();self.refresh(changed=True)

    def delete_stage(self):
        attached=sum(op.stage_id==self.selected_stage for op in self.project.operations)
        if attached and QMessageBox.question(self,'Kademeyi sil',f'Bu kademeye bağlı {attached} operasyon da silinecek. Devam edilsin mi?',
                                             QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:self.project.remove_stage(self.selected_stage)
        except ValueError as error:self.set_status(str(error),True);return
        self.selected_stage=self.project.stages[0].id;self.selected_operation=''
        self.populate();self.refresh(changed=True)

    def move_stage(self,direction):
        self.project.move_stage(self.selected_stage,direction);self.populate();self.refresh(changed=True)

    def operation_values(self,kind):
        return dict(stage_id=self.operation_targets[kind].currentData(),**{
            key:control.currentData() if isinstance(control,QComboBox) else control.value()
            for key,control in self.operation_fields[kind].items()})

    def add_operation(self,kind):
        constructor={'groove':Groove,'keyway':Keyway,'chamfer':Chamfer,'fillet':Fillet}[kind]
        operation=constructor(**self.operation_values(kind))
        self.project.operations.append(operation);self.selected_operation=operation.id
        self.populate();self.refresh(changed=True)

    def update_operation(self,kind):
        op=next((o for o in self.project.operations if o.id==self.selected_operation),None)
        if op is None or op.kind!=kind:self.set_status('Önce aynı türden bir operasyon seçin.',True);return
        for key,value in self.operation_values(kind).items():setattr(op,key,value)
        self.populate();self.refresh(changed=True)

    def operation_form_changed(self,kind):
        if self.loading_operation:return
        op=next((o for o in self.project.operations if o.id==self.selected_operation),None)
        if op is None or op.kind!=kind:
            self.refresh_standards();return
        for key,value in self.operation_values(kind).items():setattr(op,key,value)
        self.selected_stage=op.stage_id
        self.populate();self.refresh(changed=True)

    def delete_operation(self):
        self.project.operations[:]=[o for o in self.project.operations if o.id!=self.selected_operation]
        self.selected_operation='';self.populate();self.refresh(changed=True)

    def operation_selected(self,item,previous):
        if item:self.select_operation(item.data(Qt.UserRole))

    def select_operation(self,operation_id):
        op=next((o for o in self.project.operations if o.id==operation_id),None)
        if op is None:return
        self.selected_operation=op.id;self.select_stage(op.stage_id)
        with QSignalBlocker(self.operations):
            for i in range(self.operations.count()):
                if self.operations.item(i).data(Qt.UserRole)==op.id:self.operations.setCurrentRow(i)
        self.loading_operation=True
        try:
            for key,control in self.operation_fields[op.kind].items():
                value=getattr(op,key)
                control.setCurrentIndex(control.findData(value)) if isinstance(control,QComboBox) else control.setValue(value)
        finally:self.loading_operation=False
        self.tabs.setCurrentIndex(list(TITLES).index(op.kind)+1);self.refresh()

    def confirm_discard(self):
        return not self.dirty or QMessageBox.question(self,'Kaydedilmemiş mil projesi','Kaydedilmemiş parametreler değiştirilsin mi?',
                    QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes

    def confirm_close(self):
        if not self.dirty:return True
        answer=QMessageBox.warning(self,'Kaydedilmemiş mil projesi',
            'Mil parametrelerinde kaydedilmemiş değişiklikler var. Çıkmadan önce kaydedilsin mi?',
            QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Cancel)
        if answer==QMessageBox.Save:return self.save_dialog()
        return answer==QMessageBox.Discard

    def open_dialog(self):
        if not self.confirm_discard():return
        path,_=QFileDialog.getOpenFileName(self,'Mil projesi aç','','Mil projesi (*.gokshaft.json *.json)')
        if not path:return
        try:project=storage.load(path)
        except (OSError,ValueError) as error:self.set_status(str(error),True);return
        self.project=project;self.project_path=Path(path);self.dirty=False;self.last_result=None
        self.selected_stage=project.stages[0].id;self.selected_operation=''
        self.populate();self.refresh();self.set_status('Mil projesi açıldı.')

    def save_dialog(self):
        path,_=QFileDialog.getSaveFileName(self,'Mil parametrelerini kaydet',str(self.project_path or (self.project.name+'.gokshaft.json')),
                                         'Mil projesi (*.gokshaft.json)',options=QFileDialog.DontConfirmOverwrite)
        if not path:return False
        try:
            try:storage.save(self.project,path)
            except FileExistsError:
                # The dialog may have been open while another process created
                # the target. Never infer authorization merely from exists().
                digest=storage.fingerprint(path)
                if QMessageBox.question(self,'Mevcut mil projesi',
                    'Seçilen JSON dosyası zaten var. Bu dosyanın üzerine yazılsın mı?',
                    QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return False
                storage.save(self.project,path,overwrite=True,expected_digest=digest)
        except (OSError,ValueError) as error:self.set_status(str(error),True);return False
        self.project_path=Path(path);self.dirty=False;self.set_status('Mil parametreleri JSON olarak kaydedildi.')
        return True

    def create_and_save(self):
        path,_=QFileDialog.getSaveFileName(self,'Yeni SLDPRT kaydet',self.project.name+'.SLDPRT','SOLIDWORKS parçası (*.SLDPRT)')
        if not path:return
        if Path(path).exists():self.set_status('Mevcut SLDPRT üzerine yazılmaz. Yeni bir dosya adı seçin.',True);return
        self.create_model(output_path=path)

    def create_model(self, *, output_path=''):
        if not self.can_start():return
        errors=validate(self.project)
        if errors:self.set_status('\n'.join(errors),True);return
        snapshot=deepcopy(self.project)
        self.set_status('SOLIDWORKS işlemi hazırlanıyor…')
        self.jobs.start(self,lambda events,stop:controller.create(snapshot,events,stop,output_path=output_path))

    def handle_events(self,events):
        for kind,value in events:
            if kind=='shaft_phase':self.set_status(value)
            elif kind=='shaft_cancelled':self.set_status('İşlem başlamadan durduruldu.')
            elif kind=='shaft_created':
                self.last_result=value
                self.set_status(f"{value['document']} oluşturuldu · {value['feature_count']} yerel özellik · Rebuild başarılı")
        # Worker batches can contain both the initial phase and job_error.
        # Errors must win over an older phase, including when startup fails.
        super().handle_events(events)

    def set_busy(self,busy):
        super().set_busy(busy);self.refresh()

    def theme_changed(self):
        for picker in self.standard_pickers.values():picker.set_appearance(self.context.appearance)
        for view in (self.top_view,self.section_view):view.appearance=self.context.appearance;view.update()
