"""GOKWORKS transfer workspace; all scanning, COM and reports run as jobs."""

from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QCheckBox, QFileDialog, QTableView, QAbstractItemView, QListWidget, QListWidgetItem,
    QProgressBar, QComboBox)

from gui_qt.components import (BasePage, ValueForm, ResultsPanel, TransferWorkspace,
    Disclosure, card, button, label, configure_view, open_folder)
from gui_qt.models import TableModel, Column, FilterProxy, LABELS
from .formats import FORMATS
from .models import Source, Options, Cancelled
from .scanner import scan
from .exporter import convert, inspect_configurations
from .report import write_report

CONFIGURATIONS = {'Aktif konfigürasyon': 'active', 'Bütün konfigürasyonlar': 'all', 'Seçilen konfigürasyonlar': 'selected'}
ASSEMBLIES = {'Montajı tek dosya aktar': 'single', 'Bileşenleri ayrı aktar': 'components'}
NAMING = {'Orijinal dosya adı': 'original', 'Dosya adı + konfigürasyon': 'configuration', 'Dosya adı + format': 'format'}
QUALITY = {'Kaba': 'coarse', 'Orta': 'medium', 'Yüksek': 'fine', 'Özel': 'custom'}


class CadResults(ResultsPanel):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.model = TableModel((Column('Kaynak dosya', 'path'), Column('Tür', 'type'),
            Column('Konfigürasyon', 'configuration'), Column('Format', 'format'),
            Column('Durum', 'status', lambda value: 'Uyarılı' if value == 'partial' else LABELS.get(value, value)),
            Column('Açıklama', 'detail'), Column('Çıktı', 'output')))
        self.proxy.setSourceModel(self.model)
        self.table.setColumnWidth(0, 220); self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 150); self.table.setColumnWidth(3, 180)
        self.tabs.setTabText(0, 'İşlem sonuçları')

    def job_row(self, value, *, completed=False):
        row = dict(value)
        row['path'] = row['source']
        row['type'] = Path(row['path']).suffix.upper().lstrip('.')
        row['source'] = repr((row['path'], row.get('configuration', ''), row.get('format', '')))
        self.model.upsert(row)
        if completed:
            self.results.append(dict(value))
            self.append_log(f"{row.get('status')} · {Path(row['path']).name} · {row.get('configuration', '')} · {row.get('format', '')} · {row.get('detail', '')}")
        self.refresh_count()

    def save_dialog(self):
        self.page.save_report()

    def refresh_count(self, *args):
        super().refresh_count(*args)
        self.counter.setText(f'{self.proxy.rowCount()} / {self.model.rowCount()} işlem satırı · {len(self.results)} tamamlanan')


