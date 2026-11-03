"""QA (2026-11-03): finishing background jobs must not deadlock the GUI thread.

JobWorker used to be deleted (deleteLater) on its own QThread. ~QObject holds
Qt's signal/slot mutex while PySide acquires the GIL, and the GUI thread may hold
the GIL while waiting for that mutex inside connect(): an ABBA deadlock that froze
the window ("Yanıt vermiyor"). The worker is now handed back to and deleted on
the GUI thread. The stress runs in a subprocess because a deadlocked process
cannot be interrupted from Python.
"""

import os
from pathlib import Path
import subprocess
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[1]

STRESS = textwrap.dedent('''
    import os
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtCore import QObject, QThread, Signal
    from PySide6.QtWidgets import QApplication, QPushButton
    from gui_qt.workers import JobManager

    app = QApplication([])

    class Owner(QObject):
        def handle_events(self, values): pass
        def set_busy(self, busy): pass
        def set_status(self, *args, **kwargs): pass
        def job_finished(self): pass

    class Sender(QObject):
        signal = Signal()

    owner, manager, started = Owner(), JobManager(), 0
    deleted_on = []
    widgets = [QPushButton() for _ in range(200)]
    while started < 600:
        if not manager.busy:
            manager.start(owner, lambda sink, stop: sink.put(('x', 1)))
            manager.worker.destroyed.connect(lambda *_: deleted_on.append(QThread.currentThread() is app.thread()))
            started += 1
        for widget in widgets:            # GUI thread connects while holding the GIL
            sender = Sender()
            sender.signal.connect(widget.click)
            sender.signal.disconnect(widget.click)
        app.processEvents()
    while manager.busy:
        app.processEvents()
    for _ in range(5):
        app.processEvents()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    print('OK', started, all(deleted_on), len(deleted_on))
''')


def test_many_finishing_jobs_never_deadlock_and_workers_die_on_gui_thread():
    environment = dict(os.environ, PYTHONPATH=str(ROOT), QT_QPA_PLATFORM='offscreen')
    result = subprocess.run([sys.executable, '-c', STRESS], cwd=ROOT, env=environment,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    line = [row for row in result.stdout.splitlines() if row.startswith('OK')][-1]
    _, started, all_on_gui, deleted = line.split()
    assert started == '600' and all_on_gui == 'True' and int(deleted) >= 599
