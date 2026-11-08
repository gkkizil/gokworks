"""GOKWORKS BasePage: stage editor, native operations and two linked views."""

from gui_qt.components import fit_columns
from gui_qt.components import NumberSpinBox
from copy import deepcopy
from dataclasses import fields
from pathlib import Path

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QBoxLayout,QFormLayout,QSplitter,QSizePolicy,
    QTableWidget,QTableWidgetItem,QAbstractItemView,QTabWidget,
    QLineEdit,QComboBox,QListWidget,QListWidgetItem,QFileDialog,QMessageBox,QCheckBox)
from gui_qt.components import BasePage, ElidedLabel, label, button, scroll, toggle_button, toggle_icon
from gui_qt.theme import ROW_HEIGHT, COLORS
from . import controller, storage
from .geometry import operation_plan
from .models import Project, Groove, Keyway, Chamfer, Fillet, Bore, CosmeticThread
from .preview import ShaftPreview
from .ribbon import CommandRibbon
from .standard_picker import ChannelStandardPicker
from .validation import validate
from .edge_treatments import circular_edges, plan_treatments


def num(value):
    """Shortest exact display with the Turkish decimal comma (12,5 not 12.5)."""
    return f'{value:g}'.replace('.',',')


class MeasureSpinBox(NumberSpinBox):
    """Shaft dimension field; the shared design-system spin box (decimals set per use)."""


TITLES = {'groove':'Segman kanalı','keyway':'Kama kanalı','chamfer':'Pah','fillet':'Radyüs','cosmetic_thread':'Kozmetik diş'}
FIELD_TITLES = {'offset':'Kademede başlangıç · mm','width':'Kanal genişliği · mm','length':'Boy · mm','depth':'Yüzeyden derinlik · mm',
                'angle':'Açı · °','distance':'Mesafe · mm','radius':'Radyüs · mm','pitch':'Diş adımı · mm'}


