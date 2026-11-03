"""Serialized CAD jobs with queued Qt signals, bounded event batches and safe stop."""

import threading
import time
import traceback

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, Qt
import shiboken6
from solidworks import diagnostics


class EventSink:
    """Queue-compatible endpoint for unchanged service engines; used on worker only.

    Events are batched for at most ``interval`` seconds. A short timer delivers
    a partial batch when the engine then blocks in a long CAD/COM call, so
    status text such as the current part is not held until the next event.
    """
    interval = .016

    def __init__(self, emit):
        self.emit = emit
        self.pending = []
        self.last_flush = time.monotonic()
        self._lock = threading.Lock()
        self._timer = None
        self._closed = False

    def put(self, value):
        with self._lock:
            self.pending.append(value)
            elapsed = time.monotonic() - self.last_flush
            if len(self.pending) >= 64 or elapsed >= self.interval:
                self._flush_locked()
            elif self._timer is None and not self._closed:
                self._timer = threading.Timer(max(0., self.interval - elapsed), self._timed_flush)
                self._timer.daemon = True
                self._timer.start()

    def _timed_flush(self):
        with self._lock:
            self._timer = None
            if not self._closed:
                self._flush_locked()

    def _flush_locked(self):
        if self.pending:
            values, self.pending = self.pending, []
            self.emit(values)
            self.last_flush = time.monotonic()

    def flush(self):
        with self._lock:
            self._flush_locked()

    def close(self):
        """Deliver the rest and stop timed delivery before the emitter is deleted."""
        with self._lock:
            self._closed = True
            timer, self._timer = self._timer, None
            self._flush_locked()
        if timer is not None:
            timer.cancel()


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
            sink.close()
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
        self._joining = False
        self.join_timer = QTimer(self)
        self.join_timer.setSingleShot(True)
        self.join_timer.setInterval(5)
        self.join_timer.timeout.connect(self._finished)

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
        self.worker.completed.connect(self.thread.quit)
        self.thread.finished.connect(self._finished)
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
        thread = self.thread
        if thread is None:
            return
        if not self._joining:
            diagnostics.record('qt_job_finished_received')
        # QThread.finished precedes native thread-local destructors. Keep all
        # owned references and the CAD lock until the OS thread has also exited.
        # A blocking wait here can deadlock Python cleanup that needs the GIL.
        if not thread.wait(0):
            if not self._joining:
                diagnostics.record('qt_job_native_join_pending')
            self._joining = True
            self.join_timer.start()
            return
        self.join_timer.stop()
        self._joining = False
        diagnostics.record('qt_job_native_joined')
        owner, worker = self.owner, self.worker
        self.thread = self.worker = self.owner = self.stop = None
        if worker is not None and shiboken6.isValid(worker):
            # Never destroy the worker on its own QThread (no deleteLater there):
            # ~QObject holds Qt's signal/slot mutex while PySide asks for the
            # GIL, and the GUI thread may hold the GIL while waiting for that
            # mutex in connect() - an ABBA deadlock that froze the window. The
            # native thread has been joined above, so nothing else can touch
            # the worker; delete it here, synchronously, on the GUI thread.
            shiboken6.delete(worker)
        thread.deleteLater()
        if owner is not None:
            owner.set_busy(False)
        self.busyChanged.emit(False)
        self.finished.emit()
        if owner is not None:
            owner.job_finished()
        diagnostics.record('qt_job_finished_delivered')
