"""Folder-first Pack and Go workflow with a hierarchical, collision-aware preview."""

from pathlib import Path, PureWindowsPath
from collections import Counter
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QHBoxLayout, QComboBox, QTreeView, QInputDialog,
                              QSplitter, QVBoxLayout, QApplication)

from naming import exporter as engine
from naming.hierarchy import document_rows
from .. import services
from ..models import TreeModel, FilterProxy, Column
from ..components import BasePage, ValueForm, card, scroll, label, button, configure_view, show_details


class NamingPage(BasePage):
    def __init__(self, context):
        super().__init__(context, 'İsimlendirme aracı', 'Montaj ve teknik resim bağlantılarını koruyarak yeni bir paket oluşturun.')
        self.snapshot = None
        self.entries = ()
        self.overrides = {}
        self.use_active = False
        self.valid_plan = False
        self.scan_button = self.action('Dosyaları oku', self.scan, primary=True)
        self.save_button = self.action('Paketi oluştur', self.save)
        self.save_button.setEnabled(False)
        self.stop_button = self.action('Durdur', self.jobs.cancel, locked=False)
        self.stop_button.setEnabled(False)
        splitter = QSplitter(Qt.Vertical)
        panel, body = card('Kaynak montaj ve hedef')
        self.form = ValueForm(self.settings, 'naming_')
        self.source_folder = self.form.path('source_folder', 'Montajın bulunduğu klasör')
        self.source_file = self.form.path('source_file', 'Kaynak montaj / dosya', folder=False)
        self.discover_button = button('Klasördeki montajları bul', self.discover)
        self.active_button = button('Aktif montajı kullan', self.read_active)
        choices = QHBoxLayout()
        choices.addWidget(self.discover_button)
        choices.addWidget(self.active_button)
        self.assemblies = QComboBox()
        self.assemblies.setPlaceholderText('Klasörden montaj seçin…')
        self.assemblies.activated.connect(self.choose_assembly)
        choices.addWidget(self.assemblies, 1)
        self.form.form.addRow(choices)
        destination = self.settings.get('naming_destination')
        if destination is None:
            parent = self.settings.get('naming_parent', '')
            destination = str(Path(parent) / self.settings.get('naming_package', 'Yeni-paket')) if parent else ''
        self.destination = self.form.path('destination', 'Yeni montajın kaydedileceği klasör', destination)
        self.form.combo('mode', 'İsimlendirme yöntemi', ('Ön / son ek', 'Numaralı'), 'Ön / son ek')
        self.form.text('prefix', 'Ön ek')
        self.form.text('suffix', 'Son ek')
        self.form.text('start', 'Başlangıç numarası', '1')
        self.form.text('digits', 'Numara basamak sayısı', '3')
        self.form.text('find', 'Bul')
        self.form.text('replacement', 'Yerine yaz')
        body.addWidget(self.form)
        body.addWidget(label('Hedef klasör yeni veya boş olmalı. Teknik resimler, bastırılmış parçalar ve Toolbox bileşenleri dahil edilir.', 'muted'))
        splitter.addWidget(scroll(panel))
        preview, layout = card('İsimlendirme önizlemesi')
        toolbar = QHBoxLayout()
        self.edit_button = button('Seçili adı düzenle', self.edit_selected)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(button('Elle girilenleri sıfırla', self.reset_overrides))
        layout.addLayout(toolbar)
        self.tree = configure_view(QTreeView())
        self.model = TreeModel((Column('Montaj / mevcut dosya adı', 'name'), Column('Yeni dosya adı', 'new_name'),
                                Column('Tür', 'kind'), Column('Kaynak dosya', 'source')))
        self.proxy = FilterProxy(self, tree=True)
        self.proxy.setSourceModel(self.model)
        self.tree.setModel(self.proxy)
        self.tree.setColumnWidth(0, 350)
        self.tree.setColumnWidth(1, 300)
        self.tree.doubleClicked.connect(self.edit_selected)
        layout.addWidget(self.tree, 1)
        self.plan_message = label('Kaynak montajı seçip Dosyaları oku düğmesine basın.', 'muted')
        layout.addWidget(self.plan_message)
        splitter.addWidget(preview)
        splitter.setSizes([300, 420])
        splitter.setStretchFactor(1, 1)
        self.layout.addWidget(splitter, 1)
        self.controls.extend((self.form, self.discover_button, self.active_button, self.edit_button))
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(150)
        self.preview_timer.timeout.connect(self.update_preview)
        self.form.changed.connect(self.form_changed)
        self.last_error = ''
        self.finish_layout()

    def set_busy(self, busy):
        super().set_busy(busy)
        self.save_button.setEnabled(not busy and self.valid_plan)

    def form_changed(self, key):
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
            self.preview_timer.start()

    def discover(self):
        if not self.can_start():
            return
        source = self.source_folder.text()
        if not source or not Path(source).is_dir():
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
            return self.discover()
        if source and (not Path(source).is_file() or PureWindowsPath(source).suffix.lower() not in engine.CAD_TYPES):
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
        values = self.form.values()
        try:
            destination = engine.validate_destination(values['destination'], self.snapshot)
            rules = engine.Rules(prefix=values['prefix'], suffix=values['suffix'], find=values['find'],
                replacement=values['replacement'], numbered=values['mode'] == 'Numaralı',
                start=int(values['start']), digits=int(values['digits']))
            self.entries = engine.plan_names(self.snapshot, destination, rules, self.overrides, allow_collisions=True)
            targets = [engine.path_key(item.destination) for item in self.entries]
            duplicates = {key for key, count in Counter(targets).items() if count > 1}
            rows = []
            for row in document_rows(self.snapshot):
                doc = self.snapshot.documents[row.index]
                entry = self.entries[row.index]
                rows.append(dict(id=row.iid, parent=row.parent, source=doc.path, index=row.index,
                    name=PureWindowsPath(doc.path).name + (' · ortak parça' if row.shared else ''),
                    new_name=PureWindowsPath(entry.destination).name, kind=doc.kind,
                    status='error' if engine.path_key(entry.destination) in duplicates else 'pending'))
            self.model.replace(rows)
            self.tree.expandToDepth(1)
            if duplicates:
                raise engine.NameCollision('Yeni dosya adları çakışıyor. Seçili adları düzenleyin veya numaralı isimlendirme kullanın.')
            # Full validation also protects the reserved report filename.
            engine.plan_names(self.snapshot, destination, rules, self.overrides)
            self.valid_plan = True
            self.plan_message.setText(f'{len(self.entries)} dosya · Hedef: {destination}')
            self.last_error = ''
        except (ValueError, OSError) as error:
            self.plan_message.setText(str(error))
            self.last_error = str(error)
        self.save_button.setEnabled(not self.busy and self.valid_plan)

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
        self.update_preview()
        if not self.valid_plan:
            return self.set_status(self.last_error or 'Önce geçerli bir isimlendirme planı oluşturun.', True)
        snapshot, entries, destination = self.snapshot, self.entries, self.destination.text()
        self.jobs.start(self, lambda sink, stop: engine.worker(sink, stop, operation='save',
                        snapshot=snapshot, entries=entries, destination=destination))
        self.set_status('Yeni montaj paketi oluşturuluyor…')

    def handle_events(self, events):
        for kind, value in events:
            if kind == 'assemblies':
                self.assemblies.clear()
                for path in value:
                    self.assemblies.addItem(PureWindowsPath(path).name, path)
                if len(value) == 1:
                    self.source_file.setText(str(value[0]))
                self.set_status(f'{len(value)} montaj bulundu. Montajı seçip Dosyaları oku düğmesine basın.')
            elif kind == 'naming_phase':
                self.set_status(value)
            elif kind == 'naming_done':
                if value['state'] == 'scanned':
                    self.load_snapshot(value['snapshot'])
                    self.set_status('Dosyalar okundu; yeni adları kontrol edin.')
                elif value['state'] == 'saved':
                    self.valid_plan = False
                    self.set_status('Paket oluşturuldu; yeni dosyaların referansları doğrulandı.')
                elif value['state'] == 'cancelled':
                    self.set_status('İşlem durduruldu.')
                else:
                    self.last_error = value.get('error', 'İsimlendirme tamamlanamadı.')
                    self.set_status(self.last_error, True)
            elif kind == 'job_error':
                self.set_status(value['error'], True)