class AdaptiveViews(QWidget):
    """Top view and section: stacked when there is height for both, side by side otherwise."""
    STACK_HEIGHT = 2 * 200 + 2

    def __init__(self):
        super().__init__()
        self.box = QBoxLayout(QBoxLayout.TopToBottom, self)
        self.box.setContentsMargins(0, 0, 0, 0); self.box.setSpacing(2)
        self.setMinimumHeight(170)

    def add(self, view):
        self.box.addWidget(view, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        direction = QBoxLayout.TopToBottom if event.size().height() >= self.STACK_HEIGHT else QBoxLayout.LeftToRight
        if self.box.direction() != direction:
            self.box.setDirection(direction)


# Ribbon command → editor page (QTabWidget index); 'drawing' is resolved at runtime.
COMMAND_PAGES = {'stages': 0, 'groove': 1, 'keyway': 2, 'chamfer': 3, 'fillet': 4, 'cosmetic_thread': 5, 'bore': 6, 'bulk': 7}


class ShaftPage(BasePage):
    def __init__(self,context):
        super().__init__(context,'Parametrik mil','Üstten bölümü seçin, ölçüleri girin; mil aşağıda anında çizilir.')
        # Reserve native Windows font/frame overhead at 550×450 without
        # reducing either technical view's 170 px minimum or clipping commands.
        self.layout.setContentsMargins(10,2,10,2);self.layout.setSpacing(2)
        self.project=Project(); self.selected_stage=self.project.stages[0].id
        self.selected_operation=''; self.project_path=None; self.dirty=False
        self.plan=[]; self.last_result=None; self.edge_undo=None; self.save_epoch=0
        self.open_button=self.action('Proje aç',self.open_dialog)
        self.save_button=self.action('Proje kaydet',self.save_dialog)
        # Layout: command ribbon on top (category → command), the selected command's
        # fields under it, the two shaft views below. Same widgets and logic as before.
        self.ribbon=CommandRibbon();self.ribbon.setAttribute(Qt.WA_StyledBackground,True)
        self.ribbon.commandChosen.connect(self.open_command)
        ribbon_box=QVBoxLayout(self.ribbon);ribbon_box.setContentsMargins(6,2,6,4);ribbon_box.setSpacing(2)
        top_row=QHBoxLayout();top_row.setSpacing(8);top_row.addLayout(self.ribbon.category_row)
        self.name=QLineEdit(self.project.name); self.name.setAccessibleName('Mil parça adı')
        self.name.setPlaceholderText('Parça adı');self.name.setMaximumWidth(200);self.name.setMinimumWidth(90)
        self.name.setToolTip('SOLIDWORKS parça ve dosya adı')
        # Single-line facts yield their space to the commands on narrow windows (elided, full text kept).
        self.summary=ElidedLabel('');self.summary.setProperty('role','muted');self.summary.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        top_row.addStretch(1);top_row.addWidget(label('Parça','muted'));top_row.addWidget(self.name)
        ribbon_box.addLayout(top_row)
        command_row=QHBoxLayout();command_row.setSpacing(8);command_row.addLayout(self.ribbon.command_row)
        self.selected_stage_caption=ElidedLabel('');self.selected_stage_caption.setProperty('role','muted')
        self.selected_stage_caption.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        command_row.addWidget(self.summary,1);command_row.addWidget(self.selected_stage_caption,1);ribbon_box.addLayout(command_row)
        self.layout.addWidget(self.ribbon)
        # Editor panel (scrolls when short): fields of the open command | list of added operations.
        # One scroll area (no nested ones) and an opaque background: switching sections must
        # repaint the whole field area, never leave the previous form's pixels behind (Windows).
        self.editor=QWidget();self.editor.setMinimumWidth(0)
        self.editor.setObjectName('shaftEditor');self.editor.setAttribute(Qt.WA_StyledBackground,True)
        self.panel_box=QBoxLayout(QBoxLayout.LeftToRight,self.editor)
        self.panel_box.setContentsMargins(6,6,6,6);self.panel_box.setSpacing(16)
        fields_column=QWidget();edit=QVBoxLayout(fields_column);edit.setContentsMargins(0,0,0,0);edit.setSpacing(6)
        # Kept for keyboard users and older tests: the same sections as the ribbon, in one list.
        picker_row=QHBoxLayout(); picker_row.setSpacing(4)
        self.section_picker=QComboBox();self.section_picker.setAccessibleName('Mil parametre bölümü')
        self.section_picker.setToolTip('Düzenlenecek parametre grubu: kademeler, kanallar, kenar işlemleri, diş veya iç delik')
        self.section_picker.setMinimumWidth(0);self.section_picker.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.section_picker.setMinimumContentsLength(12);self.section_picker.hide()
        header=QHBoxLayout();header.setSpacing(6)
        self.edit_mode=label('','section');header.addWidget(self.edit_mode)
        self.new_operation_button=button('Seçimi bırak · yeni ekle',self.clear_operation_selection)
        self.new_operation_button.setToolTip('Seçili işlemden çık; aynı türden yeni bir işlem ekleyin.')
        header.addWidget(self.new_operation_button);header.addStretch(1)
        edit.addLayout(header)
        self.tabs=QTabWidget(); self.tabs.tabBar().hide();self.tabs.setDocumentMode(True)
        self.tabs.setMinimumWidth(0)

        stage_page=QWidget(); stages=QVBoxLayout(stage_page); stages.setContentsMargins(0,4,0,0); stages.setSpacing(4)
        stages.addWidget(label('Çap ve boy hücresine çift tıklayıp yazın. Kademe çizimden de seçilir.','muted'))
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(['Kademe','Çap · mm','Boy · mm'])
        self.table.verticalHeader().hide(); self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        fit_columns(self.table, elastic=2, minimum=90, defaults={0: 70, 1: 130})
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT); self.table.setShowGrid(False)
        self.table.setMinimumHeight(120); self.table.setAccessibleName('Düzenlenebilir mil kademeleri')
        # Compact toolbar above the stage table; commands act on the selected row.
        commands=QHBoxLayout(); commands.setSpacing(2)
        for text,callback in (('+ Kademe',lambda:self.add_stage()),('Kopyala',lambda:self.add_stage(copy=True)),
                               ('Sil',self.delete_stage),('↑',lambda:self.move_stage(-1)),('↓',lambda:self.move_stage(1))):
            control=button(text,callback); control.setMinimumWidth(0)
            control.setAccessibleName({'+ Kademe':'Kademe ekle','↑':'Kademeyi sola taşı','↓':'Kademeyi sağa taşı'}.get(text,'Kademe '+text.lower()))
            control.setToolTip({'+ Kademe':'Seçili kademenin sağına yeni kademe ekle','Kopyala':'Seçili kademeyi kopyala','Sil':'Seçili kademeyi sil',
                                '↑':'Seçili kademeyi sola taşı','↓':'Seçili kademeyi sağa taşı'}[text])
            if text in ('↑','↓'):control.setFixedWidth(32);control.setText('←' if text=='↑' else '→')
            commands.addWidget(control)
        commands.addStretch(1)
        stages.addLayout(commands); stages.addWidget(self.table,1); self.tabs.addTab(stage_page,'Kademeler')
        self.operation_fields={}; self.operation_targets={}; self.standard_pickers={}; self.loading_operation=False
        self.add_operation_buttons={};self.update_operation_buttons={};self.operation_hints={};self.operation_actions={}
        for kind,constructor in (('groove',Groove),('keyway',Keyway),('chamfer',Chamfer),('fillet',Fillet),('cosmetic_thread',CosmeticThread)):
            page=QWidget(); box=QVBoxLayout(page); box.setContentsMargins(6,6,6,6)
            self.operation_hints[kind]=label('','muted');box.addWidget(self.operation_hints[kind])
            # Two columns keep every field of an operation visible in the ribbon panel:
            # where (stage, standard, edge) on the left, the measures on the right.
            form=QFormLayout(); form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            measures=QFormLayout(); measures.setRowWrapPolicy(QFormLayout.WrapLongRows)
            measures.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

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
                    control=MeasureSpinBox();control.setDecimals(4);control.setRange(0,1_000_000)
                    control.setMinimumWidth(100);control.setKeyboardTracking(False)
                    title='Toplam boy · mm' if kind=='keyway' and key=='length' else FIELD_TITLES[key]
                    control.setValue(getattr(prototype,key));measures.addRow(title,control)
                    if key=='angle':
                        # Unsupported orientations/angles cannot masquerade as working CAD.
                        control.setEnabled(False)
                if key=='offset':control.setToolTip('Seçilen kademenin sol başlangıcından kanalın başlangıcına kadar mesafe; tüm milin başlangıcı değildir.')
                elif key=='depth':control.setToolTip('Silindirin dış yüzeyinden kanal tabanına radyal derinlik; mm.')
                elif key=='length' and kind=='keyway':control.setToolTip('Yuvarlak uçlar dahil kanalın uçtan uca toplam boyu; mm.')
                control.setAccessibleName(TITLES[kind]+' '+FIELD_TITLES.get(key,'Hedef kenar'))
                controls[key]=control
            columns=QHBoxLayout();columns.setSpacing(16);columns.addLayout(form,1);columns.addLayout(measures,1)
            self.operation_fields[kind]=controls;box.addLayout(columns)
            if kind=='keyway':box.addWidget(label('İki uç yarım daire: R = genişlik / 2. Boy, uçtan uca toplamdır. Açı 0°.','muted'))
            if kind in ('chamfer','fillet'):
                box.addWidget(label('Ekle sonrası diğer kenarı seçip yeni operasyon ekleyin. Düzenlemek için listeden seçin.','muted'))
            if kind=='chamfer':box.addWidget(label('Bu sürümde 45° eş mesafeli pah.','muted'))
            if kind=='cosmetic_thread':
                self.thread_caption=label('','muted');box.addWidget(self.thread_caption)
                box.addWidget(label('Metrik sağ diş. Kozmetik gösterimdir; katı hacmi değişmez. Boy, pah/radyüs sonrası silindirik yüzeyden başlar.','muted'))
            action_bar=QWidget();actions=QHBoxLayout(action_bar);actions.setContentsMargins(0,0,0,0)
            # The command the user looks for: accent colour and a little larger, at the top of the fields.
            add=button('+ İşlemi ekle',lambda checked=False,k=kind:self.add_operation(k),primary=True)
            add.setMinimumHeight(30);add.setMinimumWidth(130)
            add.setToolTip('Alanlardaki ölçülerle bu işlemi mile ekle')
            update=button('Seçiliyi güncelle',lambda checked=False,k=kind:self.update_operation(k))
            self.add_operation_buttons[kind]=add;self.update_operation_buttons[kind]=update
            self.operation_actions[kind]=action_bar
            actions.addWidget(add);actions.addWidget(update)
            box.addStretch()
            self.tabs.addTab(page,TITLES[kind])
        bore_page=QWidget();bore_box=QVBoxLayout(bore_page)
        self.bore_enabled=QCheckBox('Eksenel iç delik aç');self.bore_enabled.setAccessibleName('Mil iç deliğini etkinleştir')
        bore_box.addWidget(self.bore_enabled);bore_form=QFormLayout();bore_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.bore_controls={};self.loading_bore=False
        for key,title in (('diameter','İç çap · mm'),('end_condition','Sonlandırma'),('entry','Giriş'),('depth','Kör delik boyu · mm')):
            if key in ('diameter','depth'):
                control=MeasureSpinBox();control.setDecimals(4)
                control.setKeyboardTracking(False);control.setRange(.0001,1_000_000);control.setValue(getattr(Bore(),key))
            else:
                control=QComboBox()
                for text,value in ((('Boydan boya','through_all'),('Kör delik','blind')) if key=='end_condition' else (('Soldan','left'),('Sağdan','right'))):
                    control.addItem(text,value)
            control.setAccessibleName('İç delik '+title);self.bore_controls[key]=control;bore_form.addRow(title,control)
        bore_box.addLayout(bore_form)
        bore_box.addWidget(label('Tek eksenli silindirik delik. Kör delik tabanı düzdür. Et kalınlığı, segman ve kama derinlikleriyle birlikte kontrol edilir.','muted'))
        bore_box.addStretch();self.tabs.addTab(bore_page,'İç delik')
        self.build_bulk_page()
        advanced=label('Matkap uç konisi, iç diş, gerçek helisel diş, freze düzlüğü ve omuz boşaltması henüz desteklenmiyor.','muted')
        self.tabs.addTab(advanced,'İleri'); self.tabs.setTabEnabled(self.tabs.count()-1,False)
        from .drawing.ui import DrawingPanel
        self.drawing_panel=DrawingPanel(self);self.drawing_tab=self.tabs.count()
        self.tabs.addTab(self.drawing_panel,'Teknik resim')
        # Group prefixes keep related sections together in the single picker.
        for index,title in enumerate(('Kademeler · Çap ve boy','Kanal · Segman kanalı','Kanal · Kama kanalı','Kenar · Tek kenara pah',
                                      'Kenar · Tek kenara radyüs','Diş · Kozmetik diş','Delik · Eksenel iç delik','Kenar · Toplu pah / radyüs')):
            self.section_picker.addItem(title,index)
        self.section_picker.addItem('Teknik resim · Tolerans ve yüzey',self.drawing_tab)
        self.section_picker.currentIndexChanged.connect(lambda:self.tabs.setCurrentIndex(self.section_picker.currentData()))
        self.tabs.currentChanged.connect(self.section_changed)
        edit.addWidget(self.tabs,1)
        for action_bar in self.operation_actions.values():header.addWidget(action_bar)   # Ekle / Güncelle beside the title
        edit.addStretch(0)
        list_column=QWidget();side=QVBoxLayout(list_column);side.setContentsMargins(0,0,0,0);side.setSpacing(6)
        self.operation_count=label('Eklenen işlemler · 0','section');side.addWidget(self.operation_count)
        self.operations=QListWidget();self.operations.setMinimumHeight(72);self.operations.setMaximumHeight(140)
        self.operations.setAlternatingRowColors(True)
        self.operations.setToolTip('Bir işlemi seçin: ölçüleri soldaki alanlarda açılır, değişiklik anında uygulanır.')
        self.operations.setAccessibleName('Mil operasyonları');side.addWidget(self.operations)
        list_actions=QHBoxLayout();list_actions.setSpacing(4)
        self.remove_operation_button=button('Seçili işlemi sil',self.delete_operation)
        self.remove_operation_button.setToolTip('Listede seçili segman, kama, pah, radyüs veya diş işlemini kaldır')
        self.bulk_shortcut=button('Tüm kenarlara pah / radyüs…',self.show_bulk_treatments)
        self.bulk_shortcut.setToolTip('Mil uçları ve kademe omuzlarını tek işlemle düzenleyin.')
        list_actions.addWidget(self.remove_operation_button);list_actions.addWidget(self.bulk_shortcut);list_actions.addStretch(1)
        side.addLayout(list_actions)
        # Manufacturing check used by validation before CAD output.
        wall=QFormLayout(); wall.setContentsMargins(0,4,0,0);self.minimum_wall=MeasureSpinBox();self.minimum_wall.setDecimals(3)
        self.minimum_wall.setKeyboardTracking(False)
        self.minimum_wall.setRange(.001,100000);self.minimum_wall.setValue(self.project.minimum_wall)
        self.minimum_wall.setAccessibleName('En az kalan radyal et kalınlığı')
        self.minimum_wall.setToolTip('Kanal ve delik sonrası kalan en ince et; altındaki ölçüler hata verir.')
        wall.addRow('En az et kalınlığı · mm',self.minimum_wall);side.addLayout(wall);side.addStretch(1)
        self.fields_column,self.list_column=fields_column,list_column
        fields_column.setMinimumWidth(280);list_column.setMinimumWidth(240)
        self.panel_box.addWidget(fields_column,3);self.panel_box.addWidget(list_column,2)
        self.source_scroll=scroll(self.editor);self.source_scroll.setMinimumHeight(96)
        self.source_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        views=AdaptiveViews();self.views=views
        self.top_view=ShaftPreview();self.section_view=ShaftPreview(section=True)
        for view in (self.top_view,self.section_view):
            view.stageSelected.connect(self.select_stage);view.operationSelected.connect(self.select_operation)
            views.add(view)
        self.splitter=QSplitter(Qt.Vertical);self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.source_scroll);self.splitter.addWidget(views)
        self.splitter.setStretchFactor(0,0);self.splitter.setStretchFactor(1,1);self.splitter.setSizes([290,600])
        self.layout.addWidget(self.splitter,1)
        self.validation_label=label('','muted');self.validation_label.setMaximumHeight(60);self.layout.addWidget(self.validation_label)
        footer=QHBoxLayout();self.create_button=button("SolidWorks’te çiz",self.create_model,primary=True)
        self.create_button.setToolTip('Açık SolidWorks oturumunda yeni parametrik mil parçası oluştur')
        self.create_button.setAccessibleName('Yeni parametrik SOLIDWORKS parçası oluştur')
        self.save_part_button=button('SLDPRT oluştur ve kaydet…',self.create_and_save)
        self.stop_button=button('Durdur',self.jobs.cancel);self.stop_button.hide()
        # Same setting as 'Otomatik teknik resim oluştur' in the drawing section.
        self.auto_drawing=toggle_button('Teknik resmi de oluştur',self.context.appearance)
        self.auto_drawing.setToolTip('İşaretliyse katı model oluşturulup kaydedildikten hemen sonra aynı SOLIDWORKS oturumunda '
                                     '.SLDDRW teknik resmi de oluşturulur. Teknik resim kayıtlı parçaya bağlandığı için '
                                     'SolidWorks’te çiz de önce kayıt yeri sorar. Ayarlar: Teknik resim · Tolerans ve yüzey.')
        self.auto_drawing.setAccessibleName('Katı modelden sonra teknik resmi otomatik oluştur')
        self.auto_drawing.toggled.connect(self.auto_drawing_toggled)
        footer.addWidget(self.create_button);footer.addWidget(self.save_part_button);footer.addWidget(self.auto_drawing)
        footer.addStretch();footer.addWidget(self.stop_button)
        self.layout.addLayout(footer);self.finish_layout()
        self.controls.extend([self.source_scroll,self.create_button,self.save_part_button,self.auto_drawing])
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
        self.section_changed(self.tabs.currentIndex())
        self.build_menu()

    def build_menu(self):
        """Classic drop-down menus over the page's existing commands (same methods as the buttons)."""
        from gui_qt.page_menu import PageMenuBar
        from PySide6.QtWidgets import QMenu
        bar=self.menu_bar=PageMenuBar(self);open_=self.open_command
        menu=bar.addMenu('&Dosya')
        self.menu_commands=[(bar.command(menu,'Proje aç…',self.open_dialog,shortcut='Ctrl+O'),self.open_button),
                            (bar.command(menu,'Proje kaydet…',self.save_dialog,shortcut='Ctrl+S'),self.save_button)]
        menu.addSeparator()
        self.menu_commands+=[(bar.command(menu,'SolidWorks’te çiz',self.create_model,shortcut='F5'),self.create_button),
                             (bar.command(menu,'SLDPRT oluştur ve kaydet…',self.create_and_save,shortcut='Ctrl+Shift+S'),self.save_part_button)]
        bar.command(menu,'Kayıtlı parçaya teknik resim…',self.drawing_from_part)
        menu.addSeparator();self.menu_commands.append((bar.command(menu,'Durdur',self.jobs.cancel),self.stop_button))
        menu=bar.addMenu('&Kademe')
        bar.command(menu,'Çap ve boy tablosu',lambda:open_('stages'))
        menu.addSeparator()
        bar.command(menu,'Kademe ekle',lambda:self.add_stage(),shortcut='Ctrl+N')
        bar.command(menu,'Seçili kademeyi kopyala',lambda:self.add_stage(copy=True),shortcut='Ctrl+D')
        bar.command(menu,'Seçili kademeyi sil',self.delete_stage)
        bar.command(menu,'Sola taşı',lambda:self.move_stage(-1),shortcut='Ctrl+Left')
        bar.command(menu,'Sağa taşı',lambda:self.move_stage(1),shortcut='Ctrl+Right')
        menu=bar.addMenu('Ka&nal')
        bar.command(menu,'Segman kanalı ekle…',lambda:open_('groove'))
        bar.command(menu,'Kama kanalı ekle…',lambda:open_('keyway'))
        menu=bar.addMenu('K&enar')
        bar.command(menu,'Tüm kenarlara pah / radyüs…',lambda:open_('bulk'))
        bar.command(menu,'Tek kenara pah…',lambda:open_('chamfer'))
        bar.command(menu,'Tek kenara radyüs…',lambda:open_('fillet'))
        menu.addSeparator()
        self.menu_commands.append((bar.command(menu,'Son toplu uygulamayı geri al',self.undo_bulk_treatments),self.edge_undo_button))
        menu=bar.addMenu('Diş ve &delik')
        bar.command(menu,'Kozmetik diş ekle…',lambda:open_('cosmetic_thread'))
        bar.command(menu,'Eksenel iç delik…',lambda:open_('bore'))
        bar.check(menu,'İç deliği aç',self.bore_enabled)
        menu=bar.addMenu('&Teknik resim')
        bar.command(menu,'Sayfa, tolerans ve yüzey ayarları…',lambda:open_('drawing'))
        bar.check(menu,'Katı modelden sonra teknik resmi de oluştur',self.auto_drawing)
        for menu in bar.findChildren(QMenu):
            menu.aboutToShow.connect(lambda:bar.sync_enabled(self.menu_commands))

    def build_bulk_page(self):
        page=QWidget();box=QVBoxLayout(page);box.setContentsMargins(6,6,6,6)
        box.addWidget(label('Tüm uçlar ve omuzlar','section'))
        box.addWidget(label('Milin iki ucu ve kademeler arasındaki dairesel omuz kenarları birlikte işlenir.', 'muted'))
        form=QFormLayout();form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.bulk_kind=QComboBox();self.bulk_kind.addItem('Pah · 45°','chamfer');self.bulk_kind.addItem('Radyüs','fillet')
        self.bulk_kind.setAccessibleName('Toplu kenar işlemi türü')
        form.addRow('Uygulanacak işlem',self.bulk_kind)
        self.bulk_size=MeasureSpinBox()
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
        box.addWidget(label('Katı modeli üretmek için ardından SolidWorks’te çiz düğmesini kullanın.', 'muted'))
        box.addStretch();self.tabs.addTab(page,'Toplu pah / radyüs')
        self.bulk_kind.currentIndexChanged.connect(self.refresh_bulk_info)
        self.bulk_size.valueChanged.connect(self.refresh_bulk_info)
        self.bulk_replace.toggled.connect(self.refresh_bulk_info)

    def page_key(self,index):
        return 'drawing' if index==self.drawing_tab else next((k for k,v in COMMAND_PAGES.items() if v==index),None)

    def open_command(self,key):
        """Ribbon command: open its editor page (bulk edges go through the existing shortcut)."""
        if key=='bulk':self.show_bulk_treatments()
        else:
            self.tabs.setCurrentIndex(self.drawing_tab if key=='drawing' else COMMAND_PAGES[key])
            self.source_scroll.verticalScrollBar().setValue(0)
        # Re-clicking the open command must not leave it unchecked.
        self.ribbon.show_page(self.page_key(self.tabs.currentIndex()))

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'panel_box'):
            narrow=event.size().width()<760
            self.panel_box.setDirection(QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight)
            self.ribbon.set_compact(event.size().width()<640)

    def fit_current_page(self,index):
        """Only the open section sizes the editor; hidden sections take no height."""
        for i in range(self.tabs.count()):
            page=self.tabs.widget(i)
            policy=QSizePolicy.Preferred if i==index else QSizePolicy.Ignored
            page.setSizePolicy(policy,policy)
        self.tabs.updateGeometry();self.editor.adjustSize()
        if hasattr(self,'source_scroll'):self.source_scroll.viewport().update()

    def section_changed(self,index):
        self.fit_current_page(index)
        if hasattr(self,'ribbon'):
            self.ribbon.show_page(self.page_key(index));self.ribbon.set_appearance(COLORS[self.context.appearance])
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
            self.selected_stage_caption.setText(f'Seçili: {row}. kademe · Ø{num(stage.diameter)} · Boy {num(stage.length)} mm')
        op=next((op for op in self.project.operations if op.id==self.selected_operation),None)
        is_single=1<=self.tabs.currentIndex()<=5
        self.edit_mode.setVisible(is_single)
        self.new_operation_button.setVisible(is_single and op is not None)
        self.edit_mode.setText('Seçili işlem düzenleniyor' if op is not None else 'Yeni işlem ekle')
        self.operation_count.setText(f'Eklenen işlemler · {len(self.project.operations)}')
        self.operations.setFixedHeight(max(72,min(148,len(self.project.operations)*28+8)))
        self.bulk_shortcut.setVisible(self.tabs.currentIndex()!=7)
        self.remove_operation_button.setEnabled(not self.busy and op is not None)
        for kind in self.operation_fields:
            self.operation_actions[kind].setVisible(is_single and list(TITLES)[self.tabs.currentIndex()-1]==kind)
            editing=op is not None and op.kind==kind
            self.add_operation_buttons[kind].setEnabled(not self.busy and not editing)
            self.update_operation_buttons[kind].setEnabled(not self.busy and editing)
            self.operation_hints[kind].setText('Alanlardaki değişiklikler seçili işleme anında uygulanır.' if editing
                                              else 'Kademeyi ve ölçüleri seçin, sonra + İşlemi ekle.')
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
                    item=QTableWidgetItem(f'{num(value)}');item.setData(Qt.UserRole,stage.id)
                    if col==0:item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter if col else Qt.AlignLeft|Qt.AlignVCenter)
                    self.table.setItem(row,col,item)
        for target in self.operation_targets.values():
            previous=target.currentData()
            with QSignalBlocker(target):
                target.clear()
                for i,stage in enumerate(self.project.stages,1):target.addItem(f'{i}. kademe · Ø{num(stage.diameter)}',stage.id)
                index=target.findData(previous or self.selected_stage);target.setCurrentIndex(max(index,0))
        with QSignalBlocker(self.operations):
            self.operations.clear()
            for op in self.project.operations:
                index=next(i for i,s in enumerate(self.project.stages,1) if s.id==op.stage_id)
                detail=''
                if isinstance(op,(Chamfer,Fillet)):
                    side='Sol' if op.edge=='left' else 'Sağ'
                    size=op.distance if isinstance(op,Chamfer) else op.radius
                    detail=f' · {side} · {num(size)} mm'
                elif isinstance(op,CosmeticThread):
                    side='Sol' if op.edge=='left' else 'Sağ'
                    detail=f' · M{num(self.project.stage(op.stage_id).diameter)}×{num(op.pitch)} · {side} · {num(op.length)} mm'
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
        self.summary.setText('Ölçü hatası' if errors else f'{len(self.project.stages)} kademe · L {num(self.project.total_length)} mm · Ømaks {num(self.project.maximum_diameter)} mm')
        self.validation_label.setText('\n'.join(errors) if errors else 'Ölçüler geçerli · Yeni parça oluşturulur · Önizleme boyut oranlarını korur')
        self.validation_label.setToolTip('\n'.join(errors));self.validation_label.setProperty('role','error' if errors else 'muted')
        self.validation_label.style().unpolish(self.validation_label);self.validation_label.style().polish(self.validation_label)
        for view in (self.top_view,self.section_view):view.set_project(self.project,self.selected_stage,self.selected_operation)
        self.refresh_standards()
        self.refresh_thread_caption()
        self.refresh_editor_context()
        if hasattr(self,'drawing_panel') and not getattr(self,'_drawing_refresh',False):self.drawing_panel.populate()
        self.sync_auto_drawing()

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
        if stage is not None:self.thread_caption.setText(f"M{num(stage.diameter)} × {num(values['pitch'])} · Gösterim boyu {num(values['length'])} mm")

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
        try:removed=self.project.remove_stage(self.selected_stage)
        except ValueError as error:self.set_status(str(error),True);return
        self.notify_pruned(removed)
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
        self.selected_operation='';self.notify_pruned(self.project.prune_drawing())
        self.populate();self.refresh(changed=True)

    def notify_pruned(self,removed):
        if removed:
            self.set_status(f'Silinen öğeye bağlı {len(removed)} teknik resim gereksinimi kaldırıldı: '+', '.join(removed[:4])
                            +(' …' if len(removed)>4 else ''))

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
        drawing=self.project.drawing
        if drawing is not None and drawing.enabled:
            from .drawing.controller import output_paths
            plan=self.drawing_panel.refresh_plan()
            if plan['errors']:
                self.set_status('Teknik resim planında hata var; önce Teknik resim bölümünü düzeltin.\n'+'\n'.join(plan['errors']),True);return
            taken=[v for v in output_paths(path,drawing).values() if v and Path(v).exists()]
            if taken:self.set_status('Teknik resim çıktısı zaten var, üzerine yazılmaz: '+taken[0],True);return
            if not self.can_start():return
            snapshot=deepcopy(self.project)
            from .drawing.controller import create_part_and_drawing
            self.set_status('SOLIDWORKS parçası ve teknik resmi hazırlanıyor…')
            self.jobs.start(self,lambda events,stop:create_part_and_drawing(snapshot,path,events,stop))
            return
        self.create_model(output_path=path)

    def drawing_enabled(self):
        return self.project.drawing is not None and self.project.drawing.enabled

    def sync_auto_drawing(self):
        if not hasattr(self,'auto_drawing'):return
        on=self.drawing_enabled()
        if self.auto_drawing.isChecked()!=on:
            with QSignalBlocker(self.auto_drawing):self.auto_drawing.setChecked(on)
        # The action buttons say exactly what will happen.
        self.create_button.setText('SolidWorks’te çiz + teknik resim…' if on else 'SolidWorks’te çiz')
        self.save_part_button.setText('SLDPRT + teknik resim kaydet…' if on else 'SLDPRT oluştur ve kaydet…')

    def auto_drawing_toggled(self,checked):
        if checked==self.drawing_enabled():return
        # Write through the drawing panel so the project, its checkbox and the plan stay in one place.
        self.drawing_panel.enabled.setChecked(checked)
        self.set_status('Katı modelden sonra teknik resim de oluşturulacak; SolidWorks’te çiz önce kayıt yeri sorar.'
                        if checked else 'Yalnız katı model oluşturulacak.')

    def drawing_changed(self):
        self._drawing_refresh=True
        try:self.refresh(changed=True)
        finally:self._drawing_refresh=False

    def drawing_from_part(self):
        if not self.can_start():return
        plan=self.drawing_panel.refresh_plan()
        if plan['errors']:self.set_status('Teknik resim planında hata var:\n'+'\n'.join(plan['errors']),True);return
        path,_=QFileDialog.getOpenFileName(self,'GOKWORKS mil parçası seç','','SOLIDWORKS parçası (*.SLDPRT *.sldprt)')
        if not path:return
        from .drawing.controller import output_paths, create_drawing
        from .drawing.models import DrawingSettings
        taken=[v for v in output_paths(path,self.project.drawing or DrawingSettings()).values() if v and Path(v).exists()]
        if taken:self.set_status('Teknik resim çıktısı zaten var, üzerine yazılmaz: '+taken[0],True);return
        snapshot=deepcopy(self.project)
        self.set_status('Kayıtlı parça için teknik resim hazırlanıyor… Parça ölçüleri mil parametreleriyle karşılaştırılır.')
        self.jobs.start(self,lambda events,stop:create_drawing(snapshot,path,events,stop))

    def create_model(self, *, output_path=''):
        if not output_path and self.drawing_enabled():
            # A drawing references a saved part: save first, then draw.
            self.create_and_save();return
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
            elif kind=='shaft_drawing':
                state=value.get('state');problems=value.get('problems',[])
                if state=='complete':
                    self.set_status(f"Teknik resim oluşturuldu ve yeniden açılarak doğrulandı: {value.get('drawing_path','')}")
                elif state=='partial':
                    self.set_status('Teknik resim kısmen tamamlandı; eksikler gizlenmedi:\n'+'\n'.join(problems),True)
                else:
                    self.set_status('Model korundu, teknik resim oluşturulamadı:\n'+'\n'.join(problems),True)
            elif kind=='shaft_created':
                self.last_result=value
                self.set_status(f"{value['document']} oluşturuldu · {value['feature_count']} yerel özellik · Rebuild başarılı")
        # Worker batches can contain both the initial phase and job_error.
        # Errors must win over an older phase, including when startup fails.
        super().handle_events(events)

    def set_busy(self,busy):
        super().set_busy(busy);self.refresh()

    def theme_changed(self):
        if hasattr(self,'ribbon'):self.ribbon.set_appearance(COLORS[self.context.appearance])
        if hasattr(self,'auto_drawing'):self.auto_drawing.setIcon(toggle_icon(self.context.appearance))
        for picker in self.standard_pickers.values():picker.set_appearance(self.context.appearance)
        for view in (self.top_view,self.section_view):view.appearance=self.context.appearance;view.update()
