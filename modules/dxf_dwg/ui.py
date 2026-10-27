"""Sheet-metal exports and source-matched preview; shared export flow is intact."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QEvent, Slot, QFileSystemWatcher, QObject
from PySide6.QtWidgets import QSplitter
from gui_qt.export import ExportPage
from gui_qt.components import label
from modules.cad_converter.models import Cancelled
from modules.cad_converter.api import RestoreError
from .preview.models import Request, MeshCache
from .preview.panel import PreviewPanel
from .preview.solidworks import capture, file_stamp
from .preview.solidworks import capture_geometry
from .preview.cancellation import cancellable_read


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
        self.preview_before_export = self.options_form.check(
            'preview_before_export', 'Kaydetmeden önce önizle', True)
        self.preview_before_export.setToolTip(
            'Önce seçili parçanın açınımını gösterir. Listeden parçaları kontrol edin; '
            'kaydetmek için Aktarımı başlat düğmesine tekrar basın.')
        self.form.fields['preview_before_export'] = self.preview_before_export
        self.options_form.form.addRow(label('Aktarımda değiştirilmiş SolidWorks belgeleri otomatik kaydedilir.', 'muted'))
        self.start_button.setToolTip('DXF/DWG aktarır; açık değiştirilmiş SolidWorks belgelerine sessiz Tümünü Kaydet uygular.')
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
        self.preview_splitter.setSizes([450, 380])
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
        if not self.jobs.busy and not self.context.closing:
            self._preview_cancelled = False
        super().scan()
        if not self.jobs.busy or self.jobs.owner is not self:
            self._preview_after_scan = False

    def preview_option_changed(self, key):
        if key in ('source', 'recursive'):
            self.clear_preview()
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
            row = next((r for r in self.results.model.rows if r.get('source') == self.preview_request.source), None)
            if row: self.request_preview(row)

    def request_preview(self, row, force=False):
        bend_lines = self.form.value('bend_lines')
        outputs = [o for o in row.get('outputs', ()) if o.get('status') in ('success', 'skipped')
                   and row.get('bend_lines', bend_lines) == bend_lines]
        output = next((o for o in outputs if o.get('format', '').upper() == 'DXF'), outputs[0] if outputs else {})
        quantity = row.get('quantity')
        request = Request(str(row['source']), str(row.get('configuration', '')), str(row.get('body_ref', '')),
                          str(output.get('path', '')), str(output.get('status', '')), tuple(row.get('source_stamp') or ()),
                          row.get('update_stamp'), quantity if type(quantity) is int and quantity > 0 else None,
                          bool(bend_lines))
        if not force and request == self.preview_request:
            return
        self.preview_generation += 1
        self._preview_cancelled = False
        self._stop_message_pending = False
        self.preview_request = self.preview_pending = request
        self.preview_payload = None
        self.preview_force |= force
        self.preview.clear('SolidWorks kaynak ve bükülmüş geometri kontrol ediliyor…')
        self.preview.source_label.setText(Path(request.source).name)
        self.preview.source_label.setToolTip(request.source)
        if self.watcher.files(): self.watcher.removePaths(self.watcher.files())
        self.watcher.addPath(request.source)
        if self.preview_running and self.jobs.owner is self: self.jobs.cancel()
        self.preview_timer.start()

    def refresh_preview(self):
        self.selected_updated()
        if self.preview_request:
            request = self.preview_request
            row = next((r for r in self.results.model.rows if r.get('source') == request.source), None)
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
        if self._preview_restore_failed and not self.preview_running:
            self.set_status('Kaynak durumu geri alınamadığı için otomatik kayıt başlatılmadı. SolidWorks’te kaynağı kontrol edip Yenile ile tekrar doğrulayın.', True)
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
            self.preview.refresh_button.setEnabled(not busy)
            # With review enabled, Start reveals the flat without cancelling it.
            # Direct export can preempt capture only after native state restores.
            if busy and self.preview_running: self.start_button.setEnabled(True)

    def process_events(self, events):
        ordinary = []
        for kind, value in events:
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
        if ordinary: super().handle_events(ordinary)
