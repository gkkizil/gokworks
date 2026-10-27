"""Integrated, asynchronous profile cut-list and Weldments workflow."""

from copy import deepcopy
from dataclasses import asdict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QTableView, QFileDialog, QAbstractItemView, QDialog, QLineEdit, QComboBox,
    QSplitter, QStackedWidget, QMenu, QCheckBox, QHeaderView, QMessageBox)

from gui_qt.components import BasePage, ValueForm, Disclosure, label, button, configure_view, show_details, scroll
from gui_qt.models import TableModel, FilterProxy, Column
from gui_qt.services import check_connection
from .models import Project, Demand, quantity, number, transfer, reconcile, checkpoint
from .properties import DEFAULT_MAPPING, validate_mapping, section_thickness
from .scanner import scan, Options, Cancelled
from .optimizer import optimize
from .dialogs import MappingDialog, RowDialog
from .storage import save, load, export_report
from .widgets import CutOrder, mm, source_name, group_name, cut_pattern, plan_totals


def display(value): return str(value).replace('.', ',')


class ProfileTableModel(TableModel):
    def data(self,index,role=Qt.DisplayRole):
        if role == Qt.ToolTipRole and index.isValid():
            row = self.rows[index.row()]
            if self.columns[index.column()].key == 'source' and row.get('source_detail'):
                return row['source_detail']
            if self.columns[index.column()].key == 'group':
                return str(row.get('group','')) + '\n' + str(row.get('cuts',''))
        if role == Qt.TextAlignmentRole and index.isValid() and self.columns[index.column()].key in ('length','count','allowance','angle1','angle2','remaining','bar'):
            return Qt.AlignRight | Qt.AlignVCenter
        return super().data(index,role)


