"""GOKWORKS BasePage: stage editor, native operations and two linked views."""

from copy import deepcopy
from dataclasses import fields
from pathlib import Path

from PySide6.QtCore import Qt, QSignalBlocker, QLocale
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QSplitter,
    QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QTabWidget,
    QLineEdit,QComboBox,QDoubleSpinBox,QListWidget,QListWidgetItem,QFileDialog,QMessageBox,QCheckBox)
from gui_qt.components import BasePage, label, button, scroll
from . import controller, storage
from .geometry import operation_plan
from .models import Project, Groove, Keyway, Chamfer, Fillet, Bore, CosmeticThread
from .preview import ShaftPreview
from .standard_picker import ChannelStandardPicker
from .validation import validate
from .edge_treatments import circular_edges, plan_treatments


TITLES = {'groove':'Segman kanalı','keyway':'Kama kanalı','chamfer':'Pah','fillet':'Radyüs','cosmetic_thread':'Kozmetik diş'}
FIELD_TITLES = {'offset':'Kademede başlangıç · mm','width':'Kanal genişliği · mm','length':'Boy · mm','depth':'Yüzeyden derinlik · mm',
                'angle':'Açı · °','distance':'Mesafe · mm','radius':'Radyüs · mm','pitch':'Diş adımı · mm'}


