"""Sheet-metal exports and source-matched preview; shared export flow is intact."""

from PySide6.QtCore import Qt, QTimer, QEvent, Slot, QFileSystemWatcher, QObject
from PySide6.QtWidgets import QSplitter
from gui_qt.export import ExportPage
from modules.cad_converter.models import Cancelled
from modules.cad_converter.api import RestoreError
from .preview.models import Request, MeshCache
from .preview.panel import PreviewPanel
from .preview.solidworks import capture


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
        self._events = _PageEvents(self)
        self.handle_events = self._events.accept
        self.preview = PreviewPanel()
        self.preview_cache = MeshCache()
        self.preview_generation = 0
        self.preview_request = self.preview_pending = None
        self.preview_running = False
        self.preview_force = False
        self._export_after_preview = False
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
        self.form.changed.connect(lambda key: self.clear_preview() if key == 'source' else None)
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

    def show_preview(self):
        self.layout_preview()
        self.results.tabs.setCurrentWidget(self.preview if self.preview_compact else self.preview_splitter)

    def clear_preview(self, *args):
        self.preview_generation += 1
        self.preview_timer.stop()
        self.preview_request = self.preview_pending = self.preview_payload = None
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
        if self.preview_request:
            row = next((r for r in self.results.model.rows if r.get('source') == self.preview_request.source), None)
            if row: self.request_preview(row)

    def request_preview(self, row, force=False):
        outputs = [o for o in row.get('outputs', ()) if o.get('status') in ('success', 'skipped')]
        output = next((o for o in outputs if o.get('format', '').upper() == 'DXF'), outputs[0] if outputs else {})
        quantity = row.get('quantity')
        request = Request(str(row['source']), str(row.get('configuration', '')), str(row.get('body_ref', '')),
                          str(output.get('path', '')), str(output.get('status', '')), tuple(row.get('source_stamp') or ()),
                          row.get('update_stamp'), quantity if type(quantity) is int and quantity > 0 else None,
                          bool(row.get('bend_lines', self.form.value('bend_lines'))))
        if not force and request == self.preview_request:
            return
        self.preview_generation += 1
        self.preview_request = self.preview_pending = request
        self.preview_payload = None
        self.preview_force |= force
        self.preview.clear('SolidWorks kaynak ve bükülmüş geometri kontrol ediliyor…')
        from pathlib import Path
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
        if self.preview_request and path == self.preview_request.source:
            self.refresh_preview()

    def resume_preview(self):
        self.preview_running = False
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
        if self.preview_running and self.jobs.owner is self and self.jobs.busy:
            self._export_after_preview = True
            self.preview_pending = None; self.preview_timer.stop()
            self.preview_generation += 1  # discard a result already in transit
            self.jobs.cancel()
            self.set_status('Önizleme durduruluyor; kaynak durumu geri alınınca aktarım başlayacak.')
            return
        super().start_export()

    def cancel_pending_preview(self):
        self._export_after_preview = False
        self.preview_pending = None; self.preview_timer.stop()

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
            # Export remains available to preempt our own background capture.
            # The live COM call finishes and state restores before export starts.
            if busy and self.preview_running: self.start_button.setEnabled(True)

    def process_events(self, events):
        ordinary = []
        for kind, value in events:
            if kind == 'dxf_preview_restore_error':
                self._export_after_preview = False
                self.preview_pending = None
                self.preview_timer.stop()
                self.preview_generation += 1
                if self.preview_running and self.jobs.owner is self: self.jobs.cancel()
                self.preview.clear(value[1])
                self.set_status('SolidWorks oturum durumu geri alınamadı: ' + value[1], True)
            elif kind in ('dxf_preview', 'dxf_preview_error', 'dxf_preview_cancelled'):
                generation, result = value
                if generation != self.preview_generation:
                    continue  # An older selection must never repaint the current part.
                if kind == 'dxf_preview':
                    self.preview_payload = result
                    self.preview.show_payload(result)
                    self.set_status('3D önizleme hazır · ' + result.configuration)
                else:
                    self.preview.clear(result)
                    self.set_status('Önizleme: ' + result, kind == 'dxf_preview_error')
            else:
                ordinary.append((kind, value))
        if ordinary: super().handle_events(ordinary)