class ProfileCuttingPage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'Profil kesim optimizasyonu',
                         'Kesilecek parçaları ekleyin, ham profil boyunu girin ve kesim planını görün.')
        self.project, self.scan_result, self.plan = Project(), None, None
        self.last_path = None
        self.scan_current = False
        self._ready_rows = 0
        try: self.mapping = validate_mapping(deepcopy(self.settings.get('profile_property_mapping', DEFAULT_MAPPING)))
        except ValueError: self.mapping = deepcopy(DEFAULT_MAPPING)
        self.run_button = self.action('Kesim planını hesapla', self.calculate, primary=True)
        self.project_button = self.action('Proje', lambda: None)
        project_menu = QMenu(self.project_button)
        project_menu.addAction('Proje aç…', self.open_project)
        project_menu.addAction('Projeyi kaydet…', self.save_project)
        self.csv_action = project_menu.addAction('CSV raporu kaydet…', self.report)
        project_menu.addSeparator()
        project_menu.addAction('Örnekle dene', self.load_example)
        self.project_button.setMenu(project_menu)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        self.tabs = QTabWidget(); self.layout.addWidget(self.tabs, 1)
        self._build_cut_page()
        self._build_scan_page()
        self._build_plan_page()
        self.controls.extend((self.form, self.stock_extra, self.scan_options, self.demands,
                              self.scan_view, self.report_button))
        self.form.changed.connect(self.options_changed)
        self.finish_layout(); self.refresh_demands()

    def _build_cut_page(self):
        cut_page = QWidget(); cut_layout = QVBoxLayout(cut_page)
        cut_layout.setContentsMargins(0, 6, 0, 0); cut_layout.setSpacing(6)
        cut_layout.addWidget(label('1 · Parçaları ekleyin   →   2 · Ham profil boyunu girin   →   3 · Kesim planını hesaplayın', 'muted'))
        tools = QHBoxLayout()
        self.add_button = button('Parça ekle', self.add_manual)
        self.from_sw_button = button('SolidWorks’ten al', lambda: self.tabs.setCurrentIndex(1))
        self.edit_button = button('Düzenle', self.edit_selected)
        self.remove_button = button('Kaldır', self.remove)
        for control in (self.add_button, self.from_sw_button): tools.addWidget(control)
        tools.addStretch()
        for control in (self.edit_button, self.remove_button): tools.addWidget(control)
        view_button = button('Görünüm')
        view_menu = QMenu(view_button)
        self.detail_columns = view_menu.addAction('Kaynak ve ilave boy sütunlarını göster')
        self.detail_columns.setCheckable(True)
        self.detail_columns.toggled.connect(self.update_demand_columns)
        view_button.setMenu(view_menu); tools.addWidget(view_button)
        self.controls.extend((self.add_button, self.from_sw_button, self.edit_button, self.remove_button, view_button))
        cut_layout.addLayout(tools)

        self.cut_splitter = QSplitter(Qt.Horizontal); self.cut_splitter.setChildrenCollapsible(False)
        cut_layout.addWidget(self.cut_splitter, 1)
        listing = QWidget(); listing.setMinimumWidth(180)
        body = QVBoxLayout(listing); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(6)
        body.addWidget(label('Kesilecek parçalar', 'section'))
        self.demand_model = ProfileTableModel((Column('Profil', 'profile'), Column('Malzeme', 'material'),
            Column('Parça boyu · mm','length',display), Column('Adet','count'), Column('İlave boy · mm','allowance',display),
            Column('Kaynak','source')), editable=('profile','material','length','count','allowance'))
        self.demands = configure_view(QTableView()); self.demands.setModel(self.demand_model)
        self.demands.setSortingEnabled(False)
        self.demands.setAccessibleName('Kesilecek parçalar: profil, malzeme, parça boyu ve adet')
        self.demands.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.demands.setEditTriggers(QAbstractItemView.EditKeyPressed)
        self.demands.doubleClicked.connect(lambda _: self.edit_selected())
        for i,width in enumerate((170,100,120,55,120,240)): self.demands.setColumnWidth(i,width)
        header = self.demands.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.demands.selectionModel().selectionChanged.connect(self.update_actions)
        self.demand_model.edited.connect(self.edit_demand_cell)
        self.demand_stack = QStackedWidget(); self.demand_stack.addWidget(self.demands)
        empty = QWidget(); empty_body = QVBoxLayout(empty)
        empty_body.addStretch()
        self.empty_title = label('Hangi parçalar kesilecek?', 'section')
        self.empty_title.setAlignment(Qt.AlignCenter)
        empty_body.addWidget(self.empty_title)
        intro = label('Örneğin: 40×40×2 profilden 1200 mm boyunda 4 parça.\nParça ekle ile başlayın veya SolidWorks listenizi alın.', 'muted')
        intro.setAlignment(Qt.AlignCenter); empty_body.addWidget(intro)
        example = button('Örnekle dene', self.load_example)
        empty_body.addWidget(example, alignment=Qt.AlignHCenter); self.controls.append(example)
        empty_body.addStretch(); self.demand_stack.addWidget(empty)
        body.addWidget(self.demand_stack, 1)
        self.demand_summary = label('Henüz parça eklenmedi.', 'muted'); body.addWidget(self.demand_summary)
        self.cut_splitter.addWidget(listing)

        stock = QWidget(); stock_body = QVBoxLayout(stock)
        stock_body.setContentsMargins(8, 0, 4, 0); stock_body.setSpacing(8)
        stock_body.addWidget(label('Ham profil ve kesim payı', 'section'))
        stock_body.addWidget(label('Satın aldığınız tek çubuğun boyu.\n6 metre için 6000 mm girin.', 'muted'))
        self.form = ValueForm(self.settings, 'profile_cutting_')
        self.form.text('stock_length', 'Ham çubuk boyu · mm', '6000').setToolTip('Bir adet satın alınan profilin uzunluğu; 6 m = 6000 mm.')
        self.form.text('kerf', 'Testere kesim payı · mm', '3').setToolTip('Her parçada testerenin kaybettirdiği boy; parça boyundan ayrıdır.')
        self.form.stack_fields(); stock_body.addWidget(self.form)
        for field in self.form.fields.values():
            self.form.form.labelForField(field).setWordWrap(False)
        self.stock_extra = ValueForm(self.settings, 'profile_cutting_')
        self.stock_extra.text('trim', 'Uç düzeltme · mm / bir uç', '0')
        self.stock_extra.form.addRow(label('Girilen değer çubuğun iki ucundan da düşülür. Her parçada boy + ilave boy + testere payı tüketilir.', 'muted'))
        self.stock_extra.stack_fields()
        self.stock_disclosure = Disclosure('Uç düzeltme ve hesap bilgisi', self.stock_extra)
        stock_body.addWidget(self.stock_disclosure)
        self.form.fields.update(self.stock_extra.fields)
        self.stock_extra.changed.connect(self.form.changed)
        for key in ('stock_length','kerf','trim'): setattr(self.project, key, self.form.value(key))
        self.input_summary = label('', 'section'); stock_body.addWidget(self.input_summary)
        self.next_step = label('Önce kesilecek parçaları ekleyin.', 'muted'); stock_body.addWidget(self.next_step)
        stock_body.addWidget(label('Farklı kesit ve malzemeler ayrı çubuklara yerleştirilir. Hesap, bu boyda yeterli çubuk olduğunu varsayar.', 'muted'))
        stock_body.addStretch()
        stock_scroll = scroll(stock); stock_scroll.setMinimumWidth(220)
        stock_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cut_splitter.addWidget(stock_scroll); self.cut_splitter.setSizes([780,280])
        self.tabs.addTab(cut_page, 'Parçalar ve stok')

    def _build_scan_page(self):
        sw_page = QWidget(); sw_layout = QVBoxLayout(sw_page); sw_layout.setContentsMargins(0,8,0,0)
        grid = self.source_grid = QGridLayout(); grid.setSpacing(6)
        self.connect_button = button('Bağlantıyı kontrol et', self.connect)
        self.scan_button = button('Açık modeli oku', lambda: self.start_scan(None))
        self.file_button = button('Dosya seç…', self.choose_source)
        self.refresh_button = button('Verileri yenile', self.refresh_scan)
        self.transfer_button = button('Hazır satırları listeye ekle', self.import_scan, primary=True)
        self.mapping_button = button('Alan adlarını eşleştir', self.edit_mapping)
        self.source_actions = (self.scan_button, self.file_button, self.refresh_button)
        self.controls.extend((*self.source_actions, self.connect_button, self.transfer_button, self.mapping_button))
        self.source_columns = 0
        self.reflow_source()
        sw_layout.addLayout(grid)
        advanced = QWidget(); advanced_body = QVBoxLayout(advanced); advanced_body.setContentsMargins(0,0,0,0)
        row = QHBoxLayout(); row.addWidget(self.connect_button); row.addWidget(self.mapping_button); row.addStretch()
        advanced_body.addLayout(row)
        self.scan_options = ValueForm(self.settings, 'weldment_')
        self.scan_options.check('update_cut_list', 'Okumadan önce kesim listesini güncelle', False).setToolTip('SolidWorks Cut List güncellenir; kaynak dosya kaydedilmez.')
        self.scan_options.check('geometry_length', 'Boy bilgisi eksikse doğrulanmış geometriden al', False).setToolTip('Yalnız doğrusal olduğu doğrulanan profiller için; bounding box boyu kullanılmaz.')
        advanced_body.addWidget(self.scan_options)
        self.scan_details_check = QCheckBox('Açı sütunlarını göster')
        self.scan_details_check.setChecked(self.settings.get('profile_cutting_scan_details', False) is True)
        self.scan_details_check.toggled.connect(self.update_scan_columns); advanced_body.addWidget(self.scan_details_check)
        advanced_body.addWidget(label('Kaynak açıları testere ayarı değildir. Açılı kesimler listeye eklenmeden önce kontrol edilir.', 'muted'))
        self.scan_disclosure = Disclosure('SolidWorks seçenekleri', advanced)
        sw_layout.addWidget(self.scan_disclosure)
        self.source_label = label('Açık modeli okuyun veya bir SLDPRT / SLDASM dosyası seçin.', 'muted')
        sw_layout.addWidget(self.source_label)
        self.search = QLineEdit(); self.search.setPlaceholderText('Parça, profil veya malzeme ara…')
        self.status_filter = QComboBox()
        for text, value in (('Tüm sonuçlar',None),('Hazır','Hazır'),('Kontrol gerekiyor','İnceleme Gerekli'),('Hariç','Hariç')):
            self.status_filter.addItem(text, value)
        search_row = QHBoxLayout(); search_row.addWidget(self.search,1); search_row.addWidget(self.status_filter)
        sw_layout.addLayout(search_row)
        self.scan_model = ProfileTableModel((Column('Parça / kesim grubu','source'), Column('Profil kesiti','profile'),
            Column('Malzeme','material'), Column('Boy · mm','length',display), Column('Adet','count'),
            Column('Açı 1 · °','angle1'), Column('Açı 2 · °','angle2'), Column('Kontrol','status',lambda v:'Kontrol gerekiyor' if v=='İnceleme Gerekli' else v)),
            editable=('profile','material','length','count','angle1','angle2'))
        self.scan_proxy = FilterProxy(self); self.scan_proxy.setSourceModel(self.scan_model)
        self.status_filter.currentIndexChanged.connect(lambda _:self.scan_proxy.set_status(self.status_filter.currentData()))
        self.scan_view = configure_view(QTableView()); self.scan_view.setModel(self.scan_proxy)
        self.scan_view.setMinimumHeight(180)
        for i,width in enumerate((270,160,95,90,60,70,70,140)): self.scan_view.setColumnWidth(i,width)
        self.scan_view.doubleClicked.connect(lambda _: self.review_selected())
        self.scan_view.setEditTriggers(QAbstractItemView.EditKeyPressed)
        self.scan_view.selectionModel().selectionChanged.connect(self.update_actions)
        self.scan_model.edited.connect(self.edit_scan_cell)
        self.search.textChanged.connect(self.scan_proxy.set_query)
        sw_layout.addWidget(self.scan_view, 1)
        self.scan_summary = label('Henüz tarama yapılmadı.', 'muted'); sw_layout.addWidget(self.scan_summary)
        row = QHBoxLayout()
        self.review_button = button('Satırı kontrol et', self.review_selected)
        row.addWidget(self.review_button); self.controls.append(self.review_button)
        more = button('Ayrıntılar'); menu = QMenu(more)
        menu.addAction('Okuma ayrıntıları…', self.scan_details); menu.addAction('CSV raporu kaydet…', self.report)
        more.setMenu(menu); row.addWidget(more); self.controls.append(more)
        row.addStretch(); row.addWidget(self.transfer_button); sw_layout.addLayout(row)
        sw_layout.addWidget(label('Yalnız hazır satırlar eklenir. Elle girdiğiniz parçalar korunur; aynı tarama iki kez eklenmez.', 'muted'))
        sw_scroll = scroll(sw_page)
        sw_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tabs.addTab(sw_scroll, 'SolidWorks’ten al')
        self.update_scan_columns(self.scan_details_check.isChecked())

    def _build_plan_page(self):
        plan_page = QWidget(); plan_layout = QVBoxLayout(plan_page); plan_layout.setContentsMargins(0,8,0,0)
        self.plan_summary = label('Önce parçaları ekleyip kesim planını hesaplayın.', 'section')
        plan_layout.addWidget(self.plan_summary)
        self.plan_numbers = label('', 'muted'); plan_layout.addWidget(self.plan_numbers)
        self.plan_proof = label('', 'muted'); plan_layout.addWidget(self.plan_proof)
        self.plan_stack = QStackedWidget(); plan_layout.addWidget(self.plan_stack,1)
        self.plan_splitter = QSplitter(Qt.Horizontal); self.plan_splitter.setChildrenCollapsible(False)
        left = QWidget(); layout = QVBoxLayout(left); layout.setContentsMargins(0,0,0,0)
        self.plan_list_panel = left
        layout.addWidget(label('Çubuklar · ayrıntı için seçin', 'section'))
        self.plan_model = ProfileTableModel((Column('Çubuk','bar'), Column('Profil / malzeme','group'),
            Column('Kesilecek parçalar','cuts'), Column('Artan · mm','remaining',display)))
        self.plan_view = configure_view(QTableView()); self.plan_view.setModel(self.plan_model)
        self.plan_view.setSortingEnabled(False); self.plan_view.setMinimumHeight(100)
        self.plan_view.setColumnHidden(2,True)
        self.plan_view.horizontalHeader().setStretchLastSection(False)
        self.plan_view.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents)
        self.plan_view.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        self.plan_view.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeToContents)
        self.plan_view.selectionModel().currentRowChanged.connect(lambda index, _: self.draw_bar(index.row()))
        layout.addWidget(self.plan_view,1); self.plan_splitter.addWidget(left)
        self.cut_order = CutOrder(self.context); self.diagram = self.cut_order.diagram
        self.plan_splitter.addWidget(self.cut_order); self.plan_splitter.setSizes([370,700])
        self.plan_stack.addWidget(self.plan_splitter)
        empty = QWidget(); layout = QVBoxLayout(empty); layout.addStretch()
        layout.addWidget(label('Kesim planı burada görünecek.', 'section'))
        back = button('Parçalar ve stoka dön',lambda:self.tabs.setCurrentIndex(0))
        layout.addWidget(back,alignment=Qt.AlignLeft); layout.addStretch(); self.plan_stack.addWidget(empty)
        self.plan_stack.setCurrentIndex(1)
        footer = QHBoxLayout()
        footer.addWidget(label('Artan profil ile testere / uç düzeltme kaybı ayrı gösterilir.', 'muted'),1)
        self.report_button = button('Kesim planını CSV kaydet', self.report); footer.addWidget(self.report_button)
        plan_layout.addLayout(footer)
        plan_scroll = scroll(plan_page); plan_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tabs.addTab(plan_scroll, 'Kesim planı')

    def reflow_source(self):
        columns = 3 if self.width()-32 >= 800 else 2
        if columns == self.source_columns: return
        for control in self.source_actions: self.source_grid.removeWidget(control)
        for i,control in enumerate(self.source_actions): self.source_grid.addWidget(control,i//columns,i%columns,Qt.AlignLeft)
        for i in range(4): self.source_grid.setColumnStretch(i,1 if i==columns else 0)
        self.source_columns = columns

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'source_actions'): self.reflow_source()
        if hasattr(self,'plan_splitter'):
            orientation = Qt.Horizontal if self.width() >= 950 else Qt.Vertical
            if self.plan_splitter.orientation() != orientation:
                self.plan_splitter.setOrientation(orientation)
                self.plan_splitter.setSizes([240,450] if orientation == Qt.Vertical else [370,700])
            self.plan_list_panel.setMaximumHeight(160 if orientation == Qt.Vertical else 16777215)

    def set_busy(self, busy):
        super().set_busy(busy)
        if hasattr(self, 'report_button'): self.update_actions()

    def update_actions(self, *args):
        if not hasattr(self, 'report_button'): return
        idle = not self.busy
        has_parts = bool(self.project.demands)
        self.run_button.setEnabled(idle and has_parts)
        self.run_button.setToolTip('Hesapla: kaç çubuk alınacak ve her çubuktan hangi parçalar kesilecek.' if has_parts
                                  else 'Önce Parça ekle veya SolidWorks’ten al ile kesilecek parçaları ekleyin.')
        selected = bool(self.demands.selectionModel().selectedRows())
        self.edit_button.setEnabled(idle and selected)
        self.remove_button.setEnabled(idle and selected)
        self.transfer_button.setText(f'{self._ready_rows} hazır satırı listeye ekle' if self._ready_rows else 'Hazır satırları listeye ekle')
        self.transfer_button.setEnabled(idle and self.scan_current and self._ready_rows > 0)
        self.review_button.setEnabled(idle and self.scan_result is not None and self.scan_view.currentIndex().isValid())
        self.refresh_button.setEnabled(idle and (self.scan_result is not None or self.last_path is not None))
        self.report_button.setEnabled(idle and self.plan is not None)
        self.csv_action.setEnabled(idle and (has_parts or self.scan_result is not None))

    def update_demand_columns(self, *args):
        detail = self.detail_columns.isChecked()
        self.demands.setColumnHidden(5, not detail)
        self.demands.setColumnHidden(4, not (detail or any(number(r.allowance) for r in self.project.demands)))

    def update_scan_columns(self, checked):
        if hasattr(self, 'scan_view'):
            self.scan_view.setColumnHidden(5, not checked)
            self.scan_view.setColumnHidden(6, not checked)
        self.settings.set('profile_cutting_scan_details', bool(checked))

    def update_input_summary(self):
        rows = self.project.demands
        count = sum(r.count for r in rows)
        length = sum((number(r.length) * r.count for r in rows), number('0'))
        groups = len({r.group for r in rows})
        self.input_summary.setText(f'{count} parça · {groups} profil grubu\nToplam parça boyu: {mm(length)} mm' if rows else '')
        stale = any(r.source_changed for r in rows)
        self.next_step.setText('Kaynağı değişen satırları güncelleyip tekrar aktarın.' if stale else
            'Ham boyu ve testere payını kontrol edin; ardından Kesim planını hesapla’ya basın.' if rows else
            'Önce kesilecek parçaları ekleyin.')

    def invalidate(self):
        self.plan = None; self.plan_model.replace([]); self.cut_order.clear()
        self.plan_stack.setCurrentIndex(1)
        self.plan_summary.setText('Liste veya ayarlar değişti; kesim planını yeniden hesaplayın.')
        self.plan_numbers.clear(); self.plan_proof.clear()
        self.update_actions()

    def options_changed(self, key):
        setattr(self.project, key, self.form.value(key)); self.invalidate()

    def refresh_demands(self):
        self.demand_model.replace([dict(asdict(row), source=(row.source_changed+' '+row.source if row.source_changed else row.source),
                                       status='error' if row.source_changed else '') for row in self.project.demands])
        stale = sum(bool(row.source_changed) for row in self.project.demands)
        self.demand_summary.setText(f'{len(self.project.demands)} satır · {sum(row.count for row in self.project.demands)} parça'
            + (f' · {stale} değişmiş kaynak: güncel satırları yeniden aktarın.' if stale else ''))
        self.demand_stack.setCurrentIndex(0 if self.project.demands else 1)
        self.update_demand_columns(); self.update_input_summary(); self.update_actions()

    def add_manual(self):
        dialog = RowDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.project.demands.append(dialog.value); self.invalidate(); self.refresh_demands()

    def edit_selected(self):
        index = self.demands.currentIndex()
        if not index.isValid() or not self.can_start(): return
        dialog = RowDialog(self, self.project.demands[index.row()])
        if dialog.exec() == QDialog.Accepted:
            self.project.demands[index.row()] = dialog.value
            self.invalidate(); self.refresh_demands()

    def load_example(self):
        if not self.can_start(): return
        if self.project.demands and QMessageBox.question(self, 'Örnek listeyi aç',
                'Mevcut liste örnek parçalarla değişecek. Kaydetmediğiniz değişiklikler kaybolur. Devam edilsin mi?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.project = Project([Demand('example-1','40×40×2','S235JR','1200',4,thickness='2'),
                                Demand('example-2','40×40×2','S235JR','800',6,thickness='2')])
        for key in ('stock_length','kerf','trim'): self.form.set_value(key,getattr(self.project,key))
        self.scan_result = None; self.scan_current = False; self._ready_rows = 0; self.last_path = None
        self.scan_model.replace([]); self.scan_summary.setText('Henüz tarama yapılmadı.')
        self.source_label.setText('Açık modeli okuyun veya bir SLDPRT / SLDASM dosyası seçin.')
        self.invalidate(); self.refresh_demands(); self.tabs.setCurrentIndex(0)
        self.set_status('Örnek liste: 1200 mm × 4 ve 800 mm × 6. Ham profil 6000 mm; hesaplayarak kesim planını görün.')

    def edit_demand_cell(self, index, key, value):
        row = self.project.demands[index]; previous = getattr(row, key)
        try:
            if key == 'profile' and row.thickness:
                inferred = section_thickness(str(value))
                if inferred is not None and number(row.thickness) != inferred:
                    raise ValueError('Profil kesiti et kalınlığıyla uyuşmuyor. Düzenle ile kesiti ve et kalınlığını birlikte değiştirin.')
            setattr(row, key, quantity(value) if key == 'count' else str(value))
            row.validate(); self.invalidate()
        except ValueError as error:
            setattr(row, key, previous); self.set_status(str(error), True)
        self.refresh_demands()

    def remove(self):
        selected = {index.row() for index in self.demands.selectionModel().selectedRows()}
        self.project.demands = [row for i,row in enumerate(self.project.demands) if i not in selected]
        self.invalidate(); self.refresh_demands()

    def connect(self):
        if self.can_start(): self.jobs.start(self, check_connection)

    def choose_source(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Kaynak SolidWorks parçası veya montajı seç', '',
                                             'SolidWorks (*.sldprt *.SLDPRT *.sldasm *.SLDASM)')
        if path: self.start_scan(path)

    def refresh_scan(self):
        self.start_scan(self.scan_result.source if self.scan_result else self.last_path)

    def start_scan(self, path):
        if not self.can_start(): return
        self.last_path = path
        self.scan_current = False
        self.update_actions(); self.tabs.setCurrentIndex(1)
        options = Options(self.scan_options.value('update_cut_list'), self.scan_options.value('geometry_length'))
        mapping = deepcopy(self.mapping)
        self.jobs.start(self, lambda events, stop: scan(path, options, mapping, events, stop))

    def refresh_scan_table(self):
        if not self.scan_result:
            self._ready_rows = 0; self.update_actions(); return
        self.scan_model.replace([dict(source=f'{source_name(row.source)} / {row.folder}',
            source_detail=f'{row.source}\nKonfigürasyon: {row.configuration}\nKesim grubu: {row.folder}',
            profile=row.profile, material=row.material, length=row.length, count=row.count,
            angle1=row.angle1, angle2=row.angle2, status=row.status) for row in self.scan_result.rows])
        s = self.scan_result.summary
        self._ready_rows = sum(r.ready for r in self.scan_result.rows)
        self.scan_summary.setText(f'{s["profiles"]} profil parçası bulundu · {self._ready_rows} satır hazır · '
            f'{s["review"]} kontrol gerekiyor · {s["excluded"]} hariç'
            + (f' · {s["unscanned"]} model okunamadı' if s['unscanned'] else ''))
        self.scan_summary.setToolTip(f'{s["parts"]} parça örneği · {s["weldments"]} Weldment · '
            f'Bilinen toplam boy {display(s["length"])} mm · {s["property_errors"]} özellik alanı sorunlu')
        self.update_actions()

    def edit_scan_cell(self, index, key, value):
        row = self.scan_result.rows[index]
        try:
            parsed = quantity(value) if key == 'count' else str(value)
            if key == 'length': number(parsed, 'Boy', positive=True)
            if key in ('angle1','angle2') and parsed and number(parsed, 'Açı') > 180:
                raise ValueError('Açı 0–180° olmalı.')
            setattr(row, key, parsed); row.reviewed = False; row.geometry_verified = False
            if 'Analiz verisi elle düzenlendi; kaynak/ham boy doğrulaması gerekir.' not in row.issues:
                row.issues.append('Analiz verisi elle düzenlendi; kaynak/ham boy doğrulaması gerekir.')
        except ValueError as error: self.set_status(str(error), True)
        self.refresh_scan_table()

    def review_selected(self):
        index = self.scan_view.currentIndex()
        if not index.isValid() or not self.scan_result: return
        position = self.scan_proxy.mapToSource(index).row(); row = self.scan_result.rows[position]
        if row.excluded:
            show_details(self, 'Profil kesimine uygun olmayan gövde', '\n'.join(row.issues)); return
        dialog = RowDialog(self, row)
        if dialog.exec() == QDialog.Accepted:
            self.scan_result.rows[position] = dialog.value; self.refresh_scan_table()

    def edit_mapping(self):
        dialog = MappingDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.mapping = dialog.mapping; self.settings.set('profile_property_mapping', deepcopy(self.mapping))
            self.set_status('Property eşleştirmesi kaydedildi. Yeni eşleştirme için verileri yenileyin.')

    def import_scan(self):
        if self.scan_result is None:
            self.set_status('Önce açık modeli veya bir SolidWorks dosyasını tarayın.', True); return
        if not self.scan_current:
            self.set_status('Bu tarama kaydedilmiş projeden geldi. Yeni aktarım için Verileri yenile düğmesini kullanın.', True); return
        stats = transfer(self.project, self.scan_result)
        if stats['added'] or stats['changed']: self.invalidate(); self.refresh_demands(); self.tabs.setCurrentIndex(0)
        self.set_status(f'{stats["added"]} satır eklendi · {stats["duplicate"]} tekrar aktarılmadı · '
            f'{stats["changed"]} değişmiş kaynak · {stats["blocked"]} inceleme/hariç. '
            + ('Değişmiş kaynağın önceki aktarımı korundu; yenisi için ilgili eski satırı seçip kaldırın.' if stats['changed'] else 'Manuel kayıtlar korundu.'),
            bool(stats['changed'] or stats['blocked']))

    def calculate(self):
        if not self.can_start(): return
        snapshot = deepcopy(self.project)
        try: snapshot.validate(require_current=True)
        except ValueError as error:
            self.tabs.setCurrentIndex(0)
            focused = False
            for key in ('stock_length','kerf','trim'):
                try: number(getattr(snapshot,key), positive=key=='stock_length')
                except ValueError:
                    if key == 'trim': self.stock_disclosure.set_expanded(True)
                    self.form.fields[key].setFocus(); focused = True; break
            if not focused and 2*number(snapshot.trim) >= number(snapshot.stock_length):
                self.stock_disclosure.set_expanded(True); self.form.fields['trim'].setFocus()
            self.set_status(str(error), True); return
        def operation(events, stop):
            try: events.put(('profile_plan', optimize(snapshot, stop=stop)))
            except Cancelled: events.put(('phase', 'Planlama durduruldu.'))
            except ValueError as error: events.put(('profile_plan_error', str(error)))
        self.jobs.start(self, operation)
        self.set_status('Kesim planı hesaplanıyor…')

    def handle_events(self, events):
        super().handle_events(events)
        for kind, value in events:
            if kind == 'phase': self.set_status(value)
            elif kind == 'profile_plan_error':
                self.tabs.setCurrentIndex(0); self.set_status(value, True)
            elif kind == 'connection_done':
                self.set_status('SolidWorks bağlantısı hazır · ' + value.get('revision','') if value['connected'] else value['error'], not value['connected'])
            elif kind == 'weldment_scan':
                self.scan_result = value; self.scan_current = True
                if reconcile(self.project, value): self.invalidate(); self.refresh_demands()
                self.refresh_scan_table(); self.tabs.setCurrentIndex(1)
                self.source_label.setText(f'{source_name(value.source)} · {value.configuration}')
                self.source_label.setToolTip(value.source)
                if value.unscanned:
                    failures=[d for d in value.diagnostics if d.get('configuration')]
                    detail=next((d.get('detail','') for d in failures or value.diagnostics),'Tarama ayrıntılarını açın.')
                    self.set_status(f'{value.unscanned} belge okunamadı. {detail}', True)
                elif not value.rows:
                    self.set_status('Bu konfigürasyonda Cut List bulunamadı. SolidWorks’te kesim listesini '
                                    'oluşturup/güncelleyip tekrar tarayın.', True)
                else:
                    self.set_status('Tarama tamamlandı. Hazır satırları aktarın; diğerlerini inceleyin.')
            elif kind == 'profile_plan':
                self.plan = value
                self.plan_model.replace([dict(bar=i+1, group=group_name(bar.group),
                    cuts=cut_pattern(bar), remaining=bar.remaining)
                    for i,bar in enumerate(value.bars)])
                totals = plan_totals(value)
                usage = format(totals['usage'], '.1f').replace('.', ',')
                self.plan_summary.setText(f'{totals["bars"]} çubuktan {totals["count"]} parça kesilecek · '
                    f'Çubuk boyu {mm(value.stock_length)} mm')
                self.plan_numbers.setText(f'Kullanım %{usage} · Artan profil {mm(totals["remaining"])} mm · '
                    f'Testere kaybı {mm(totals["saw"])} mm · Uç düzeltme kaybı {mm(totals["trim"])} mm')
                self.plan_numbers.setToolTip('Kullanım oranı: parça boyları + ilave boylar / toplam ham çubuk boyu. Testere ve uç düzeltmesi ayrıca kayıptır.')
                self.plan_proof.setText('Bu liste için en az çubuk adedi doğrulandı.' if value.optimal else
                    'Geçerli kesim planı. Daha az çubukla çözüm olamayacağı garanti edilmez.')
                self.plan_proof.setToolTip(value.method)
                self.plan_stack.setCurrentIndex(0)
                self.tabs.setCurrentIndex(2); self.plan_view.selectRow(0); self.draw_bar(0)
                self.set_status('Kesim planı miktar, malzeme grubu ve stok sınırlarına karşı doğrulandı.')
            elif kind == 'profile_io': self.set_status(value)
            elif kind == 'profile_project':
                project, result = value
                self.project = project
                for key in ('stock_length','kerf','trim'): self.form.set_value(key,getattr(project,key))
                self.scan_result = result; self.scan_current = False
                self.last_path = result.source if result is not None else None
                self.scan_model.replace([]); self.refresh_scan_table()
                self.source_label.setText('Kaydedilmiş tarama · Yeni aktarım için Verileri yenile düğmesini kullanın.')
                self.invalidate(); self.refresh_demands(); self.set_status('Proje açıldı; sonuç için yeniden hesaplayın.')
        self.update_actions()

    def draw_bar(self, index):
        if not self.plan or not 0 <= index < len(self.plan.bars): return
        self.cut_order.show_bar(self.plan, index)

    def theme_changed(self):
        if hasattr(self, 'plan_view'): self.draw_bar(max(0,self.plan_view.currentIndex().row()))

    def scan_details(self):
        if not self.scan_result: return
        lines = [f'{row.source} [{row.configuration}] / {row.folder} · {row.status}\n' +
                 '\n'.join(row.issues+row.errors()) + f'\nBoy kaynağı: {row.length_source} · {row.freshness}\nKaynak gösterim birimi: {row.display_unit or "okunamadı"} · Hesap: mm\n' +
                 '\n'.join(f'{p.name}: ham={p.raw} | çözümlenmiş={p.evaluated} | {p.status}' for p in row.properties.values())
                 for row in self.scan_result.rows]
        lines += [f'{value.get("source", "Kaynak")} [{value.get("configuration", "—")}]\n'
                  + str(value.get('detail') or '') for value in self.scan_result.diagnostics]
        show_details(self, 'Weldments · Tarama ayrıntıları', '\n\n'.join(lines) or 'Cut List bulunamadı.')

    def save_project(self):
        if not self.can_start(): return
        path,_ = QFileDialog.getSaveFileName(self, 'Profil kesim projesini kaydet', '', 'Profil projesi (*.gokprofile)')
        if not path: return
        project, result = deepcopy(self.project), deepcopy(self.scan_result)
        def operation(events,stop):
            try:
                save(project,result,path,stop=stop)
                events.put(('profile_io','Profil kesim projesi kaydedildi.'))
            except Cancelled: events.put(('phase','Proje kaydı durduruldu; önceki dosya korundu.'))
        self.jobs.start(self,operation)

    def open_project(self):
        if not self.can_start(): return
        path,_ = QFileDialog.getOpenFileName(self, 'Profil kesim projesini aç', '', 'Profil projesi (*.gokprofile)')
        if not path: return
        from PySide6.QtWidgets import QMessageBox
        if self.project.demands and QMessageBox.question(self, 'Mevcut liste', 'Proje açılınca mevcut kesim listesi değişecek. Devam edilsin mi?') != QMessageBox.Yes: return
        def operation(events,stop):
            try:
                checkpoint(stop); result=load(path); checkpoint(stop)
                events.put(('profile_project',result))
            except Cancelled: events.put(('phase','Proje açma durduruldu; önceki liste korundu.'))
        self.jobs.start(self,operation)

    def report(self):
        if not self.can_start(): return
        path,_ = QFileDialog.getSaveFileName(self, 'Kesim ve tarama raporunu kaydet', '', 'CSV (*.csv)')
        if not path: return
        project, result, plan = deepcopy(self.project), deepcopy(self.scan_result), deepcopy(self.plan)
        def operation(events,stop):
            try:
                export_report(project,result,plan,path,stop=stop)
                events.put(('profile_io','CSV raporu kaydedildi.'))
            except Cancelled: events.put(('phase','Rapor kaydı durduruldu; yarım rapor yayımlanmadı.'))
        self.jobs.start(self,operation)
