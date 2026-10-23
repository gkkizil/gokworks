"""Integrated, asynchronous profile cut-list and Weldments workflow."""

from copy import deepcopy
from dataclasses import asdict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QTableView, QFileDialog, QAbstractItemView, QDialog, QLineEdit, QComboBox)

from gui_qt.components import BasePage, ValueForm, Disclosure, label, button, configure_view, show_details, scroll
from gui_qt.models import TableModel, FilterProxy, Column
from gui_qt.diagrams import EngineeringDiagram
from gui_qt.services import check_connection
from .models import Project, quantity, number, transfer, reconcile, checkpoint
from .properties import DEFAULT_MAPPING, validate_mapping
from .scanner import scan, Options, Cancelled
from .optimizer import optimize
from .dialogs import MappingDialog, RowDialog
from .storage import save, load, export_report


def display(value): return str(value).replace('.', ',')


class ProfileTableModel(TableModel):
    def data(self,index,role=Qt.DisplayRole):
        if role == Qt.TextAlignmentRole and index.isValid() and self.columns[index.column()].key in ('length','count','allowance','angle1','angle2','remaining','bar'):
            return Qt.AlignRight | Qt.AlignVCenter
        return super().data(index,role)


class ProfileCuttingPage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'Profil kesim optimizasyonu',
                         'Weldments profillerini tarayın veya elle girin; stok boyuna göre kesim planı oluşturun.')
        self.project, self.scan_result, self.plan = Project(), None, None
        self.last_path = None
        self.scan_current = False
        try: self.mapping = validate_mapping(deepcopy(self.settings.get('profile_property_mapping', DEFAULT_MAPPING)))
        except ValueError: self.mapping = deepcopy(DEFAULT_MAPPING)
        self.run_button = self.action('Kesim planını hesapla', self.calculate, primary=True)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        self.tabs = QTabWidget(); self.layout.addWidget(self.tabs, 1)

        cut_page = QWidget(); cut_layout = QVBoxLayout(cut_page)
        cut_layout.setContentsMargins(0, 8, 0, 0)
        tools = QHBoxLayout()
        for text, callback in (('Manuel profil ekle', self.add_manual), ('Seçileni kaldır', self.remove),
                               ('Proje aç', self.open_project), ('Kaydet', self.save_project)):
            control = button(text, callback); tools.addWidget(control); self.controls.append(control)
        tools.addStretch(); cut_layout.addLayout(tools)
        self.form = ValueForm(self.settings, 'profile_cutting_')
        for key, text, default in (('stock_length','Stok boyu · mm','6000'), ('kerf','Testere payı · mm / kesim','3'),
                                   ('trim','Uç düzeltme · mm / bir uç','0')):
            self.form.text(key, text, default)
            setattr(self.project, key, self.form.value(key))
        cut_layout.addWidget(self.form)
        self.demand_model = ProfileTableModel((Column('Profil', 'profile'), Column('Malzeme', 'material'),
            Column('Boy · mm','length',display), Column('Adet','count'), Column('Ek ham boy · mm','allowance',display),
            Column('Kaynak','source')), editable=('profile','material','length','count','allowance'))
        self.demands = configure_view(QTableView()); self.demands.setModel(self.demand_model)
        for i,width in enumerate((180,110,100,70,140,300)): self.demands.setColumnWidth(i,width)
        self.demands.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.demand_model.edited.connect(self.edit_demand_cell)
        cut_layout.addWidget(self.demands, 1)
        self.demand_summary = label('Kesim listesi boş. Manuel profil ekleyin veya SolidWorks taramasını aktarın.', 'muted')
        cut_layout.addWidget(self.demand_summary)
        cut_layout.addWidget(label('Her parçada nominal boy + ek ham boy + testere payı tüketilir. İki stok ucunun düzeltmesi ayrıca düşülür. Farklı kesit/et/malzeme/standart/stok kodu ayrı stok havuzudur.', 'muted'))
        self.tabs.addTab(cut_page, 'Kesim listesi')

        sw_page = QWidget(); sw_layout = QVBoxLayout(sw_page); sw_layout.setContentsMargins(0,8,0,0)
        grid = self.source_grid = QGridLayout(); grid.setSpacing(6)
        self.connect_button = button('SolidWorks’e bağlan', self.connect)
        self.scan_button = button('Açık modeli tara', lambda: self.start_scan(None), primary=True)
        self.file_button = button('SolidWorks dosyası seç', self.choose_source)
        self.refresh_button = button('Verileri yenile', self.refresh_scan)
        self.transfer_button = button('Kesim optimizasyonuna aktar', self.import_scan, primary=True)
        self.mapping_button = button('Property eşleştirmesi', self.edit_mapping)
        self.source_actions = (self.connect_button, self.scan_button, self.file_button,
                               self.refresh_button, self.transfer_button, self.mapping_button)
        for control in self.source_actions: self.controls.append(control)
        self.source_columns = 0
        self.reflow_source()
        sw_layout.addLayout(grid)
        self.scan_options = ValueForm(self.settings, 'weldment_')
        self.scan_options.check('update_cut_list', 'Tararken Cut List’i güncelle (kaynak dosya kaydedilmez)', False)
        self.scan_options.check('geometry_length', 'Eksik LENGTH için yalnız doğrulanmış doğrusal geometriden boy al', False)
        sw_layout.addWidget(Disclosure('Tarama seçenekleri', self.scan_options))
        self.source_label = label('1 · Modeli tara   →   2 · İnceleme gereken satırları doğrula   →   3 · Kesim listesine aktar', 'muted')
        sw_layout.addWidget(self.source_label)
        self.search = QLineEdit(); self.search.setPlaceholderText('Kaynak, profil veya Cut List ara…')
        self.status_filter = QComboBox()
        self.status_filter.addItems(('Tüm sonuçlar','Hazır','İnceleme Gerekli','Hariç'))
        search_row = QHBoxLayout(); search_row.addWidget(self.search,1); search_row.addWidget(self.status_filter)
        sw_layout.addLayout(search_row)
        self.scan_model = ProfileTableModel((Column('Kaynak / Cut List','source'), Column('Profil','profile'),
            Column('Malzeme','material'), Column('Boy · mm','length',display), Column('Adet','count'),
            Column('Açı 1 · °','angle1'), Column('Açı 2 · °','angle2'), Column('Durum','status')),
            editable=('profile','material','length','count','angle1','angle2'))
        self.scan_proxy = FilterProxy(self); self.scan_proxy.setSourceModel(self.scan_model)
        self.status_filter.currentIndexChanged.connect(lambda i:self.scan_proxy.set_status(None if i==0 else self.status_filter.currentText()))
        self.scan_view = configure_view(QTableView()); self.scan_view.setModel(self.scan_proxy)
        self.scan_view.setMinimumHeight(180)
        for i,width in enumerate((270,160,95,90,60,70,70,140)): self.scan_view.setColumnWidth(i,width)
        self.scan_view.doubleClicked.connect(lambda _: self.review_selected())
        self.scan_model.edited.connect(self.edit_scan_cell)
        self.search.textChanged.connect(self.scan_proxy.set_query)
        sw_layout.addWidget(self.scan_view, 1)
        self.scan_summary = label('Henüz tarama yapılmadı.', 'muted'); sw_layout.addWidget(self.scan_summary)
        row = QHBoxLayout()
        for text, callback in (('Seçili satırı incele', self.review_selected), ('Tarama ayrıntıları', self.scan_details),
                               ('CSV raporu', self.report)):
            control = button(text, callback); row.addWidget(control); self.controls.append(control)
        row.addStretch(); sw_layout.addLayout(row)
        sw_layout.addWidget(label('Angle1/Angle2 kaynak property açısıdır; testere açı ayarı değildir. Hariç ve inceleme gereken satırlar aktarılmaz. Aktarım mevcut manuel listeye eklenir.', 'muted'))
        sw_scroll = scroll(sw_page)
        sw_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tabs.addTab(sw_scroll, 'SolidWorks taraması')

        plan_page = QWidget(); plan_layout = QVBoxLayout(plan_page); plan_layout.setContentsMargins(0,8,0,0)
        self.plan_summary = label('Kesim listesi ve stok ayarlarını tamamlayıp hesaplayın.', 'muted')
        plan_layout.addWidget(self.plan_summary)
        self.diagram = EngineeringDiagram(width=650, height=190)
        self.diagram.setMinimumHeight(130); self.diagram.setMaximumHeight(230)
        plan_layout.addWidget(self.diagram)
        self.plan_model = ProfileTableModel((Column('Stok','bar'), Column('Profil / malzeme','group'),
            Column('Kesim sırası · nominal + ek boy (mm)','cuts'), Column('Kalan · mm','remaining',display)))
        self.plan_view = configure_view(QTableView()); self.plan_view.setModel(self.plan_model)
        for i,width in enumerate((70,280,520,130)): self.plan_view.setColumnWidth(i,width)
        self.plan_view.selectionModel().currentRowChanged.connect(lambda index, _: self.draw_bar(index.row()))
        plan_layout.addWidget(self.plan_view, 1)
        self.report_button = button('Kesim / tarama raporunu kaydet', self.report)
        plan_layout.addWidget(self.report_button)
        self.tabs.addTab(plan_page, 'Kesim planı')
        self.controls.extend((self.form, self.scan_options, self.demands, self.scan_view, self.report_button))
        self.form.changed.connect(self.options_changed)
        self.finish_layout(); self.refresh_demands()

    def reflow_source(self):
        columns = 3 if self.width()-32 >= 800 else 2
        if columns == self.source_columns: return
        for control in self.source_actions: self.source_grid.removeWidget(control)
        for i,control in enumerate(self.source_actions): self.source_grid.addWidget(control,i//columns,i%columns)
        for i in range(3): self.source_grid.setColumnStretch(i,1 if i<columns else 0)
        self.source_columns = columns

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'source_actions'): self.reflow_source()

    def invalidate(self):
        self.plan = None; self.plan_model.replace([]); self.diagram.vector.delete('all')
        self.plan_summary.setText('Liste veya ayarlar değişti; kesim planını yeniden hesaplayın.')

    def options_changed(self, key):
        setattr(self.project, key, self.form.value(key)); self.invalidate()

    def refresh_demands(self):
        self.demand_model.replace([dict(asdict(row), source=(row.source_changed+' '+row.source if row.source_changed else row.source),
                                       status='error' if row.source_changed else '') for row in self.project.demands])
        stale = sum(bool(row.source_changed) for row in self.project.demands)
        self.demand_summary.setText(f'{len(self.project.demands)} satır · {sum(row.count for row in self.project.demands)} profil'
            + (f' · {stale} değişmiş kaynak: güncel satırları yeniden aktarın.' if stale else ''))

    def add_manual(self):
        dialog = RowDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.project.demands.append(dialog.value); self.invalidate(); self.refresh_demands()

    def edit_demand_cell(self, index, key, value):
        row = self.project.demands[index]; previous = getattr(row, key)
        try:
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
        options = Options(self.scan_options.value('update_cut_list'), self.scan_options.value('geometry_length'))
        mapping = deepcopy(self.mapping)
        self.jobs.start(self, lambda events, stop: scan(path, options, mapping, events, stop))

    def refresh_scan_table(self):
        if not self.scan_result: return
        self.scan_model.replace([dict(source=f'{row.source} [{row.configuration}] / {row.folder}',
            profile=row.profile, material=row.material, length=row.length, count=row.count,
            angle1=row.angle1, angle2=row.angle2, status=row.status) for row in self.scan_result.rows])
        s = self.scan_result.summary
        self.scan_summary.setText(f'{s["parts"]} parça örneği · {s["weldments"]} Weldment dosya/konfigürasyonu · '
            f'{s["profiles"]} profil · bilinen boy {display(s["length"])} mm · '
            f'{s["property_errors"]} property alanı sorunlu · {s["review"]} inceleme · {s["excluded"]} hariç · {s["unscanned"]} taranamayan')

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
        except ValueError as error: self.set_status(str(error), True); return
        def operation(events, stop):
            try: events.put(('profile_plan', optimize(snapshot, stop=stop)))
            except Cancelled: events.put(('phase', 'Planlama durduruldu.'))
        self.jobs.start(self, operation)

    def handle_events(self, events):
        super().handle_events(events)
        for kind, value in events:
            if kind == 'phase': self.set_status(value)
            elif kind == 'connection_done':
                self.set_status('SolidWorks bağlantısı hazır · ' + value.get('revision','') if value['connected'] else value['error'], not value['connected'])
            elif kind == 'weldment_scan':
                self.scan_result = value; self.scan_current = True
                if reconcile(self.project, value): self.invalidate(); self.refresh_demands()
                self.refresh_scan_table(); self.tabs.setCurrentIndex(1)
                self.source_label.setText(f'{value.source} [{value.configuration}]')
                self.set_status('Tarama tamamlandı. Hazır satırları aktarın; diğerlerini inceleyin.', bool(value.unscanned))
            elif kind == 'profile_plan':
                self.plan = value
                self.plan_model.replace([dict(bar=i+1, group=' / '.join(v for v in bar.group if v),
                    cuts=' | '.join(f'{cut.length}+{cut.allowance}' for cut in bar.cuts), remaining=bar.remaining)
                    for i,bar in enumerate(value.bars)])
                self.plan_summary.setText(f'{len(value.bars)} stok · {sum(len(b.cuts) for b in value.bars)} kesim · '
                    f'toplam kalan {display(sum(number(b.remaining) for b in value.bars))} mm\n{value.method}')
                self.tabs.setCurrentIndex(2); self.plan_view.selectRow(0); self.draw_bar(0)
                self.set_status('Kesim planı miktar, malzeme grubu ve stok sınırlarına karşı doğrulandı.')
            elif kind == 'profile_io': self.set_status(value)
            elif kind == 'profile_project':
                project, result = value
                self.project = project
                for key in ('stock_length','kerf','trim'): self.form.set_value(key,getattr(project,key))
                self.scan_result = result; self.scan_current = False
                self.scan_model.replace([]); self.refresh_scan_table()
                self.source_label.setText('Kaydedilmiş tarama · Yeni aktarım için Verileri yenile düğmesini kullanın.')
                self.invalidate(); self.refresh_demands(); self.set_status('Proje açıldı; sonuç için yeniden hesaplayın.')

    def draw_bar(self, index):
        if not self.plan or not 0 <= index < len(self.plan.bars): return
        bar, plan = self.plan.bars[index], self.plan
        def draw(scene):
            scene.delete('all')
            dark = self.context.appearance == 'dark'
            text = '#E8EEF7' if dark else '#203550'
            scene.configure(background='#1C2533' if dark else '#F4F7FC')
            scene.create_text(325, 18, text=f'{index+1}. stok · ' + ' / '.join(v for v in bar.group if v),
                              fill=text, width=630, font=('Segoe UI',-12,'bold'))
            scale = 610/float(plan.stock_length); left = 20+float(plan.trim)*scale
            scene.create_rectangle(20,60,630,110,outline=text,tags='stock')
            for cut in bar.cuts:
                width = float(cut.consumption)*scale
                scene.create_rectangle(left,60,left+width,110,fill='#80B6F5',outline=text,tags='cut')
                if width > 40: scene.create_text(left+width/2,85,text=display(cut.length),fill='#10233A',font=('Segoe UI',-11))
                left += width
            scene.create_text(325, 145, text=f'Stok {display(plan.stock_length)} mm · Kalan {display(bar.remaining)} mm · '
                f'Testere {display(plan.kerf)} mm / kesim', fill=text, width=630,font=('Segoe UI',-12))
        self.diagram.render_geometry(draw)

    def theme_changed(self):
        if hasattr(self, 'plan_view'): self.draw_bar(max(0,self.plan_view.currentIndex().row()))

    def scan_details(self):
        if not self.scan_result: return
        lines = [f'{row.source} [{row.configuration}] / {row.folder} · {row.status}\n' +
                 '\n'.join(row.issues+row.errors()) + f'\nBoy kaynağı: {row.length_source} · {row.freshness}\nKaynak gösterim birimi: {row.display_unit or "okunamadı"} · Hesap: mm\n' +
                 '\n'.join(f'{p.name}: ham={p.raw} | çözümlenmiş={p.evaluated} | {p.status}' for p in row.properties.values())
                 for row in self.scan_result.rows]
        lines += [str(value) for value in self.scan_result.diagnostics]
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
