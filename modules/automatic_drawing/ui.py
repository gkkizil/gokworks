"""One drawing workbench and one editable file/configuration/assembly tree."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QProgressBar, QSplitter,
    QStyledItemDelegate, QTabWidget, QTableWidget, QTableWidgetItem, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget)

from gui_qt.components import (BasePage, AdaptiveRow, Disclosure, NumberSpinBox, button,
    configure_view, fit_columns, label, pane, scroll)
from .models import Options, PAPERS, STAGES, Source
from .pipeline import worker
from .outputs import write_batch_report
from .rules import CLASS_TITLES


def parse_scales(text):
    result = []
    for token in text.split(';'):
        pieces = token.strip().replace(',', '.').split(':')
        if len(pieces) != 2:
            raise ValueError('Ölçekleri 1:1;1:2;1:2,5 biçiminde girin.')
        numerator, denominator = map(float, pieces)
        if denominator <= 0 or numerator <= 0:
            raise ValueError('Ölçek payı ve paydası pozitif olmalı.')
        result.append(numerator/denominator)
    return tuple(result)


class ConfigurationDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        return super().createEditor(parent, option, index) if index.column() == 1 else None


class AutoDrawingPage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'Otomatik Teknik Resim',
                         'SolidWorks parça ve montajlarından modele bağlı, düzenlenebilir teknik resimler oluşturun.')
        self.results = []
        self.batch_notice = ''
        self.source_items = {}
        self.saved = self.settings.get('automatic_drawing', {})
        if not isinstance(self.saved, dict):
            self.saved = {}
        self.analyze_button = self.action('Analiz et', self.analyze)
        self.start_button = self.action('Resimleri oluştur', self.start, primary=True)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        self.report_button = self.action('Rapor kaydet', self.save_report)
        self.controls.remove(self.report_button)
        self.report_button.setEnabled(False)

        left = QWidget(); left.setMinimumWidth(0)
        ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 4, 0)
        ll.addWidget(label('Dosya ve montaj ağacı', 'section'))
        self.add_file_button = button('Dosya ekle…', self.choose_files)
        self.add_folder_button = button('Klasör ekle…', self.choose_folder)
        self.active_button = button('Aktif dosyayı al', self.use_active)
        self.remove_button = button('Seçilileri kaldır', self.remove_sources)
        ll.addWidget(AdaptiveRow(self.add_file_button, self.add_folder_button))
        ll.addWidget(AdaptiveRow(self.active_button, self.remove_button))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Dosya / bileşen', 'Konfigürasyon', 'Durum'])
        self.tree.setAccessibleName('Teknik resim kaynakları ve montaj hiyerarşisi')
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setItemDelegate(ConfigurationDelegate(self.tree))
        self.tree.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.tree.setMinimumWidth(0)
        fit_columns(self.tree, elastic=0, minimum=120, autofit=(1, 2),
                    settings=self.settings, key='automatic_drawing_sources')
        self.tree.itemSelectionChanged.connect(self.show_analysis)
        ll.addWidget(self.tree, 1)
        ll.addWidget(label('Kutuları işaretleyin. Konfigürasyonu değiştirmek için hücreye çift tıklayın.',
                           'muted'))
        self.controls += [self.add_file_button, self.add_folder_button, self.active_button,
                          self.remove_button, self.tree]

        self.tabs = QTabWidget(); self.tabs.setMinimumWidth(0)
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget); settings_layout.setContentsMargins(8, 8, 8, 8)
        self.fields = {}
        self._build_options(settings_layout)
        settings_layout.addStretch()
        settings_scroll = scroll(settings_widget)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tabs.addTab(settings_scroll, 'Ayarlar')

        # This is the PDF exported by SolidWorks from the actual native drawing.
        preview = QWidget(); pv = QVBoxLayout(preview); pv.setContentsMargins(8, 8, 8, 8)
        self.preview_caption = label('Oluşturulan gerçek PDF burada gösterilecek.', 'muted')
        pv.addWidget(self.preview_caption)
        from PySide6.QtPdf import QPdfDocument
        from PySide6.QtPdfWidgets import QPdfView
        self.pdf_document = QPdfDocument(self)
        self.pdf_view = QPdfView()
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        pv.addWidget(self.pdf_view, 1)
        self.tabs.addTab(preview, 'Önizleme')
        self.analysis_text = QPlainTextEdit(); self.analysis_text.setReadOnly(True)
        self.analysis_text.setPlainText('Bir kaynak seçip “Analiz et” komutunu kullanın.')
        self.tabs.addTab(self.analysis_text, 'Analiz')
        self.result_table = QTableWidget(0, 5)
        self.result_table.setHorizontalHeaderLabels(['Dosya', 'Konfigürasyon', 'Durum', 'Pafta', 'Açıklama'])
        configure_view(self.result_table)
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.itemSelectionChanged.connect(self.select_result)
        fit_columns(self.result_table, elastic=4, minimum=160, autofit=(0, 1, 2, 3),
                    settings=self.settings, key='automatic_drawing_results')
        self.tabs.addTab(self.result_table, 'Sonuçlar')

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(left); self.splitter.addWidget(self.tabs)
        self.splitter.setStretchFactor(0, 1); self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([290, 800])
        self.layout.addWidget(self.splitter, 1)
        self.progress_label = label('SolidWorks bağlantısı analiz / oluşturma sırasında kontrol edilir.', 'muted')
        self.layout.addWidget(self.progress_label)
        self.stage_progress = QProgressBar()
        self.stage_progress.setRange(0, len(STAGES)); self.stage_progress.setValue(0)
        self.stage_progress.setTextVisible(False)
        self.layout.addWidget(self.stage_progress)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(2000)
        self.log.setMaximumHeight(100)
        self.layout.addWidget(Disclosure('İşlem günlüğü', self.log))
        self.finish_layout()

    def _saved(self, key, default):
        value = self.saved.get(key, default)
        if isinstance(default, bool):
            return value if isinstance(value, bool) else default
        return value if isinstance(value, type(default)) and not isinstance(value, bool) else default

    def _line(self, form, key, title, default=''):
        widget = QLineEdit(self._saved(key, default)); widget.setClearButtonEnabled(True)
        widget.setMinimumWidth(0); widget.setAccessibleName(title)
        form.addRow(title, widget); self.fields[key] = widget; self.controls.append(widget)
        return widget

    def _combo(self, form, key, title, items, default):
        widget = QComboBox(); widget.setMinimumContentsLength(4)
        widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        for text, value in items: widget.addItem(text, value)
        index = widget.findData(self._saved(key, default)); widget.setCurrentIndex(max(0, index))
        form.addRow(title, widget); self.fields[key] = widget; self.controls.append(widget)
        return widget

    def _check(self, form, key, title, default):
        widget = QCheckBox(title); widget.setChecked(self._saved(key, default))
        form.addRow(widget); self.fields[key] = widget; self.controls.append(widget)
        return widget

    def _path(self, form, key, title, file_filter=None):
        widget = QLineEdit(self._saved(key, '')); widget.setClearButtonEnabled(True)
        widget.setMinimumWidth(0); widget.setAccessibleName(title)
        self.fields[key] = widget; self.controls.append(widget)
        browse = button('Seç…', lambda: self.choose_path(widget, title, file_filter))
        row = QWidget(); layout = QHBoxLayout(row); layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget, 1); layout.addWidget(browse)
        form.addRow(title, row); self.controls.append(browse)

    def _form(self, layout, title):
        section, body = pane(title)
        form = QFormLayout(); form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        body.addLayout(form); layout.addWidget(section)
        return form

    def _build_options(self, layout):
        general = self._form(layout, 'Pafta ve şablon')
        self._path(general, 'template', 'Drawing şablonu · DRWDOT', 'SolidWorks Drawing şablonu (*.drwdot *.DRWDOT)')
        self._path(general, 'sheet_format', 'Firma anteti · SLDDRT (isteğe bağlı)',
                   'SolidWorks sayfa biçimi (*.slddrt *.SLDDRT)')
        self._combo(general, 'paper', 'Pafta boyutu', [('A3 yatay', 'A3'), ('Otomatik', 'auto'),
                    *[(p+' yatay', p) for p in PAPERS if p != 'A3'], ('Özel', 'custom')], 'A3')
        for key, title, default in (('custom_width_mm', 'Özel en · mm', 420.),
                                    ('custom_height_mm', 'Özel boy · mm', 297.)):
            spin = NumberSpinBox(2); spin.setRange(100, 5000)
            value = self.saved.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 100 <= value <= 5000:
                value = default
            spin.setValue(value); general.addRow(title, spin); self.fields[key] = spin; self.controls.append(spin)
        def custom_paper():
            custom = self.fields['paper'].currentData() == 'custom'
            for key in ('custom_width_mm', 'custom_height_mm'):
                general.setRowVisible(self.fields[key], custom)
        self.fields['paper'].currentIndexChanged.connect(custom_paper)
        custom_paper()
        self._combo(general, 'projection', 'İzdüşüm', [('ISO · birinci açı', 'first'),
                                                     ('Üçüncü açı', 'third')], 'first')
        self._line(general, 'scales_text', 'Tercih edilen ölçekler',
                   '5:1;2:1;1:1;1:2;1:2,5;1:5;1:10;1:20;1:50;1:100')
        self._line(general, 'manual_scale_text', 'Manuel ölçek · boşsa otomatik')
        views = self._form(layout, 'Görünüş ve ölçüler')
        self._combo(views, 'main_view', 'Ana görünüş', [('Akıllı seçim', 'auto'), ('Ön', 'front'),
                    ('Arka', 'back'), ('Üst', 'top'), ('Alt', 'bottom'), ('Sağ', 'right'), ('Sol', 'left')], 'auto')
        self._combo(views, 'classification', 'Parça sınıfı', [('Otomatik', 'auto')]+[
            (title, key) for key, title in CLASS_TITLES.items() if key != 'assembly'], 'auto')
        for key, title, default in (
            ('top', 'Üst izdüşüm', True), ('side', 'Yan izdüşüm', True),
            ('isometric', 'İzometrik görünüş', True),
            ('model_dimensions', 'Resme işaretli model ölçüleri', True),
            ('include_unmarked', 'İşaretsiz ölçüleri de aktar', False),
            ('geometry_dimensions', 'Geometriden referans ölçüleri', False),
            ('arrange_dimensions', 'Ölçüleri düzenle ve denetle', True),
            ('center_marks', 'Delik merkez işaretleri', True),
            ('flat_pattern', 'Mevcut sac açınımını ekle', True),
            ('bend_lines', 'Açınım büküm çizgileri', True)):
            self._check(views, key, title, default)
        views.addRow(label('Kesit / detay gereksinimleri analiz raporunda önerilir; bu sürümde otomatik oluşturulmaz.',
                           'muted'))
        assembly = self._form(layout, 'Montaj')
        self._combo(assembly, 'assembly_scope', 'Oluşturulacak resimler',
                    [('Yalnız seçili dosyalar / montaj', 'assembly'),
                     ('Montaj ve benzersiz parçalar', 'parts'),
                     ('Montaj, alt montajlar ve benzersiz parçalar', 'all')], 'assembly')
        self._check(assembly, 'bom', 'Native SolidWorks BOM tablosu', True)
        self._combo(assembly, 'bom_type', 'BOM kapsamı', [('Yalnız parçalar', 'parts'),
                    ('Üst seviye', 'top'), ('Girintili', 'indented')], 'parts')
        self._path(assembly, 'bom_template', 'BOM şablonu (isteğe bağlı)',
                   'SolidWorks BOM şablonu (*.sldbomtbt *.SLDBOMTBT)')
        self._check(assembly, 'balloons', 'BOM’a bağlı otomatik balonlar', False)
        output = self._form(layout, 'Çıktı')
        self._path(output, 'output_dir', 'Çıktı klasörü · boşsa kaynak klasör')
        self._line(output, 'naming', 'Dosya adı şablonu', '{name}-{configuration}')
        self._combo(output, 'existing', 'Mevcut dosya', [('Yeni ad üret', 'unique'), ('Atla', 'skip')], 'unique')
        output.addRow(label('Düzenlenebilir SLDDRW her zaman üretilir.', 'muted'))
        self._check(output, 'pdf', 'Tüm paftalar PDF / önizleme', True)
        self._check(output, 'dxf', 'Tek pafta için DXF', False)
        mapping = self._form(layout, 'Antet · model özelliği → resim özelliği')
        raw_map = self.saved.get('property_map')
        saved_map = raw_map if isinstance(raw_map, list) and 0 < len(raw_map) <= 50 and all(
            isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(s, str) for s in p)
            for p in raw_map) else Options().property_map
        self.mapping_fields = []
        for index, (source, target) in enumerate(saved_map):
            left, right = QLineEdit(source), QLineEdit(target)
            left.setPlaceholderText('Model özelliği'); right.setPlaceholderText('Resim özelliği')
            left.setAccessibleName(f'Antet {index+1} kaynak model özelliği')
            right.setAccessibleName(f'Antet {index+1} hedef resim özelliği')
            row = QWidget(); fields = QHBoxLayout(row); fields.setContentsMargins(0, 0, 0, 0)
            fields.addWidget(left, 1); fields.addWidget(label('→', wrap=False)); fields.addWidget(right, 1)
            mapping.addRow(row); self.mapping_fields.append((left, right)); self.controls += [left, right]

    def choose_path(self, field, title, file_filter):
        if file_filter:
            path, _ = QFileDialog.getOpenFileName(self, title, field.text(), file_filter)
        else:
            path = QFileDialog.getExistingDirectory(self, title, field.text())
        if path: field.setText(path)

    def options(self):
        data, saved = {}, {}
        for key, field in self.fields.items():
            value = (field.isChecked() if isinstance(field, QCheckBox) else field.currentData()
                     if isinstance(field, QComboBox) else field.value()
                     if isinstance(field, NumberSpinBox) else field.text().strip())
            saved[key] = value
            if not key.endswith('_text'):
                data[key] = value
        data['scales'] = parse_scales(saved['scales_text'])
        text = saved['manual_scale_text']
        data['manual_scale'] = parse_scales(text)[0] if text else None
        if text and len(parse_scales(text)) != 1:
            raise ValueError('Manuel ölçek için yalnız bir oran girin.')
        data['property_map'] = tuple((left.text().strip(), right.text().strip()) for left, right in self.mapping_fields)
        saved['property_map'] = list(data['property_map'])
        options = Options(**data).validate()
        self.settings.set('automatic_drawing', saved)
        return options

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'SolidWorks kaynakları', '',
            'SolidWorks (*.sldprt *.SLDPRT *.sldasm *.SLDASM)')
        self.add_sources(Source(str(Path(path).resolve())) for path in paths)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Kaynak klasör')
        if path and self.can_start():
            self.jobs.start(self, worker('folder', folder=path))

    def use_active(self):
        if self.can_start():
            self.jobs.start(self, worker('analyze'))

    def add_sources(self, sources):
        if self.busy: return
        for source in sources:
            if source.key in self.source_items:
                continue
            item = QTreeWidgetItem([Path(source.path).name, source.configuration, 'Bekliyor'])
            item.setData(0, Qt.UserRole, source); item.setToolTip(0, source.path)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
            item.setCheckState(0, Qt.Checked)
            self.tree.addTopLevelItem(item); self.source_items[source.key] = item

    def selected_sources(self):
        sources = {}
        pending = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while pending:
            item = pending.pop(0)
            pending.extend(item.child(i) for i in range(item.childCount()))
            original = item.data(0, Qt.UserRole)
            if item.checkState(0) == Qt.Checked and isinstance(original, Source) and original.path:
                source = Source(original.path, item.text(1).strip())
                sources.setdefault(source.key, source)
        return tuple(sources.values())

    def remove_sources(self):
        if self.busy: return
        for item in self.tree.selectedItems():
            if item.parent() is not None:
                item.setCheckState(0, Qt.Unchecked)
                continue
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        self.source_items = {key: item for key, item in self.source_items.items()
                             if item.treeWidget() is self.tree}

    def analyze(self):
        if not self.can_start(): return
        sources = self.selected_sources()
        if not sources:
            self.set_status('Analiz edilecek dosyaları işaretleyin veya aktif dosyayı alın.', True)
            return
        self.jobs.start(self, worker('analyze', sources))

    def start(self):
        if not self.can_start(): return
        try:
            sources, options = self.selected_sources(), self.options()
            if not sources:
                raise ValueError('Teknik resmi oluşturulacak dosyaları işaretleyin.')
            self.pdf_document.close()
            self.results.clear(); self.result_table.setRowCount(0)
            self.report_button.setEnabled(False)
            self.stage_progress.setValue(0); self.log.clear()
            self.batch_notice = ''
            self.jobs.start(self, worker('generate', sources, options))
        except (ValueError, OSError, TypeError) as error:
            self.set_status(str(error), True)

    def _analysis_item(self, info):
        item = self.source_items.get(info.source.key) or self.source_items.pop((info.source.key[0], ''), None)
        if item is None:
            item = next((candidate for candidate in self.source_items.values()
                         if candidate.data(0, Qt.UserRole).key[0] == info.source.key[0] and
                         candidate.text(1) == info.source.configuration), None)
        if item is not None:
            self.source_items = {key: value for key, value in self.source_items.items() if value is not item}
        if item is None:
            item = QTreeWidgetItem()
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
            item.setCheckState(0, Qt.Checked); self.tree.addTopLevelItem(item)
        self.source_items[info.source.key] = item
        item.setText(0, Path(info.source.path).name); item.setText(1, info.source.configuration)
        item.setText(2, 'Analiz edildi'); item.setToolTip(0, info.source.path)
        item.setData(0, Qt.UserRole, info.source); item.setData(0, Qt.UserRole+1, info)
        item.takeChildren()
        pending = [(item, info.tree.children if info.tree else ())]
        while pending:
            parent, children = pending.pop()
            for node in children:
                child = QTreeWidgetItem([node.name, node.source.configuration,
                                        {'ready': 'Hazır', 'suppressed': 'Bastırılmış'}.get(node.state, node.state)])
                child.setData(0, Qt.UserRole, node.source); child.setToolTip(0, node.source.path+'\n'+node.detail)
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
                if node.state not in ('ready', 'hidden'):
                    child.setFlags(child.flags() & ~Qt.ItemIsEnabled)
                parent.addChild(child); pending.append((child, node.children))
        item.setExpanded(True)
        self.tree.setCurrentItem(item)
        self.show_analysis()

    def show_analysis(self):
        item = self.tree.currentItem()
        if item is None: return
        info = item.data(0, Qt.UserRole+1)
        if info is None: return
        lines = [info.title, info.source.path, 'Konfigürasyon: '+info.source.configuration,
                 'SolidWorks API: '+info.revision, 'Sınıf: '+CLASS_TITLES.get(info.classification, info.classification),
                 info.classification_reason, 'Dış ölçüler · mm: '+' × '.join(f'{v:g}' for v in info.size_mm),
                 f'Katı gövde: {info.body_count} · Sac gövde: {info.sheet_body_count}',
                 'Kaynak birim: '+info.source_unit, '', 'Model özellikleri:']
        lines += [f'{key}: {value}' for key, value in info.properties.items()]
        lines += ['', 'Unsur türleri:']+[f'{key}: {value}' for key, value in info.feature_types.items()]
        lines += ['', *info.warnings]
        self.analysis_text.setPlainText('\n'.join(lines))

    def show_result(self, result):
        self.results = [r for r in self.results if r.source.key != result.source.key]+[result]
        self.result_table.setRowCount(len(self.results))
        for row, value in enumerate(self.results):
            detail = '\n'.join(f.text for f in value.findings) or 'Temel yapısal doğrulamalar geçti.'
            for col, text in enumerate((Path(value.source.path).name, value.source.configuration,
                                        value.status, str(len(value.sheets)), detail)):
                cell = QTableWidgetItem(text); cell.setToolTip(text)
                self.result_table.setItem(row, col, cell)
        if result.analysis:
            self._analysis_item(result.analysis)
        self.log.appendPlainText(f'{result.status} · {result.source.path} · {result.stage}')
        for finding in result.findings: self.log.appendPlainText(f'{finding.severity}: {finding.text}')

    def select_result(self):
        row = self.result_table.currentRow()
        if not 0 <= row < len(self.results): return
        result = self.results[row]
        self.pdf_document.close()
        path = result.outputs.get('pdf')
        if path and Path(path).is_file():
            self.pdf_document.load(path)
            self.preview_caption.setText(Path(path).name+' · SolidWorks’ten alınan PDF')
        else:
            self.preview_caption.setText('Bu sonuç için PDF oluşturulmadı. SLDDRW / rapor ayrıntılarını kontrol edin.')

    def save_report(self):
        if not self.results: return
        path, _ = QFileDialog.getSaveFileName(self, 'Teknik resim işlem raporu', 'GOKWORKS-teknik-resim.json',
                                             'JSON (*.json)')
        if path:
            try:
                write_batch_report(path, self.results); self.set_status('İşlem raporu kaydedildi.')
            except (OSError, ValueError) as error:
                self.set_status(str(error), True)

    def handle_events(self, events):
        super().handle_events(events)
        for kind, value in events:
            if kind == 'drawing_sources':
                # The worker is still finishing; this is an inventory update, not user input.
                busy, self.busy = self.busy, False
                try: self.add_sources(value)
                finally: self.busy = busy
            elif kind == 'drawing_analysis':
                self._analysis_item(value); self.tabs.setCurrentIndex(2)
                self.set_status('Model analizi tamamlandı.')
            elif kind == 'drawing_analysis_error':
                self.set_status(value['error'], True); self.log.appendPlainText(value['error'])
            elif kind == 'drawing_progress':
                self.stage_progress.setValue(value['completed'])
                self.progress_label.setText(f"{value['completed']} / {value['total']} aşama · "+
                                            Path(value['source'].path).name+' · '+value['stage'])
                self.progressChanged.emit(value['completed'], value['total'])
            elif kind == 'drawing_result':
                self.show_result(value)
            elif kind == 'drawing_notice':
                self.batch_notice = value
                self.log.appendPlainText(value); self.set_status(value, True)
            elif kind == 'drawing_done':
                self.report_button.setEnabled(bool(self.results))
                counts = {status: sum(r.status == status for r in value)
                          for status in ('PASS', 'WARNING', 'FAIL', 'CANCELLED', 'SKIPPED')}
                summary = ' · '.join(f'{count} {name}' for name, count in counts.items())
                self.set_status(summary+('\n'+self.batch_notice if self.batch_notice else ''),
                                error=bool(counts['FAIL'] or self.batch_notice))
                self.tabs.setCurrentIndex(3)

    def job_finished(self):
        self.report_button.setEnabled(bool(self.results))
