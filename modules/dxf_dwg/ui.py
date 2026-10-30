"""Sheet-metal exports and source-matched preview; shared export flow is intact."""

from pathlib import Path
import csv

from PySide6.QtCore import Qt, QTimer, QEvent, Slot, QFileSystemWatcher, QObject, QSignalBlocker
from PySide6.QtWidgets import QSplitter, QFileDialog, QHeaderView, QHBoxLayout, QVBoxLayout, QCheckBox, QWidget
from gui_qt.export import ExportPage
from gui_qt.components import label, button, ValueForm, Disclosure
from modules.cad_converter.models import Cancelled
from modules.cad_converter.api import RestoreError
from .preview.models import Request, MeshCache
from .preview.panel import PreviewPanel
from .preview.solidworks import capture, file_stamp
from .preview.solidworks import capture_geometry
from .preview.cancellation import cancellable_read
from .inventory import display_rows, selected_items
from .table import SheetTableModel
from gui_qt.models import LABELS


class _PageEvents(QObject):
    """Explicit GUI-affine receiver, avoiding a shadowed inherited Qt slot.

    PySide can bind an override of ExportPage's decorated slot through the
    inherited meta-method. Composition gives JobManager one unambiguous slot.
    """
    def __init__(self, page):
        super().__init__(page)
        self.page = page

    @Slot(object)
    def accept(self, events):
        self.page.process_events(events)