class CadConverterPage(BasePage):
    def __init__(self, context):
        super().__init__(context, '3D Dönüştürücü', 'Parça ve montajları birden fazla CAD formatına toplu aktarın.')
        self.sources = []
        # Source selection stays above the settings scroll area. It is the
        # first action in the workflow and must not live beside the run button.
        self.source_panel, source_body = card('Kaynak dosyaları')
        self.scan_button = button('Dosyaları seç…', self.add_files, primary=True)
        self.folder_button = button('Kaynak klasörü seç…', self.add_folder)
        source_body.addWidget(self.scan_button)
        source_body.addWidget(self.folder_button)
        self.source_form = ValueForm(self.settings, 'cad_converter_')
        self.source_form.check('recursive', 'Alt klasörleri tara', True)
        source_body.addWidget(self.source_form)
        self.source_count = label('SLDPRT / SLDASM · Dosya seçilmedi.', 'muted')
        source_body.addWidget(self.source_count)
        self.start_button = self.action('Aktarımı başlat', self.start_export, primary=True)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        self.stop_button.setEnabled(False)
        panel, body = card('Çıktı ve formatlar')
        self.form = ValueForm(self.settings, 'cad_converter_')
        self.form.path('output', 'Çıktı klasörü')
        self.form.fields.update(self.source_form.fields)
        body.addWidget(self.form); self.form.stack_fields()
        self.remove_button = button('Seçileni kaldır', self.remove_selected)
        formats_widget = QWidget(); grid = QGridLayout(formats_widget)
        grid.setContentsMargins(0, 0, 0, 0); grid.setSpacing(5)
        self.format_checks = {}
        for index, fmt in enumerate(FORMATS):
            title = {'xt': 'Parasolid X_T', 'xb': 'Parasolid X_B'}.get(fmt.key, fmt.label.replace(' · MBD lisansı', ' · MBD'))
            check = QCheckBox(title)
            check.setToolTip('SolidWorks MBD lisansı ve PublishSTEP242File desteği gerekir.' if fmt.protocol == 242 else fmt.label)
            check.setChecked(self.settings.get('cad_converter_format_' + fmt.key, fmt.key == 'step214') is True)
            check.toggled.connect(lambda checked, key=fmt.key: self.settings.set('cad_converter_format_' + key, checked))
            check.toggled.connect(self.update_choices)
            self.format_checks[fmt.key] = check
            grid.addWidget(check, index, 0)
        body.addWidget(label('Çıktı formatları', 'section')); body.addWidget(formats_widget)

        self.model_form = ValueForm(self.settings, 'cad_converter_')
        self.model_form.combo('configurations', 'Konfigürasyon', CONFIGURATIONS)
        self.model_form.text('selected', 'Seçilen adlar · noktalı virgülle ayırın')
        self.config_button = button('Konfigürasyonları oku', self.read_configurations)
        self.config_list = QListWidget(); self.config_list.setMaximumHeight(120)
        self.config_list.itemChanged.connect(self.selected_names_changed)
        self.model_form.form.addRow(self.config_button); self.model_form.form.addRow(self.config_list)
        self.model_form.combo('assembly_mode', 'Montaj aktarımı', ASSEMBLIES)
        self.model_form.check('include_subassemblies', 'Alt montajları da ayrı aktar', False)
        self.model_form.stack_fields()
        body.addWidget(self.model_form)

        self.naming_form = ValueForm(self.settings, 'cad_converter_')
        self.naming_form.combo('naming', 'Dosya adı', NAMING)
        self.naming_form.text('prefix', 'Ön ek'); self.naming_form.text('suffix', 'Son ek')
        self.naming_form.check('preserve_folders', 'Kaynak alt klasörlerini koru', False)
        self.naming_form.check('overwrite', 'Mevcut çıktıların üzerine yaz', False)
        self.naming_form.stack_fields()
        body.addWidget(Disclosure('İsimlendirme ve kayıt', self.naming_form))

        self.stl_form = ValueForm(self.settings, 'cad_converter_')
        self.stl_form.combo('stl_unit', 'STL birimi', ('mm', 'inch'), 'mm')
        self.stl_form.combo('stl_quality', 'Mesh kalitesi', QUALITY, 'Orta')
        self.stl_form.text('deviation', 'Özel sapma · mm', '.1')
        self.stl_form.text('angle', 'Özel açı toleransı · °', '15')
        self.stl_form.form.addRow(label('STL üçgen mesh taşır; STEP/Parasolid gibi B-Rep değildir. Montaj gövdeleri aynı STL dosyasına yazılır; montaj ağacı korunmaz.', 'muted'))
        self.stl_form.stack_fields()
        self.stl_options = Disclosure('STL ayarları', self.stl_form)
        body.addWidget(self.stl_options)
        body.addWidget(label('Kaynak CAD dosyaları kaydedilmez. AP242, MBD yayınlamasıdır; PMI içeriğinin eksiksizliği ayrıca kontrol edilir.', 'muted'))
        body.addWidget(button('Çıktı klasörünü aç', lambda: open_folder(self.form.value('output')) if self.form.value('output') else None))
        body.addStretch()
        self.controls.extend((self.source_panel, self.scan_button, panel, self.folder_button, self.remove_button, self.config_button))

        self.results = CadResults(self)
        self.files_model = TableModel((Column('Kaynak dosya', 'source'), Column('Tür', 'type'),
            Column('Konfigürasyon', 'configuration'), Column('Çıktı formatları', 'format'),
            Column('Durum', 'status', lambda v: LABELS.get(v, v))))
        self.files_proxy = FilterProxy(self)
        self.files_proxy.setSourceModel(self.files_model)
        self.files_view = configure_view(QTableView()); self.files_view.setModel(self.files_proxy)
        self.files_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.files_view.setColumnWidth(0, 260)
        inventory = QWidget(); inventory_layout = QVBoxLayout(inventory)
        inventory_layout.setContentsMargins(0, 0, 0, 0)
        inventory_tools = QHBoxLayout()
        self.type_filter = QComboBox(); self.type_filter.addItems(('Bütün modeller', 'Yalnız parçalar', 'Yalnız montajlar'))
        self.type_filter.currentIndexChanged.connect(self.refresh_sources)
        inventory_tools.addWidget(self.type_filter); inventory_tools.addStretch(); inventory_tools.addWidget(self.remove_button)
        inventory_layout.addLayout(inventory_tools)
        self.empty_hint = label('Başlamak için soldaki Dosyaları seç veya Kaynak klasörü seç düğmesini kullanın.', 'muted')
        inventory_layout.addWidget(self.empty_hint)
        inventory_layout.addWidget(self.files_view)
        inventory_layout.addWidget(label('Çoklu seçim: Ctrl / Shift · Dosya veya klasörleri pencereye bırakabilirsiniz.', 'muted'))
        self.results.tabs.insertTab(0, inventory, 'Dosyalar')
        self.results.tabs.setCurrentIndex(0)
        self.results.search.textChanged.connect(self.files_proxy.set_query)
        self.results.cleared.connect(self.clear_sources)
        self.progress = QProgressBar(); self.progress.setRange(0, 1); self.progress.setValue(0)
        self.results.layout.addWidget(self.progress)
        self.counts = label('0 başarılı · 0 uyarılı · 0 atlanan · 0 hatalı', 'muted')
        self.results.layout.addWidget(self.counts)
        self.splitter = TransferWorkspace(self, panel, self.results)
        self.splitter.source_column.layout().insertWidget(0, self.source_panel)
        self.source_scroll = self.splitter.source_scroll
        self.layout.addWidget(self.splitter, 1)
        self.controls.append(self.type_filter)
        for form in (self.source_form, self.form, self.model_form, self.naming_form, self.stl_form):
            form.changed.connect(self.update_choices)
        self.setAcceptDrops(True)
        self.update_choices()
        self.finish_layout()

    def selected_names_changed(self):
        names = [self.config_list.item(i).text() for i in range(self.config_list.count()) if self.config_list.item(i).checkState() == Qt.Checked]
        self.model_form.set_value('selected', '; '.join(names))

    def update_choices(self, *args):
        if not hasattr(self, 'results'): return
        selected = self.model_form.value('configurations') == 'Seçilen konfigürasyonlar'
        self.model_form.show_field('selected', selected)
        self.config_list.setVisible(selected and self.config_list.count() > 0)
        self.model_form.show_field('include_subassemblies', self.model_form.value('assembly_mode') == 'Bileşenleri ayrı aktar')
        self.stl_options.setVisible(any(self.format_checks[key].isChecked() for key in ('stl_binary', 'stl_ascii')))
        custom = self.stl_form.value('stl_quality') == 'Özel'
        self.stl_form.show_field('deviation', custom); self.stl_form.show_field('angle', custom)
        self.refresh_sources()

    def refresh_sources(self):
        if not hasattr(self, 'files_model'): return
        suffix = {1: '.sldprt', 2: '.sldasm'}.get(self.type_filter.currentIndex())
        formats = ', '.join(fmt.label for fmt in FORMATS if self.format_checks[fmt.key].isChecked())
        configuration = self.model_form.value('configurations')
        self.files_model.replace([dict(source=s.path, type=Path(s.path).suffix.upper().lstrip('.'),
            configuration=configuration, format=formats, status='pending')
            for s in self.sources if suffix is None or Path(s.path).suffix.casefold() == suffix])
        self.source_count.setText(f'{len(self.sources)} kaynak model · {self.files_model.rowCount()} görünür' if self.sources else 'SLDPRT / SLDASM · Dosya seçilmedi.')
        self.source_count.setToolTip('\n'.join(s.path for s in self.sources))
        self.empty_hint.setVisible(not self.sources)
        self.results.tabs.setTabText(0, f'Dosyalar · {len(self.sources)}')

    def clear_sources(self):
        self.sources.clear(); self.config_list.clear()
        self.progress.setRange(0, 1); self.progress.setValue(0)
        self.counts.setText('0 başarılı · 0 uyarılı · 0 atlanan · 0 hatalı')
        self.refresh_sources(); self.set_status('Dosya listesi, sonuçlar ve günlük temizlendi.')

    def remove_selected(self):
        if self.busy: return
        selected = {index.data(Qt.UserRole)['source'] for index in self.files_view.selectionModel().selectedRows()}
        self.sources = [s for s in self.sources if s.path not in selected]
        self.refresh_sources()

    def add_files(self):
        if not self.can_start(): return
        paths, _ = QFileDialog.getOpenFileNames(self, 'Kaynak SolidWorks modellerini seç',
            self.settings.get('cad_converter_source_folder', ''), 'SolidWorks 3D (*.sldprt *.SLDPRT *.sldasm *.SLDASM)')
        if paths: self.add_paths(paths)

    def add_folder(self):
        if not self.can_start(): return
        path = QFileDialog.getExistingDirectory(self, 'Kaynak model klasörünü seç', self.settings.get('cad_converter_source_folder', ''))
        if path:
            self.settings.set('cad_converter_source_folder', path)
            self.add_paths([path])

    def add_paths(self, paths):
        if not self.can_start(): return
        recursive = self.form.value('recursive'); existing = tuple(self.sources)
        def operation(sink, stop):
            try:
                sources, issues = scan(paths, recursive=recursive, existing=existing, stop=stop)
                sink.put(('cad_sources', sources))
                sink.put(('cad_scan_done', issues))
            except Cancelled:
                sink.put(('phase', 'Tarama durduruldu; mevcut liste korundu.'))
        self.jobs.start(self, operation)

    def dragEnterEvent(self, event):
        if not self.jobs.busy and event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.jobs.busy:
            self.add_paths([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
            event.acceptProposedAction()

    def options(self):
        def number(value): return float(str(value).replace(',', '.'))
        custom = self.stl_form.value('stl_quality') == 'Özel' and any(self.format_checks[key].isChecked() for key in ('stl_binary', 'stl_ascii'))
        result = Options(self.form.value('output'),
            tuple(fmt.key for fmt in FORMATS if self.format_checks[fmt.key].isChecked()),
            CONFIGURATIONS[self.model_form.value('configurations')],
            tuple(n.strip() for n in self.model_form.value('selected').split(';') if n.strip()),
            ASSEMBLIES[self.model_form.value('assembly_mode')], self.model_form.value('include_subassemblies'),
            NAMING[self.naming_form.value('naming')], self.naming_form.value('prefix'), self.naming_form.value('suffix'),
            self.naming_form.value('preserve_folders'), self.naming_form.value('overwrite'),
            self.stl_form.value('stl_unit'), QUALITY[self.stl_form.value('stl_quality')],
            number(self.stl_form.value('deviation')) if custom else .1, number(self.stl_form.value('angle')) if custom else 15)
        result.validate(); return result

    def start_export(self):
        if not self.can_start(): return
        try:
            options = self.options()
            if not self.sources: raise ValueError('Önce SLDPRT veya SLDASM dosyası ekleyin.')
        except (ValueError, KeyError) as error:
            return self.set_status(str(error), True)
        sources = tuple(self.sources)
        self.results.reset(); self.results.tabs.setCurrentIndex(1)
        self.progress.setRange(0, 0)
        self.settings.flush()
        self.jobs.start(self, lambda sink, stop: convert(sources, options, sink, stop))

    def read_configurations(self):
        if not self.can_start(): return
        if not self.sources: return self.set_status('Önce kaynak model ekleyin.', True)
        self.config_list.clear()
        sources = tuple(self.sources)
        self.jobs.start(self, lambda sink, stop: inspect_configurations(sources, sink, stop))

    def save_report(self):
        if not self.can_start(): return
        if not self.results.results: return self.set_status('Önce aktarım yapın; rapora yazılacak sonuç yok.', True)
        path, _ = QFileDialog.getSaveFileName(self, 'CAD aktarım raporu', 'CAD-aktarim.csv', 'CSV (*.csv);;Excel (*.xlsx)')
        if not path: return
        rows = [dict(row) for row in self.results.results]
        def operation(sink, stop):
            write_report(rows, path)
            sink.put(('phase', 'Rapor kaydedildi: ' + path))
        self.jobs.start(self, operation)

    def set_busy(self, busy):
        super().set_busy(busy)
        self.results.set_busy(busy)
        self.results.save.setEnabled(not busy); self.results.report_menu.setEnabled(not busy)

    @Slot(object)
    def handle_events(self, events):
        for kind, value in events:
            if kind == 'cad_sources':
                self.sources.extend(value); self.refresh_sources()
            elif kind == 'cad_scan_done':
                for issue in value: self.results.append_log(issue)
                self.results.tabs.setCurrentIndex(0)
                self.set_status(f'{len(self.sources)} kaynak model hazır.' + (f' {len(value)} öğe eklenemedi; günlükte ayrıntı var.' if value else ''), bool(value))
            elif kind == 'cad_configurations':
                existing = {self.config_list.item(i).text() for i in range(self.config_list.count())}
                selected = {n.strip() for n in self.model_form.value('selected').split(';')}
                blocked = self.config_list.blockSignals(True)
                for name in value['names']:
                    if name not in existing:
                        item = QListWidgetItem(name); item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                        item.setCheckState(Qt.Checked if name in selected else Qt.Unchecked)
                        self.config_list.addItem(item); existing.add(name)
                self.config_list.blockSignals(blocked)
                self.update_choices(); self.set_status('Konfigürasyonlar okundu. Seçilen konfigürasyonlar modunda işaretleyebilirsiniz.')
            elif kind == 'cad_current': self.results.job_row(dict(value, status='running'))
            elif kind == 'cad_result': self.results.job_row(value, completed=True)
            elif kind == 'cad_counts':
                self.counts.setText(f"{value['processed']} işlem · {value['succeeded']} başarılı · {value['warned']} uyarılı · {value['skipped']} atlanan · {value['failed']} hatalı")
            elif kind == 'progress': self.progressChanged.emit(*value)
            elif kind == 'cad_done':
                self.progress.setRange(0, max(1, value['processed'])); self.progress.setValue(value['processed'])
                if value['state'] == 'error': self.set_status(value['error'], True)
                elif value['state'] == 'cancelled': self.set_status('Durduruldu; tamamlanan çıktılar korundu, yeni aktarım başlatılmadı.')
                else: self.set_status(f"Tamamlandı · {value['succeeded']} başarılı, {value['warned']} uyarılı, {value['skipped']} atlanan, {value['failed']} hatalı", value['failed'] > 0)
            elif kind in ('phase', 'log'):
                self.set_status(value)
                if kind == 'log': self.results.append_log(value)
            elif kind == 'job_error': self.set_status(value['error'], True); self.results.append_log(value['error'])