class ShaftPage(BasePage):
    def __init__(self,context):
        super().__init__(context,'Parametrik mil','Kademeleri ve operasyonları düzenleyin; iki görünüş aynı ölçüleri kullanır.')
        # Reserve native Windows font/frame overhead at 550×450 without
        # reducing either technical view's 170 px minimum or clipping commands.
        self.layout.setContentsMargins(10,2,10,2);self.layout.setSpacing(2)
        self.project=Project(); self.selected_stage=self.project.stages[0].id
        self.selected_operation=''; self.project_path=None; self.dirty=False
        self.plan=[]; self.last_result=None; self.edge_undo=None; self.save_epoch=0
        self.open_button=self.action('Proje aç',self.open_dialog)
        self.save_button=self.action('Proje kaydet',self.save_dialog)
        self.splitter=QSplitter(Qt.Horizontal); self.splitter.setChildrenCollapsible(False)
        self.editor=QWidget(); self.editor.setMinimumWidth(280); self.editor.setMaximumWidth(480)
        edit=QVBoxLayout(self.editor); edit.setContentsMargins(0,0,0,0); edit.setSpacing(6)
        edit.addWidget(label('MİL PARAMETRELERİ','section'))
        form=QFormLayout(); self.name=QLineEdit(self.project.name); self.name.setAccessibleName('Mil parça adı')
        form.addRow('Parça adı',self.name); edit.addLayout(form)
        self.summary=label('', 'subtitle'); edit.addWidget(self.summary)
        self.selected_stage_caption=label('','muted');edit.addWidget(self.selected_stage_caption)
        self.section_picker=QComboBox();self.section_picker.setAccessibleName('Mil parametre bölümü')
        self.section_picker.setMinimumWidth(0);self.section_picker.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.section_picker.setMinimumContentsLength(12);edit.addWidget(self.section_picker)
        self.bulk_shortcut=button('Toplu pah / radyüs…',self.show_bulk_treatments)
        self.bulk_shortcut.setToolTip('Mil uçları ve kademe omuzlarını tek işlemle düzenleyin.')
        edit.addWidget(self.bulk_shortcut)
        self.edit_mode=label('','section');edit.addWidget(self.edit_mode)
        self.new_operation_button=button('Seçimi temizle · Yeni işlem',self.clear_operation_selection)
        edit.addWidget(self.new_operation_button)
        self.tabs=QTabWidget(); self.tabs.tabBar().hide();self.tabs.setDocumentMode(True)
        self.tabs.setMinimumWidth(0)

        stage_page=QWidget(); stages=QVBoxLayout(stage_page); stages.setContentsMargins(4,6,4,4)
        stages.addWidget(label('Çap ve boy hücrelerine yazın. Kademeler soldan sağa sıralanır.','muted'))
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(['Kademe','Çap · mm','Boy · mm'])
        self.table.verticalHeader().hide(); self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setMinimumHeight(150); self.table.setAccessibleName('Düzenlenebilir mil kademeleri')
        stages.addWidget(self.table,1)
        commands=QHBoxLayout(); commands.setSpacing(3)
        for text,callback in (('+ Kademe',lambda:self.add_stage()),('Kopyala',lambda:self.add_stage(copy=True)),
                               ('Sil',self.delete_stage),('↑',lambda:self.move_stage(-1)),('↓',lambda:self.move_stage(1))):
            control=button(text,callback); control.setMinimumWidth(0)
            control.setAccessibleName({'+ Kademe':'Kademe ekle','↑':'Kademeyi yukarı taşı','↓':'Kademeyi aşağı taşı'}.get(text,'Kademe '+text.lower()))
            commands.addWidget(control)
        stages.addLayout(commands); self.tabs.addTab(stage_page,'Kademeler')
        self.operation_fields={}; self.operation_targets={}; self.standard_pickers={}; self.loading_operation=False
        self.add_operation_buttons={};self.update_operation_buttons={};self.operation_hints={};self.operation_actions={}
        for kind,constructor in (('groove',Groove),('keyway',Keyway),('chamfer',Chamfer),('fillet',Fillet),('cosmetic_thread',CosmeticThread)):
            page=QWidget(); box=QVBoxLayout(page); box.setContentsMargins(6,6,6,6)
            self.operation_hints[kind]=label('','muted');box.addWidget(self.operation_hints[kind])
            form=QFormLayout(); form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

            target=QComboBox(); target.setAccessibleName(TITLES[kind]+' hedef kademesi')
            self.operation_targets[kind]=target; form.addRow('Uygulanacak kademe',target)
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
                    control=QDoubleSpinBox();control.setLocale(QLocale('tr_TR'));control.setDecimals(4);control.setRange(0,1_000_000)
                    control.setMinimumWidth(100);control.setKeyboardTracking(False)
                    title='Toplam boy · mm' if kind=='keyway' and key=='length' else FIELD_TITLES[key]
                    control.setValue(getattr(prototype,key));form.addRow(title,control)
                    if key=='angle':
                        # Unsupported orientations/angles cannot masquerade as working CAD.
                        control.setEnabled(False)
                if key=='offset':control.setToolTip('Seçilen kademenin sol başlangıcından kanalın başlangıcına kadar mesafe; tüm milin başlangıcı değildir.')
                elif key=='depth':control.setToolTip('Silindirin dış yüzeyinden kanal tabanına radyal derinlik; mm.')
                elif key=='length' and kind=='keyway':control.setToolTip('Yuvarlak uçlar dahil kanalın uçtan uca toplam boyu; mm.')
                control.setAccessibleName(TITLES[kind]+' '+FIELD_TITLES.get(key,'Hedef kenar'))
                controls[key]=control
            self.operation_fields[kind]=controls;box.addLayout(form)
            if kind=='keyway':box.addWidget(label('İki uç yarım daire: R = genişlik / 2. Boy, uçtan uca toplamdır. Açı 0°.','muted'))
            if kind in ('chamfer','fillet'):
                box.addWidget(label('Ekle sonrası diğer kenarı seçip yeni operasyon ekleyin. Düzenlemek için listeden seçin.','muted'))
            if kind=='chamfer':box.addWidget(label('Bu sürümde 45° eş mesafeli pah.','muted'))
            if kind=='cosmetic_thread':
                self.thread_caption=label('','muted');box.addWidget(self.thread_caption)
                box.addWidget(label('Metrik sağ diş. Kozmetik gösterimdir; katı hacmi değişmez. Boy, pah/radyüs sonrası silindirik yüzeyden başlar.','muted'))
            action_bar=QWidget();actions=QHBoxLayout(action_bar);actions.setContentsMargins(0,0,0,0)
            add=button('İşlemi ekle',lambda checked=False,k=kind:self.add_operation(k))
            update=button('Seçiliyi güncelle',lambda checked=False,k=kind:self.update_operation(k))
            self.add_operation_buttons[kind]=add;self.update_operation_buttons[kind]=update
            self.operation_actions[kind]=action_bar
            actions.addWidget(add);actions.addWidget(update)
            box.addStretch()
            self.tabs.addTab(scroll(page),TITLES[kind])
        bore_page=QWidget();bore_box=QVBoxLayout(bore_page)
        self.bore_enabled=QCheckBox('Eksenel iç delik aç');self.bore_enabled.setAccessibleName('Mil iç deliğini etkinleştir')
        bore_box.addWidget(self.bore_enabled);bore_form=QFormLayout();bore_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.bore_controls={};self.loading_bore=False
        for key,title in (('diameter','İç çap · mm'),('end_condition','Sonlandırma'),('entry','Giriş'),('depth','Kör delik boyu · mm')):
            if key in ('diameter','depth'):
                control=QDoubleSpinBox();control.setLocale(QLocale('tr_TR'));control.setDecimals(4)
                control.setKeyboardTracking(False);control.setRange(.0001,1_000_000);control.setValue(getattr(Bore(),key))
            else:
                control=QComboBox()
                for text,value in ((('Boydan boya','through_all'),('Kör delik','blind')) if key=='end_condition' else (('Soldan','left'),('Sağdan','right'))):
                    control.addItem(text,value)
            control.setAccessibleName('İç delik '+title);self.bore_controls[key]=control;bore_form.addRow(title,control)
        bore_box.addLayout(bore_form)
        bore_box.addWidget(label('Tek eksenli silindirik delik. Kör delik tabanı düzdür. Et kalınlığı, segman ve kama derinlikleriyle birlikte kontrol edilir.','muted'))
        bore_box.addStretch();self.tabs.addTab(scroll(bore_page),'İç delik')
        self.build_bulk_page()
        advanced=label('Matkap uç konisi, iç diş, gerçek helisel diş, freze düzlüğü ve omuz boşaltması henüz desteklenmiyor.','muted')
        self.tabs.addTab(advanced,'İleri'); self.tabs.setTabEnabled(self.tabs.count()-1,False)
        for index,title in enumerate(('1 · Kademe ölçüleri','Segman kanalı','Kama kanalı','Tek kenara pah',
                                      'Tek kenara radyüs','Kozmetik diş','Eksenel iç delik','Toplu pah / radyüs')):
            self.section_picker.addItem(title,index)
        self.section_picker.currentIndexChanged.connect(lambda:self.tabs.setCurrentIndex(self.section_picker.currentData()))
        self.tabs.currentChanged.connect(self.section_changed)
        edit.addWidget(self.tabs,2)
        for action_bar in self.operation_actions.values():edit.addWidget(action_bar)
        self.operation_count=label('EKLENEN İŞLEMLER · 0','section');edit.addWidget(self.operation_count)
        self.operations=QListWidget();self.operations.setMinimumHeight(72);self.operations.setMaximumHeight(140)
        self.operations.setAlternatingRowColors(True)
        self.operations.setToolTip('İşlemi seçin: parametrelerini düzenleyin. Tekil işlemlerin ölçü değişiklikleri anında uygulanır.')
        self.operations.setAccessibleName('Mil operasyonları');edit.addWidget(self.operations,1)
        self.remove_operation_button=button('Seçili operasyonu sil',self.delete_operation);edit.addWidget(self.remove_operation_button)
        wall=QFormLayout();self.minimum_wall=QDoubleSpinBox();self.minimum_wall.setLocale(QLocale('tr_TR'));self.minimum_wall.setDecimals(3)
        self.minimum_wall.setKeyboardTracking(False)
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
        self.bore_enabled.toggled.connect(self.bore_changed)
        for control in self.bore_controls.values():
            signal=control.currentIndexChanged if isinstance(control,QComboBox) else control.valueChanged
            signal.connect(self.bore_changed)
        for kind,controls in self.operation_fields.items():
            for control in (self.operation_targets[kind],*controls.values()):
                signal=control.currentIndexChanged if isinstance(control,QComboBox) else control.valueChanged
                signal.connect(lambda *args,k=kind:self.operation_form_changed(k))
        self.populate();self.refresh()

    def build_bulk_page(self):
        page=QWidget();box=QVBoxLayout(page);box.setContentsMargins(6,6,6,6)
        box.addWidget(label('TÜM UÇLAR VE OMUZLAR','section'))
        box.addWidget(label('Milin iki ucu ve kademeler arasındaki dairesel omuz kenarları birlikte işlenir.', 'muted'))
        form=QFormLayout();form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.bulk_kind=QComboBox();self.bulk_kind.addItem('Pah · 45°','chamfer');self.bulk_kind.addItem('Radyüs','fillet')
        self.bulk_kind.setAccessibleName('Toplu kenar işlemi türü')
        form.addRow('Uygulanacak işlem',self.bulk_kind)
        self.bulk_size=QDoubleSpinBox();self.bulk_size.setLocale(QLocale('tr_TR'))
        self.bulk_size.setDecimals(4);self.bulk_size.setRange(.0001,1_000_000);self.bulk_size.setValue(1)
        self.bulk_size.setKeyboardTracking(False);self.bulk_size.setAccessibleName('Toplu pah mesafesi veya radyüs ölçüsü · mm')
        self.bulk_size_label=label('Pah mesafesi · mm');form.addRow(self.bulk_size_label,self.bulk_size);box.addLayout(form)
        self.bulk_replace=QCheckBox('Mevcut pah/radyüsleri de değiştir')
        self.bulk_replace.setToolTip('Kapalıyken mevcut kenar işlemleri korunur; yalnız boş kenarlara eklenir.')
        box.addWidget(self.bulk_replace)
        self.bulk_info=label('','muted');box.addWidget(self.bulk_info)
        self.bulk_button=button('Tüm uç ve omuzlara uygula',self.apply_bulk_treatments,primary=True)
        box.addWidget(self.bulk_button)
        self.edge_undo_button=button('Son toplu uygulamayı geri al',self.undo_bulk_treatments)
        self.edge_undo_button.setToolTip('GOKWORKS parametre listesini geri alır. Oluşturulmuş SolidWorks dosyaları değiştirilmez.')
        self.edge_undo_button.setEnabled(False);box.addWidget(self.edge_undo_button)
        box.addWidget(label('Ölçü bir kenara sığmazsa hiçbir işlem değiştirilmez. Eş çaplı birleşimlerde fiziksel omuz yoktur.', 'muted'))
        box.addWidget(label('Katı modeli üretmek için ardından SOLIDWORKS’TE ÇİZ düğmesini kullanın.', 'muted'))
        box.addStretch();self.tabs.addTab(scroll(page),'Toplu pah / radyüs')
        self.bulk_kind.currentIndexChanged.connect(self.refresh_bulk_info)
        self.bulk_size.valueChanged.connect(self.refresh_bulk_info)
        self.bulk_replace.toggled.connect(self.refresh_bulk_info)

    def section_changed(self,index):
        selected=self.section_picker.findData(index)
        if selected>=0:
            with QSignalBlocker(self.section_picker):self.section_picker.setCurrentIndex(selected)
        if hasattr(self,'validation_label'):
            op=next((op for op in self.project.operations if op.id==self.selected_operation),None)
            kind=list(TITLES)[index-1] if 1<=index<=5 else None
            if op is not None and op.kind!=kind:self.clear_operation_selection()
            self.refresh_editor_context()

    def show_bulk_treatments(self):
        self.clear_operation_selection()
        self.tabs.setCurrentIndex(7)
        self.source_scroll.ensureWidgetVisible(self.section_picker)

    def clear_operation_selection(self):
        self.selected_operation=''
        with QSignalBlocker(self.operations):self.operations.setCurrentRow(-1)
        if hasattr(self,'validation_label'):self.refresh()

    def refresh_editor_context(self):
        row=next((i for i,s in enumerate(self.project.stages,1) if s.id==self.selected_stage),None)
        if row is not None:
            stage=self.project.stage(self.selected_stage)
            self.selected_stage_caption.setText(f'Seçili: {row}. kademe · Ø{stage.diameter:g} · Boy {stage.length:g} mm')
        op=next((op for op in self.project.operations if op.id==self.selected_operation),None)
        is_single=1<=self.tabs.currentIndex()<=5
        self.edit_mode.setVisible(is_single)
        self.new_operation_button.setVisible(is_single and op is not None)
        self.edit_mode.setText('Seçili işlem düzenleniyor' if op is not None else 'Yeni işlem ekle')
        self.operation_count.setText(f'EKLENEN İŞLEMLER · {len(self.project.operations)}')
        self.operations.setFixedHeight(max(72,min(148,len(self.project.operations)*28+8)))
        self.bulk_shortcut.setVisible(self.tabs.currentIndex()!=7)
        self.remove_operation_button.setEnabled(not self.busy and op is not None)
        for kind in self.operation_fields:
            self.operation_actions[kind].setVisible(is_single and list(TITLES)[self.tabs.currentIndex()-1]==kind)
            editing=op is not None and op.kind==kind
            self.add_operation_buttons[kind].setEnabled(not self.busy and not editing)
            self.update_operation_buttons[kind].setEnabled(not self.busy and editing)
            self.operation_hints[kind].setText('Alanlardaki değişiklikler seçili işleme anında uygulanır.' if editing
                                              else 'Kademeyi ve ölçüleri seçin; İşlemi ekle düğmesine basın.')
        self.refresh_bulk_info()
        self.edge_undo_button.setEnabled(not self.busy and self.edge_undo is not None
                                         and self.project.to_dict()==self.edge_undo[1])

    def refresh_bulk_info(self,*args):
        kind=self.bulk_kind.currentData()
        self.bulk_size_label.setText('Pah mesafesi · mm' if kind=='chamfer' else 'Radyüs · mm')
        try:
            edges=circular_edges(self.project)
        except ValueError:
            self.bulk_info.setText('Önce kademe ölçülerini ve iç deliği düzeltin.');return
        occupied={(op.stage_id,op.edge) for op in self.project.operations if isinstance(op,(Chamfer,Fillet))}
        existing=sum((edge.stage_id,edge.side) in occupied for edge in edges)
        text=f'{len(edges)} gerçek kenar · {existing} mevcut pah/radyüs'
        if self.bulk_replace.isChecked():text+=f'\n{len(edges)-existing} yeni, {existing} güncelleme hazırlanacak.'
        else:text+=f'\n{len(edges)-existing} boş kenara eklenecek; mevcutlar korunur.'
        self.bulk_info.setText(text)

    def apply_bulk_treatments(self):
        if not self.can_start():return
        try:
            batch=plan_treatments(self.project,self.bulk_kind.currentData(),self.bulk_size.value(),
                                  replace_existing=self.bulk_replace.isChecked())
        except ValueError as error:
            self.set_status('Toplu kenar işlemi uygulanamadı; mevcut işlemler korundu.\n'+str(error),True);return
        before=deepcopy(self.project);after=batch.project.to_dict()
        if before.to_dict()==after:
            self.set_status(f'{batch.preserved} kenarda zaten pah/radyüs var. Değiştirmek için Mevcut pah/radyüsleri de değiştir seçeneğini açın.')
            return
        self.edge_undo=(before,after,self.dirty,self.save_epoch)
        self.project=batch.project;self.selected_operation=''
        self.populate();self.refresh(changed=True)
        self.set_status(f'Toplu işlem tamamlandı · {batch.added} yeni · {batch.updated} güncellendi · {batch.preserved} korundu'
                        +(f' · {batch.straight_joints} eş çap birleşiminde omuz yok.' if batch.straight_joints else '.'))

    def undo_bulk_treatments(self):
        if not self.can_start():return
        if self.edge_undo is None or self.project.to_dict()!=self.edge_undo[1]:
            self.set_status('Toplu uygulamadan sonra parametreler değişti; sonraki düzenlemeler geri alınmadı.',True);return
        before,_,previous_dirty,saved_epoch=self.edge_undo
        self.project=before;self.dirty=previous_dirty if saved_epoch==self.save_epoch else True
        self.edge_undo=None;self.selected_operation='';self.last_result=None
        self.populate();self.refresh();self.set_status('Son toplu pah/radyüs uygulaması geri alındı.')

    def populate(self):
        with QSignalBlocker(self.name):self.name.setText(self.project.name)
        with QSignalBlocker(self.minimum_wall):self.minimum_wall.setValue(self.project.minimum_wall)
        self.loading_bore=True
        try:
            self.bore_enabled.setChecked(self.project.bore is not None)
            bore=self.project.bore or Bore()
            for key,control in self.bore_controls.items():
                value=getattr(bore,key)
                control.setCurrentIndex(control.findData(value)) if isinstance(control,QComboBox) else control.setValue(value)
        finally:self.loading_bore=False
        self.update_bore_controls()
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
                detail=''
                if isinstance(op,(Chamfer,Fillet)):
                    side='Sol' if op.edge=='left' else 'Sağ'
                    size=op.distance if isinstance(op,Chamfer) else op.radius
                    detail=f' · {side} · {size:g} mm'
                elif isinstance(op,CosmeticThread):
                    side='Sol' if op.edge=='left' else 'Sağ'
                    detail=f' · M{self.project.stage(op.stage_id).diameter:g}×{op.pitch:g} · {side} · {op.length:g} mm'
                item=QListWidgetItem(f'{TITLES[op.kind]} · {index}. kademe{detail}');item.setData(Qt.UserRole,op.id)
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
        self.refresh_thread_caption()
        self.refresh_editor_context()

    def update_bore_controls(self):
        enabled=self.bore_enabled.isChecked()
        blind=self.bore_controls['end_condition'].currentData()=='blind'
        for key,control in self.bore_controls.items():control.setEnabled(enabled and (key not in ('depth','entry') or blind))

    def bore_changed(self,*args):
        if self.loading_bore:return
        self.project.bore=Bore(**{key:control.currentData() if isinstance(control,QComboBox) else control.value()
                                 for key,control in self.bore_controls.items()}) if self.bore_enabled.isChecked() else None
        self.update_bore_controls();self.refresh(changed=True)

    def refresh_thread_caption(self):
        values=self.operation_values('cosmetic_thread')
        stage=next((s for s in self.project.stages if s.id==values['stage_id']),None)
        if stage is not None:self.thread_caption.setText(f"M{stage.diameter:g} × {values['pitch']:g} · Gösterim boyu {values['length']:g} mm")

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
        constructor={'groove':Groove,'keyway':Keyway,'chamfer':Chamfer,'fillet':Fillet,'cosmetic_thread':CosmeticThread}[kind]
        operation=constructor(**self.operation_values(kind))
        if isinstance(operation,(Chamfer,Fillet)):
            duplicate=next((op for op in self.project.operations
                            if isinstance(op,(Chamfer,Fillet)) and op.stage_id==operation.stage_id
                            and op.edge==operation.edge),None)
            if duplicate is not None:
                side='sol' if operation.edge=='left' else 'sağ'
                self.set_status(f'Bu kademenin {side} kenarında zaten pah/radyüs var. Diğer kenarı seçin veya listeden mevcut operasyonu düzenleyin.',True)
                return
        self.project.operations.append(operation)
        self.selected_stage=operation.stage_id
        # Keep end-treatment forms in add mode. Otherwise changing Sol -> Sağ
        # silently moves the previous chamfer before Ekle copies it, producing
        # two right-edge operations. List/preview selection still opens editing.
        self.selected_operation='' if isinstance(operation,(Chamfer,Fillet)) else operation.id
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
            target=self.operation_targets[kind].currentData()
            if target and target!=self.selected_stage:self.select_stage(target)
            self.refresh_standards();self.refresh_thread_caption();return
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
        self.edge_undo=None;self.save_epoch+=1
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
        self.project_path=Path(path);self.dirty=False;self.save_epoch+=1
        self.set_status('Mil parametreleri JSON olarak kaydedildi.')
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