class DxfDwgPage(ExportPage):
    def __init__(self, context):
        super().__init__(context, 'dxf_dwg')
        self.inventory = None
        self.checked_instances = {}
        self._legacy_save_csv=self.results.save_csv
        self.results.save_csv=self.save_sheet_csv
        self.scan_origin = ('folder', '')
        self.active_scan_button = button('Aktif montajı tara', self.scan_active)
        self.file_scan_button = button('Dosya seç…', self.scan_file)
        self.file_scan_button.setToolTip('SLDPRT veya SLDASM seçerek sac gövdelerini tara')
        self.controls.extend((self.active_scan_button,self.file_scan_button))
        scan_actions = QWidget();scan_layout=QVBoxLayout(scan_actions);scan_layout.setContentsMargins(0,0,0,0)
        scan_layout.addWidget(self.active_scan_button);scan_layout.addWidget(self.file_scan_button)
        self.form.form.insertRow(1,scan_actions)
        self.start_button.setText('Seçili parçaları dışa aktar')
        self.start_button.setToolTip('İşaretli sac gövdelerini ayrı DXF/DWG dosyalarına aktarır; kaynak CAD dosyaları kaydedilmez.')
        previous_model = self.results.model
        self.results.model = SheetTableModel()
        self.results.proxy.setSourceModel(self.results.model)
        self.source_files.proxy.setSourceModel(self.results.model)
        previous_model.deleteLater()
        header = self.results.table.horizontalHeader()
        for index, width in enumerate((36,190,90,95,90,50,115,200)):
            header.setSectionResizeMode(index, QHeaderView.Interactive)
            self.results.table.setColumnWidth(index,width)
        header.setSectionResizeMode(1,QHeaderView.Stretch)
        self.results.table.setColumnHidden(7,True)  # Full detail remains in tooltip / Return / CSV.
        self.results.filter.setItemText(self.results.filter.findData('pending'),'Hazır')
        controls = QHBoxLayout()
        self.select_all_button = button('Tümünü seç', lambda:self.select_sheets(True))
        self.select_all_button.setToolTip('Tüm hazır sac parçaları seç')
        self.select_all_button.setAccessibleName('Tüm sac parçaları seç')
        self.select_none_button = button('Seçimi kaldır', lambda:self.select_sheets(False))
        self.group_instances = QCheckBox('Grupla')
        self.group_instances.setToolTip('Özdeş parçaları grupla; kapatınca montaj örneklerini ayrı göster')
        self.group_instances.setAccessibleName('Özdeş parçaları grupla / ayrı göster')
        self.group_instances.setChecked(self.settings.get('dxf_dwg_group_instances',True) is True)
        self.group_instances.toggled.connect(self.render_inventory)
        self.group_instances.toggled.connect(lambda value:self.settings.set('dxf_dwg_group_instances',value))
        for widget in (self.select_all_button,self.select_none_button,self.group_instances):
            controls.addWidget(widget);self.controls.append(widget)
        controls.addStretch()
        self.results.layout.insertLayout(1,controls)
        self.results.model.selectionEdited.connect(self.sheet_selection_changed)
        for signal in (self.results.model.modelReset,self.results.model.rowsInserted,self.results.model.rowsRemoved):
            signal.connect(self.update_source_count)
        self.results.cleared.connect(self.clear_inventory)
        self.naming_form=ValueForm(self.settings,'dxf_dwg_')
        for option, title in (('code','Parça kodunu kullan'),('body','Gövde adını ekle'),
                              ('configuration','Konfigürasyon ekle'),('material','Malzeme ekle')):
            control = self.naming_form.check('name_'+option,title,False)
            self.form.fields['name_'+option] = control
        self.naming_form.changed.connect(self.form.changed)
        self.naming_options=Disclosure('Dosya adlandırma',self.naming_form,expanded=False)
        self.options_form.form.addRow(self.naming_options)
        self.preview_before_export = self.options_form.check(
            'preview_before_export', 'Kaydetmeden önce önizle', True)
        self.preview_before_export.setToolTip(
            'Önce seçili parçanın açınımını gösterir. Listeden parçaları kontrol edin; '
            'kaydetmek için Aktarımı başlat düğmesine tekrar basın.')
        self.form.fields['preview_before_export'] = self.preview_before_export
        self.options_form.form.addRow(label('Her sac gövdesi ayrı aktarılır. Kalınlık ve adet dosya adına yazılır; gerekli gövde/konfigürasyon ayrımı otomatik eklenir.', 'muted'))
        self._events = _PageEvents(self)
        self.handle_events = self._events.accept
        self.preview = PreviewPanel()
        self.preview_cache = MeshCache()
        self.preview_generation = 0
        self.preview_request = self.preview_pending = None
        self.preview_running = False
        self._preview_cancelled = False
        self._stop_message_pending = False
        self._preview_restore_failed = False
        self._capture_geometry = None
        self.preview_force = False
        self._export_after_preview = False
        self._preview_after_scan = False
        self._awaiting_flat_review = False
        self.preview_payload = None
        self.preview_timer = QTimer(self); self.preview_timer.setSingleShot(True); self.preview_timer.setInterval(180)
        self.preview_timer.timeout.connect(self.start_preview)
        self.preview_button = self.action('Önizleme', self.show_preview, locked=False)
        self.stop_button.clicked.connect(self.cancel_pending_preview)
        self.preview.refreshRequested.connect(self.refresh_preview)
        self.preview_splitter = QSplitter(Qt.Horizontal)
        self.preview_splitter.setChildrenCollapsible(False)
        self.results.tabs.removeTab(0)
        self.preview_splitter.addWidget(self.results.table)
        self.preview_splitter.addWidget(self.preview)
        self.preview_splitter.setSizes([650, 380])
        self.results.tabs.insertTab(0, self.preview_splitter, 'Dosyalar')
        self.results.tabs.setCurrentIndex(0)
        self.results.table.show()
        self.results.installEventFilter(self)
        self.preview_compact = False
        self._moving_preview = False
        self.results.table.selectionModel().currentChanged.connect(self.selection_changed)
        self.source_files.view.selectionModel().currentChanged.connect(self.selection_changed)
        self.results.model.dataChanged.connect(self.selected_updated)
        self.results.model.modelReset.connect(self.clear_preview)
        self.results.cleared.connect(self.clear_preview)
        self.jobs.finished.connect(self.resume_preview)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self.source_changed)
        self.form.changed.connect(self.preview_option_changed)
        self._capture = capture  # injectable boundary; no COM import or connection during construction
        QTimer.singleShot(0, self.layout_preview)

    def clear_inventory(self):
        self.inventory = None; self.checked_instances.clear()

    def save_sheet_csv(self,path):
        if self.inventory is None:return self._legacy_save_csv(path)
        with Path(path).open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.writer(stream,delimiter=';')
            writer.writerow(('Kaynak','Konfigürasyon','Parça kodu','Gövde','Kalınlık mm','Malzeme',
                             'Montaj adedi','Seçili adet','Durum','Çıktı','Açıklama'))
            for row in self.inventory:
                selected=len(set(row['instances']) & self.checked_instances.get(row['sheet_id'],set()))
                writer.writerow((row['source'],row['configuration'],row.get('code',''),row['body_name'],
                    row.get('thickness_mm',''),row.get('material',''),row['quantity'],selected,
                    'Hazır' if row['status']=='pending' else LABELS.get(row['status'],row['status']),row.get('output',''),row.get('detail','')))

    def update_source_count(self,*args):
        self.source_files.counter.setText(f'Sac gövdeleri · {self.results.model.rowCount()}')
        if not self.results.model.rowCount():
            self.source_files.search.clear();self.source_files.timer.stop();self.source_files.proxy.set_query('')

    def render_inventory(self,*args):
        if self.inventory is None:
            return
        self.results.model.replace(display_rows(self.inventory,self.checked_instances,self.group_instances.isChecked()))
        self.results.table.setColumnHidden(2,all(r.get('body_count',1)==1 for r in self.inventory))
        self.results.refresh_count()

    def sheet_selection_changed(self,row,checked):
        if 'sheet_id' not in row:
            return
        selected = self.checked_instances.setdefault(row['sheet_id'],set())
        if checked: selected.update(row['instances'])
        else: selected.difference_update(row['instances'])

    def select_sheets(self,checked):
        if self.jobs.busy:
            return
        if self.inventory is None:
            for row in self.results.model.rows: row['selected'] = checked
            self.results.model.layoutChanged.emit()
            return
        for row in self.inventory:
            self.checked_instances[row['sheet_id']] = set(row['instances']) if checked and row.get('exportable') else set()
        self.render_inventory()

    def export_arguments(self):
        if self.inventory is None:
            return {}  # Compatibility for integrations supplying legacy result rows.
        return dict(items=selected_items(self.inventory,self.checked_instances),
                    naming=tuple(k for k in ('code','body','configuration','material') if self.form.value('name_'+k)))

    def prepare_export_results(self):
        if self.inventory is None:
            return super().prepare_export_results()
        self.results.results.clear(); self.results.log.clear()
        self.results.refresh_count()

    def scan_active(self):
        self.scan_origin = ('active','')
        self.scan_inventory()

    def scan_file(self):
        if not self.can_start():
            return
        path,_ = QFileDialog.getOpenFileName(self,'SolidWorks sac parçası / montaj seç','','SolidWorks (*.SLDPRT *.SLDASM *.sldprt *.sldasm)')
        if path:
            self.source.setText(str(Path(path).parent))
            self.scan_origin = ('file',path)
            self.scan_inventory()

    def scan_inventory(self):
        if not self.can_start():
            return
        from .sheetmetal import scan_sources
        mode,path = self.scan_origin
        self._preview_cancelled = False
        self.inventory = None; self.checked_instances.clear()
        self.results.reset()
        recursive = self.form.value('recursive')
        self.jobs.start(self,lambda sink,stop:scan_sources(path,recursive,sink,stop,mode=mode))
        self.set_status('Sac gövdeleri taranıyor…')

    def eventFilter(self, watched, event):
        if watched is self.results and event.type() == QEvent.Resize:
            QTimer.singleShot(0, self.layout_preview)
        return super().eventFilter(watched, event)

    def layout_preview(self):
        if self._moving_preview:
            return
        compact = self.results.width() < 700
        if compact == self.preview_compact:
            return
        self._moving_preview = True
        try:
            if compact:
                self.results.tabs.addTab(self.preview, 'Önizleme')
            else:
                index = self.results.tabs.indexOf(self.preview)
                if index >= 0: self.results.tabs.removeTab(index)
                self.preview_splitter.addWidget(self.preview)
                self.preview_splitter.setSizes([max(250, self.results.width()-380), 380])
                self.results.table.show()
                self.preview.show()
            self.preview_compact = compact
        finally:
            self._moving_preview = False

    def _reveal_preview(self):
        self.layout_preview()
        self.results.tabs.setCurrentWidget(self.preview if self.preview_compact else self.preview_splitter)

    def show_preview(self):
        """Reveal and populate the existing panel, even before any output exists."""
        if self.context.closing:
            return False
        self._reveal_preview()
        self._preview_cancelled = False  # An explicit Preview command resumes a stopped read.
        if self.preview_request and not self._source_in_scope(self.preview_request.source):
            self.clear_preview()
        self._awaiting_flat_review = True
        if self.preview_request:
            if self._flat_ready_for_export():
                self.preview.focus_flat()
            elif not self.preview_running and self.preview_pending is None:
                self.refresh_preview()
            return True
        if any(self._source_in_scope(row['source']) for row in self.results.model.rows):
            return self._select_preview_row()
        if not self.can_start():
            return False
        self._preview_after_scan = True
        self.scan()  # Folder discovery only: no CAD Save3 or production export.
        if not self.jobs.busy or self.jobs.owner is not self:
            self._preview_after_scan = False
            return False
        return True

    def _source_in_scope(self, source):
        if self.inventory is not None:
            return any(row['source']==source for row in self.inventory)
        root = self.form.value('source')
        if not root:
            return True
        path, folder = Path(source).resolve(), Path(root).resolve()
        return path.is_relative_to(folder) if self.form.value('recursive') else path.parent == folder

    def _select_preview_row(self):
        if self.context.closing or self._preview_cancelled:
            return False
        self._reveal_preview()
        index = self.results.table.currentIndex()
        if not index.isValid() or not self._source_in_scope(index.data(Qt.UserRole)['source']):
            index = next((candidate for row in range(self.results.proxy.rowCount())
                          if (candidate := self.results.proxy.index(row, 0)).isValid()
                          and self._source_in_scope(candidate.data(Qt.UserRole)['source'])),
                         self.results.proxy.index(-1, 0))
        if not index.isValid():
            self.set_status('Önizleme için görünür bir SLDPRT parçası seçin.', True)
            return False
        self.results.table.setCurrentIndex(index)
        self.request_preview(index.data(Qt.UserRole))
        return True

    def scan(self):
        self.scan_origin = ('folder',self.form.value('source'))
        self.inventory = None; self.checked_instances.clear()
        if not self.jobs.busy and not self.context.closing:
            self._preview_cancelled = False
        super().scan()
        if not self.jobs.busy or self.jobs.owner is not self:
            self._preview_after_scan = False

    def preview_option_changed(self, key):
        if key in ('source', 'recursive'):
            had_inventory = self.inventory is not None
            self.clear_inventory()
            self.scan_origin = ('folder','')
            self.clear_preview()
            if had_inventory:self.results.reset()
        elif key == 'bend_lines' and self.preview_request:
            self.refresh_preview()

    def _flat_ready_for_export(self):
        payload = self.preview_payload
        if (self.preview_running or self.preview_pending is not None or self._preview_cancelled
                or not payload or not payload.flat or not payload.flat.strokes or not self.preview_request):
            return False
        if self.preview_request.bend_lines != self.form.value('bend_lines'):
            return False
        if not self._source_in_scope(self.preview_request.source):
            return False
        try:
            return payload.revision[1] == file_stamp(self.preview_request.source)
        except (RuntimeError, IndexError):
            return False

    def clear_preview(self, *args):
        self.preview_generation += 1
        self.preview_timer.stop()
        self.preview_request = self.preview_pending = self.preview_payload = None
        self._awaiting_flat_review = False
        self.preview.clear()
        if self.watcher.files(): self.watcher.removePaths(self.watcher.files())
        if self.preview_running and self.jobs.owner is self: self.jobs.cancel()

    def selection_changed(self, current, previous=None):
        row = current.data(Qt.UserRole) if current.isValid() else None
        if row:
            self.request_preview(row)
        else:
            self.clear_preview()

    def selected_updated(self, *args):
        if self._preview_cancelled:
            return
        if self.preview_request:
            row = self.preview_row()
            if row: self.request_preview(row)

    def preview_row(self):
        request = self.preview_request
        if request and self.inventory is None:
            return next((r for r in self.results.model.rows if r.get('source')==request.source),None)
        return next((r for r in self.results.model.rows if r.get('source')==request.source
                     and str(r.get('configuration',''))==request.configuration
                     and str(r.get('body_ref',''))==request.body_ref),None) if request else None

    def request_preview(self, row, force=False):
        if row.get('sheet_id') and not Path(row['source']).is_file():
            self.clear_preview(); self.preview.clear(row.get('detail','Kaynak dosya bulunamadı.'))
            return
        bend_lines = self.form.value('bend_lines')
        outputs = [o for o in row.get('outputs', ()) if o.get('status') in ('success', 'skipped')
                   and row.get('bend_lines', bend_lines) == bend_lines]
        output = next((o for o in outputs if o.get('format', '').upper() == 'DXF'), outputs[0] if outputs else {})
        quantity = row.get('quantity')
        request = Request(str(row['source']), str(row.get('configuration', '')), str(row.get('body_ref', '')),
                          str(output.get('path', '')), str(output.get('status', '')), tuple(row.get('source_stamp') or ()),
                          row.get('update_stamp'), quantity if type(quantity) is int and quantity > 0 else None,
                          bool(bend_lines),str(row.get('flat_ref','')),str(row.get('body_name','')),row.get('thickness_mm'))
        if not force and request == self.preview_request:
            return
        self.preview_generation += 1
        self._preview_cancelled = False
        self._stop_message_pending = False
        self.preview_request = self.preview_pending = request
        self.preview_payload = None
        self.preview_force |= force
        self.preview.clear('SolidWorks kaynak ve bükülmüş geometri kontrol ediliyor…')
        self.preview.source_label.setText(Path(request.source).name+(' · '+request.body_name if request.body_name else ''))
        self.preview.source_label.setToolTip(request.source)
        if self.watcher.files(): self.watcher.removePaths(self.watcher.files())
        self.watcher.addPath(request.source)
        if self.preview_running and self.jobs.owner is self: self.jobs.cancel()
        self.preview_timer.start()

    def refresh_preview(self):
        self.selected_updated()
        if self.preview_request:
            request = self.preview_request
            row = self.preview_row()
            if row: self.request_preview(row, force=True)

    def source_changed(self, path):
        if self._preview_cancelled:
            return
        if self.preview_request and path == self.preview_request.source:
            self.refresh_preview()

    def resume_preview(self):
        self.preview_running = False
        if self._preview_cancelled:
            self.preview_pending = None
            self._export_after_preview = False
            if self._stop_message_pending and not self._preview_restore_failed:
                self.set_status('Durduruldu.')
                self.preview.message.setText('Önizleme durduruldu. Yenile ile tekrar okuyabilirsiniz.')
                if self.preview_payload is None or self.preview_payload.flat is None:
                    self.preview.flat_label.setText('Açınım · durduruldu')
                    self.preview.flat_view.show_flat(None, self.preview.message.text())
            self._stop_message_pending = False
            return
        if self._preview_after_scan:
            self._preview_after_scan = False
            self._awaiting_flat_review = True
            QTimer.singleShot(0, self._select_preview_row)
            return
        export = self._export_after_preview
        self._export_after_preview = False
        if export and not self.context.closing:
            QTimer.singleShot(0, self.start_export)
            return
        if self.preview_pending is not None and not self.context.closing:
            self.preview_timer.start()

    def start_export(self):
        if self.context.closing:
            return
        if self.inventory is not None and not selected_items(self.inventory,self.checked_instances):
            self.set_status('Aktarım için en az bir hazır sac gövdesini işaretleyin.',True)
            return
        if self.inventory is not None and self.preview_before_export.isChecked():
            chosen={row['sheet_id'] for row in selected_items(self.inventory,self.checked_instances)}
            current=self.preview_row()
            if current is None or current.get('sheet_id') not in chosen:
                for index in range(self.results.proxy.rowCount()):
                    candidate=self.results.proxy.index(index,0)
                    row=candidate.data(Qt.UserRole)
                    if row and row.get('sheet_id') in chosen:
                        self.results.table.setCurrentIndex(candidate);self.request_preview(row)
                        break
        if self.inventory is not None and not self.source.text():
            first = self.inventory[0]['source'] if self.inventory else ''
            # Naming root only; active-assembly rows outside it remain in scope.
            if first:
                with QSignalBlocker(self.source):
                    self.source.setText(str(Path(first).parent))
        if self.inventory is None and not self.results.model.rows:
            if self.scan_origin[0] in ('active','file'):
                self.scan_inventory()
            else:
                self.scan()
            self.set_status('Önce sac listesini kontrol edin; sonra işaretli gövdeleri dışa aktarın.')
            return
        if self._preview_restore_failed and not self.preview_running:
            self.set_status('Kaynak durumu geri alınamadığı için aktarım başlatılmadı. SolidWorks’te kaynağı kontrol edip Yenile ile tekrar doğrulayın.', True)
            return
        if self.preview_before_export.isChecked() and (not self._flat_ready_for_export()
                                                       or not self.preview.flat_view.isVisible()):
            if self.jobs.busy and not (self.preview_running and self.jobs.owner is self):
                self.can_start()
                return
            self._preview_cancelled = False
            if self.show_preview():
                self.set_status('Önce açınımı kontrol edin. Önizleme tamamlanmadan dosyalar kaydedilmez; hazır olunca Aktarımı başlat düğmesine tekrar basın.')
            return
        if self.preview_running and self.jobs.owner is self and self.jobs.busy:
            self._export_after_preview = True
            self.preview_pending = None; self.preview_timer.stop()
            self.preview_generation += 1  # discard a result already in transit
            self.jobs.cancel()
            self.set_status('Önizleme durduruluyor; kaynak durumu geri alınınca aktarım başlayacak.')
            return
        self._preview_cancelled = False
        self._stop_message_pending = False
        self._preview_after_scan = False
        self._awaiting_flat_review = False
        super().start_export()

    def cancel_pending_preview(self):
        self._export_after_preview = False
        self._preview_after_scan = False
        self._awaiting_flat_review = False
        self.preview_pending = None; self.preview_timer.stop()
        self._preview_cancelled = True
        self._stop_message_pending = True
        self.preview_generation += 1
        self.stop_button.setEnabled(False)
        self.set_status('Durdurma isteği alındı; yeni önizleme ve aktarım başlatılmayacak.')

    def start_preview(self):
        if self.preview_pending is None or self.context.closing:
            return
        if self.jobs.busy:
            return  # CAD export has priority; its finished signal resumes this request.
        request, generation, force = self.preview_pending, self.preview_generation, self.preview_force
        self.preview_pending = None; self.preview_force = False
        self.preview_running = True
        def operation(sink, stop):
            try:
                if force: self.preview_cache.clear()
                with cancellable_read(stop):
                    geometry_reader = self._capture_geometry
                    if geometry_reader is None and self._capture is capture:
                        geometry_reader = capture_geometry
                    if geometry_reader is not None:
                        geometry = geometry_reader(request, self.preview_cache, stop)
                        sink.put(('dxf_preview_geometry', (generation, geometry)))
                        sink.flush()  # Show 3D even while the later flat COM call is pending.
                    payload = self._capture(request, self.preview_cache, stop)
                sink.put(('dxf_preview', (generation, payload)))
            except Cancelled:
                sink.put(('dxf_preview_cancelled', (generation, 'Önizleme durduruldu. Yenile ile tekrar okuyabilirsiniz.')))
            except RestoreError as error:
                sink.put(('dxf_preview_restore_error', (generation, str(error))))
            except Exception as error:
                sink.put(('dxf_preview_error', (generation, str(error))))
        self.jobs.start(self, operation)

    def set_busy(self, busy):
        super().set_busy(busy)
        if hasattr(self, 'preview'):
            self.results.model.locked = busy
            self.preview.refresh_button.setEnabled(not busy)
            # With review enabled, Start reveals the flat without cancelling it.
            # Direct export can preempt capture only after native state restores.
            if busy and self.preview_running: self.start_button.setEnabled(True)

    def process_events(self, events):
        ordinary = []
        for kind, value in events:
            if kind == 'sheet_inventory':
                if self._preview_cancelled or self.context.closing:
                    continue
                self.inventory = value
                self.checked_instances = {r['sheet_id']:set(r['instances']) if r.get('exportable') else set() for r in value}
                self.render_inventory()
                continue
            if kind=='done' and value.get('state')=='preview' and self._preview_cancelled:
                value=dict(value,state='cancelled')
            if kind in ('sheet_current','sheet_result'):
                identifier = value if kind=='sheet_current' else value['sheet_id']
                changes = dict(status='running') if kind=='sheet_current' else {k:v for k,v in value.items()
                    if k not in ('row_id','instances','quantity','selected')}
                for row in list(self.results.model.rows):
                    if row.get('sheet_id')==identifier:
                        self.results.model.upsert(dict(row,**changes))
                if kind=='sheet_result':
                    for row in self.inventory or ():
                        if row['sheet_id']==identifier: row.update(changes)
                    self.results.results.append(value)
                    self.results.append_log(f"{value['status']} · {value['source']} [{value['configuration']}] · {value['body_name']} · {value['detail']}")
                    self.results.refresh_count()
                continue
            if kind == 'done' and value.get('state') == 'preview' and not self._preview_cancelled:
                self._preview_after_scan |= self.preview_before_export.isChecked()
            if kind == 'done' and value.get('native_restore_failed'):
                self._preview_restore_failed = True
                self._export_after_preview = False
                self.preview_pending = None
            if kind == 'dxf_preview_restore_error':
                self._preview_restore_failed = True
                self._export_after_preview = False
                self.preview_pending = None
                self.preview_timer.stop()
                self.preview_generation += 1
                if self.preview_running and self.jobs.owner is self: self.jobs.cancel()
                self.preview.clear(value[1])
                self.set_status('SolidWorks oturum durumu geri alınamadı: ' + value[1], True)
            elif kind in ('dxf_preview_geometry', 'dxf_preview', 'dxf_preview_error', 'dxf_preview_cancelled'):
                generation, result = value
                if generation != self.preview_generation:
                    continue  # An older selection must never repaint the current part.
                if kind in ('dxf_preview_geometry', 'dxf_preview'):
                    self._preview_restore_failed = False
                    self.preview_payload = result
                    self.preview.show_payload(result)
                    self.set_status('3D önizleme hazır · ' + result.configuration)
                    if kind == 'dxf_preview_geometry':
                        self.preview.flat_label.setText('Açınım · okunuyor…')
                        self.set_status('3D önizleme hazır; açınım okunuyor…')
                    elif result.flat:
                        self.set_status('Açınım hazır · listeden parçaları kontrol edin. Kaydetmek için Aktarımı başlat düğmesine basın.')
                        if self._awaiting_flat_review:
                            self._reveal_preview()
                            self.preview.focus_flat()
                    else:
                        self.set_status('Açınım önizlemesi okunamadı. Ayrıntıyı kontrol edip Yenile ile tekrar deneyin.', True)
                else:
                    self.preview_payload = None
                    self.preview.clear(result)
                    self.set_status('Önizleme: ' + result, kind == 'dxf_preview_error')
            else:
                ordinary.append((kind, value))
        if ordinary:
            super().handle_events(ordinary)
            if any(kind=='done' and value.get('state')=='preview' for kind,value in ordinary) and self.inventory is not None:
                summary=next(value for kind,value in ordinary if kind=='done' and value.get('state')=='preview')
                warnings=len(summary.get('warnings',()))
                self.set_status(f'Tarama tamamlandı. {len(self.inventory)} benzersiz sac gövdesi bulundu.'
                                +(f' · {warnings} uyarı: Günlük bölümünü kontrol edin.' if warnings else ''))
