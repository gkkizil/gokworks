"""Serialized CAD jobs with queued Qt signals, bounded event batches and safe stop."""

import threading
import time
import traceback

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from solidworks import diagnostics


class EventSink:
    """Queue-compatible endpoint for unchanged service engines; used on worker only."""
    def __init__(self, emit):
        self.emit = emit
        self.pending = []
        self.last_flush = time.monotonic()

    def put(self, value):
        self.pending.append(value)
        if len(self.pending) >= 64 or time.monotonic() - self.last_flush >= .016:
            self.flush()

    def flush(self):
        if self.pending:
            values, self.pending = self.pending, []
            self.emit(values)
            self.last_flush = time.monotonic()


class JobWorker(QObject):
    batch = Signal(object)
    completed = Signal()

    def __init__(self, operation, stop):
        super().__init__()
        self.operation, self.stop = operation, stop

    @Slot()
    def run(self):
        diagnostics.record('qt_worker_run_started')
        sink = EventSink(self.batch.emit)
        try:
            self.operation(sink, self.stop)
        except Exception as error:
            diagnostics.record('qt_worker_exception='+type(error).__name__)
            sink.put(('job_error', {'error': str(error), 'traceback': traceback.format_exc()}))
        finally:
            diagnostics.record('qt_worker_flush_started')
            sink.flush()
            diagnostics.record('qt_worker_completed_signal')
            self.completed.emit()


class JobManager(QObject):
    busyChanged = Signal(bool)
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread = None
        self.worker = None
        self.owner = None
        self.stop = None

    @property
    def busy(self):
        return self.thread is not None

    def start(self, owner, operation):
        if self.busy:
            owner.set_status('Başka bir işlem sürüyor. Tamamlanmasını bekleyin veya durdurun.', error=True)
            return False
        self.owner = owner
        diagnostics.record('qt_job_start owner='+type(owner).__name__)
        self.stop = threading.Event()
        self.thread = QThread(self)
        self.worker = JobWorker(operation, self.stop)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.batch.connect(owner.handle_events, Qt.QueuedConnection)
        self.worker.completed.connect(self.worker.deleteLater)
        self.worker.completed.connect(self.thread.quit)
        self.thread.finished.connect(self._finished)
        self.thread.finished.connect(self.thread.deleteLater)
        owner.set_busy(True)
        self.busyChanged.emit(True)
        self.thread.start()
        return True

    def cancel(self):
        if self.stop is not None:
            self.stop.set()
            if self.owner is not None:
                self.owner.set_status('Durduruluyor… Geçerli işlemin doğrulaması tamamlanıyor.')

    @Slot()
    def _finished(self):
        diagnostics.record('qt_job_finished_received')
        owner = self.owner
        self.thread = self.worker = self.owner = self.stop = None
        if owner is not None:
            owner.set_busy(False)
        self.busyChanged.emit(False)
        self.finished.emit()
        if owner is not None:
            owner.job_finished()
        diagnostics.record('qt_job_finished_delivered')
