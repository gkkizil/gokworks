"""Folder-first Pack and Go workflow with a hierarchical, collision-aware preview."""

from pathlib import Path, PureWindowsPath
from collections import Counter
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QHBoxLayout, QComboBox, QTreeView, QInputDialog,
                              QVBoxLayout, QWidget, QToolButton, QMenu, QHeaderView)

from naming import exporter as engine
from naming.hierarchy import document_rows
from .. import services
from ..models import TreeModel, FilterProxy, Column
from ..components import (BasePage, ValueForm, Disclosure, card, label, button,
                           configure_view, open_folder, TransferWorkspace)


class NamingPage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'İsimlendirme aracı', 'Montaj ve teknik resim bağlantılarını koruyarak yeni bir paket oluşturun.')
        self.snapshot = None
        self.entries = ()
        self.overrides = {}
        self.use_active = False
        self.valid_plan = False
        self.last_report = None
        self.preview_pending = False
        self.plan_signature = None
        self.scan_button = self.action('Dosyaları oku', self.scan, primary=True)
        self.save_button = self.action('Paketi oluştur', self.save)
        self.save_button.setEnabled(False)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        self.stop_button.setEnabled(False)
        panel, body = card('Kaynak ve yeni paket')
        self.form = ValueForm(self.settings, 'naming_')
        self.source_folder = self.form.path('source_folder', 'Montaj klasörü')
        destination = self.settings.get('naming_destination')
        if destination is None:
            parent = self.settings.get('naming_parent', '')
            destination = str(Path(parent) / str(self.settings.get('naming_package', 'Yeni-paket'))) if isinstance(parent, str) and parent else ''
        self.destination = self.form.path('destination', 'Yeni paket klasörü', destination)
        self.form.stack_fields()
        body.addWidget(self.form)

        self.source_options_form = ValueForm(self.settings, 'naming_')
        self.source_file = self.source_options_form.path('source_file','Kaynak dosya',folder=False)
        self.source_options_form.stack_fields()
        self.discover_button = button('Montajları bul', self.discover)
        self.active_button = button('Aktif montajı kullan', self.read_active)
        self.source_options_form.form.addRow(self.active_button)
        self.assemblies = QComboBox()
        self.assemblies.setMinimumWidth(0)
        self.assemblies.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.assemblies.setPlaceholderText('Montaj seçin…')
        self.assemblies.setAccessibleName('Klasörde bulunan montajlar')
        self.assemblies.activated.connect(self.choose_assembly)
        choices=QVBoxLayout();choices.addWidget(self.assemblies);choices.addWidget(self.discover_button)
        self.form.form.addRow(label('Kaynak montaj'),choices)
        self.source_folder.choose.clicked.connect(lambda:self.discover() if self.source_folder.text() else None)
        self.source_options = Disclosure('Dosya / aktif montaj', self.source_options_form)
        self.source_options.toggle.setToolTip('Dosyadan seç veya SolidWorks’teki aktif montajı kullan')
        body.addWidget(self.source_options)

        rules = QWidget()
        rules_layout = QVBoxLayout(rules)
        rules_layout.setContentsMargins(0, 0, 0, 0)
        rules_layout.setSpacing(8)
        self.rules_form = ValueForm(self.settings, 'naming_')
        self.rules_form.combo('mode', 'Yöntem', ('Ön / son ek', 'Numaralı'), 'Ön / son ek')
        self.rules_form.stack_fields()
        rules_layout.addWidget(self.rules_form)
        paired = QVBoxLayout(); paired.setSpacing(8)
        self.name_left = ValueForm(self.settings, 'naming_')
        self.name_left.text('prefix', 'Ön ek')
        self.name_left.text('start', 'Başlangıç', '1').setToolTip('Başlangıç numarası')
        self.name_right = ValueForm(self.settings, 'naming_')
        self.name_right.text('suffix', 'Son ek')
        self.name_right.text('digits', 'Basamak', '3').setToolTip('Numara basamak sayısı')
        self.name_left.stack_fields(); self.name_right.stack_fields()
        paired.addWidget(self.name_left)
        paired.addWidget(self.name_right)
        rules_layout.addLayout(paired)
        self.replacement_form=ValueForm(self.settings,'naming_')
        self.replacement_form.text('find','Bul'); self.replacement_form.text('replacement','Yerine yaz')
        self.replacement_form.stack_fields(); rules_layout.addWidget(self.replacement_form)
        for subform in (self.source_options_form, self.rules_form, self.name_left, self.name_right,self.replacement_form):
            self.form.fields.update(subform.fields)
            subform.changed.connect(self.form.changed)
        self.rules_options = Disclosure('İsimlendirme kuralları', rules, expanded=True)
        body.addWidget(self.rules_options)
        self.safety_note = label('Hedef klasör yeni veya boş olmalı. Teknik resimler, bastırılmış parçalar ve Toolbox bileşenleri dahil edilir.', 'muted')
        body.addWidget(self.safety_note)
        preview, layout = card('İsimlendirme önizlemesi')
        toolbar = QHBoxLayout()
        self.edit_button = button('Adı düzenle', self.edit_selected)
        self.edit_button.setToolTip('Seçili dosyanın yeni adını düzenle')
        toolbar.addWidget(self.edit_button)
        toolbar.addStretch()
        self.more_button = QToolButton()
        self.more_button.setText('Diğer')
        self.more_button.setAccessibleName('İsimlendirme önizleme işlemleri')
        self.more_button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.more_button)
        self.reset_action = menu.addAction('Elle girilenleri sıfırla', self.reset_overrides)
        menu.addAction('Hedef klasörünü aç', lambda: open_folder(self.destination.text()) if self.destination.text() else None)
        self.source_column_action=menu.addAction('Kaynak dosya sütununu göster');self.source_column_action.setCheckable(True)
        self.source_column_action.toggled.connect(lambda visible:self.tree.setColumnHidden(3,not visible))
        self.more_button.setMenu(menu)
        toolbar.addWidget(self.more_button)
        layout.addLayout(toolbar)
        self.tree = configure_view(QTreeView())
        self.model = TreeModel((Column('Montaj / mevcut dosya adı', 'name'), Column('Yeni dosya adı', 'new_name'),
                                Column('Tür', 'kind'), Column('Kaynak dosya', 'source')))
        self.proxy = FilterProxy(self, tree=True)
        self.proxy.setSourceModel(self.model)
        self.tree.setModel(self.proxy)
        self.tree.setColumnWidth(0, 240)
        self.tree.setColumnWidth(1, 230)
        self.tree.setColumnWidth(2, 100)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0,QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1,QHeaderView.Stretch)
        self.tree.setColumnHidden(3,True)
        self.tree.doubleClicked.connect(self.edit_selected)
        layout.addWidget(self.tree, 1)
        self.plan_message = label('Kaynak montajı seçip Dosyaları oku düğmesine basın.', 'muted')
        layout.addWidget(self.plan_message)
        self.preview_panel=preview
        self.splitter=TransferWorkspace(self,panel,preview)
        self.source_scroll=self.splitter.source_scroll
        self.layout.addWidget(self.splitter, 1)
        self.controls.extend((self.form, self.source_options_form, rules,
                              self.discover_button, self.active_button, self.edit_button))
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(150)
        self.preview_timer.timeout.connect(self.update_preview)
        self.form.changed.connect(self.form_changed)
        self.rules_form.changed.connect(lambda key: self.update_rule_fields() if key == 'mode' else None)
        self.update_rule_fields()
        self.last_error = ''
        self.finish_layout()
        self.jobs.finished.connect(self.schedule_preview)

    def set_busy(self, busy):
        super().set_busy(busy)
        self.save_button.setEnabled(not busy and self.valid_plan)
        self.reset_action.setEnabled(not busy)

    def update_rule_fields(self):
        numbered = self.form.value('mode') == 'Numaralı'
        self.name_left.show_field('start', numbered)
        self.name_right.show_field('digits', numbered)
        self.rules_options.toggle.setText('Kurallar · ' + self.form.value('mode'))

    def form_changed(self, key):
        if key=='source_folder':
            self.source_file.setText('');self.assemblies.clear()
        if key.startswith('source_'):
            self.snapshot = None
            self.entries = ()
            self.overrides.clear()
            self.use_active = False
            self.model.replace([])
            self.valid_plan = False
            self.save_button.setEnabled(False)
            self.plan_message.setText('Kaynak değişti. Dosyaları yeniden okuyun.')
        else:
            self.valid_plan = False
            self.save_button.setEnabled(False)
            self.preview_timer.start()

    def discover(self):
        if not self.can_start():
            return
        source = self.source_folder.text()
        if not source:
            return self.set_status('Montajın bulunduğu kaynak klasörü seçin.', True)
        self.jobs.start(self, lambda sink, stop: services.discover_assemblies(source, sink, stop))
        self.set_status('Klasördeki montaj dosyaları aranıyor…')

    def choose_assembly(self, index):
        path = self.assemblies.itemData(index)
        if path:
            self.source_file.setText(path)

    def read_active(self):
        self.use_active = True
        self.scan()

    def scan(self):
        if not self.can_start():
            return
        source = None if self.use_active else self.source_file.text()
        if not self.use_active and not source:
            if self.assemblies.count()>1:
                self.assemblies.setFocus()
                return self.set_status('Kaynak montaj listesinden işlenecek montajı seçin.',True)
            return self.discover()
        if source and PureWindowsPath(source).suffix.lower() not in engine.CAD_TYPES:
            return self.set_status('Geçerli bir SolidWorks montaj, parça veya teknik resim dosyası seçin.', True)
        active = self.use_active
        self.jobs.start(self, lambda sink, stop: engine.worker(sink, stop, operation='scan',
                        source_path=source, require_assembly=active))
        self.set_status('Montaj dosyaları ve teknik resim referansları okunuyor…')

    def load_snapshot(self, snapshot):
        self.snapshot = snapshot
        self.overrides.clear()
        self.update_preview()

    def update_preview(self):
        self.valid_plan = False
        if self.snapshot is None:
            self.save_button.setEnabled(False)
            return
        if self.jobs.busy:
            self.preview_pending = True
            return
        self.preview_pending = False
        values = self.form.values()
        snapshot, overrides = self.snapshot, dict(self.overrides)
        signature = (id(snapshot), dict(values), dict(overrides))
        self.jobs.start(self, lambda sink, stop: self.prepare_plan(snapshot, values, overrides, signature, sink, stop))

    @staticmethod
    def prepare_plan(snapshot, values, overrides, signature, sink, stop):
        """Filesystem validation and potentially large plans never run on GUI thread."""
        try:
            destination = engine.validate_destination(values['destination'], snapshot)
            rules = engine.Rules(prefix=values['prefix'], suffix=values['suffix'], find=values['find'],
                replacement=values['replacement'], numbered=values['mode'] == 'Numaralı',
                start=int(values['start']), digits=int(values['digits']))
            entries = engine.plan_names(snapshot, destination, rules, overrides, allow_collisions=True)
            targets = [engine.path_key(item.destination) for item in entries]
            duplicates = {key for key, count in Counter(targets).items() if count > 1}
            rows = []
            for row in document_rows(snapshot):
                if stop.is_set():
                    return
                doc = snapshot.documents[row.index]
                entry = entries[row.index]
                rows.append(dict(id=row.iid, parent=row.parent, source=doc.path, index=row.index,
                    name=PureWindowsPath(doc.path).name + (' · ortak parça' if row.shared else ''),
                    new_name=PureWindowsPath(entry.destination).name, kind=doc.kind,
                    status='error' if engine.path_key(entry.destination) in duplicates else 'pending'))
            if duplicates:
                sink.put(('naming_plan', dict(rows=rows,entries=entries,signature=signature,
                    error='Yeni dosya adları çakışıyor. Seçili adları düzenleyin veya numaralı isimlendirme kullanın.')))
                return
            # Full validation also protects the reserved report filename.
            engine.plan_names(snapshot, destination, rules, overrides)
            if not stop.is_set():
                sink.put(('naming_plan', dict(rows=rows,entries=entries,signature=signature,destination=str(destination))))
        except (ValueError, OSError) as error:
            sink.put(('naming_plan', dict(error=str(error),signature=signature)))

    def schedule_preview(self):
        if self.preview_pending and not self.context.closing:
            self.preview_timer.start()

    def edit_selected(self, *args):
        if self.busy or self.snapshot is None:
            return
        index = self.tree.currentIndex()
        if not index.isValid():
            return self.set_status('Önizlemeden bir dosya seçin.')
        row = index.data(Qt.UserRole)
        stem = PureWindowsPath(row['new_name']).stem
        value, ok = QInputDialog.getText(self, 'Yeni dosya adı', 'Yeni ad (uzantısız):', text=stem)
        if ok:
            try:
                value = engine.valid_stem(value)
            except ValueError as error:
                return self.set_status(error, True)
            self.overrides[engine.path_key(row['source'])] = value
            self.update_preview()

    def reset_overrides(self):
        if not self.busy:
            self.overrides.clear()
            self.update_preview()

    def save(self):
        if not self.can_start():
            return
        if self.plan_signature != (id(self.snapshot), self.form.values(), self.overrides):
            self.update_preview()
            return self.set_status('Önizleme güncelleniyor. Tamamlandığında Paketi oluştur düğmesini kullanın.')
        if not self.valid_plan:
            return self.set_status(self.last_error or 'Önce geçerli bir isimlendirme planı oluşturun.', True)
        snapshot, entries, destination = self.snapshot, self.entries, self.destination.text()
        self.jobs.start(self, lambda sink, stop: engine.worker(sink, stop, operation='save',
                        snapshot=snapshot, entries=entries, destination=destination))
        self.set_status('Yeni montaj paketi oluşturuluyor…')

    def handle_events(self, events):
        for kind, value in events:
            if kind == 'naming_plan':
                self.plan_signature = value['signature']
                if value['signature'] != (id(self.snapshot), self.form.values(), self.overrides):
                    self.preview_pending = True
                    continue
                self.entries = value.get('entries', ())
                self.last_error = value.get('error', '')
                self.valid_plan = not self.last_error
                if 'rows' in value:
                    self.model.replace(value['rows'])
                    self.tree.expandToDepth(1)
                self.plan_message.setText(self.last_error or f"{len(self.entries)} dosya · Hedef: {value['destination']}")
            elif kind == 'assemblies':
                self.assemblies.clear()
                for path in value:
                    self.assemblies.addItem(PureWindowsPath(path).name, path)
                if len(value) == 1:
                    self.assemblies.setCurrentIndex(0)
                    self.source_file.setText(str(value[0]))
                elif value:
                    self.source_file.setText('')
                    self.assemblies.setCurrentIndex(-1)
                self.set_status(f'{len(value)} montaj bulundu. Montajı seçip Dosyaları oku düğmesine basın.')
            elif kind == 'naming_phase':
                self.set_status(value)
            elif kind == 'naming_done':
                if value['state'] == 'scanned':
                    self.load_snapshot(value['snapshot'])
                    self.set_status('Dosyalar okundu; yeni adları kontrol edin.')
                elif value['state'] == 'saved':
                    self.valid_plan = False
                    self.last_report = value.get('report')
                    self.set_status('Paket oluşturuldu; yeni dosyaların referansları doğrulandı. Rapor: ' + str(self.last_report or self.destination.text()))
                elif value['state'] == 'cancelled':
                    self.set_status('İşlem durduruldu.')
                else:
                    self.last_error = value.get('error', 'İsimlendirme tamamlanamadı.')
                    self.set_status(self.last_error, True)
            elif kind == 'job_error':
                self.set_status(value['error'], True)
