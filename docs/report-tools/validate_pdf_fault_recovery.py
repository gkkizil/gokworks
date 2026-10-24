"""Exercise repeated worker failures while navigating the real Qt application.

The disposable subprocess deliberately exits with code 23. It uses fake CAD
data and never contacts SolidWorks. Source files and settings are temporary.
"""

import argparse
import faulthandler
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QThread, QTimer, Qt
from gui_qt.app import create_application, MainWindow
from modules.pdf import process as pdf


def validate(destination, cycles):
    app = create_application([])
    helper = ROOT / 'tests/support/pdf_worker.py'
    assert helper.is_file()
    heartbeat = []
    with TemporaryDirectory(prefix='GOKWORKS-pdf-fault-test-') as folder:
        folder = Path(folder)
        source = folder / 'Örnek çizimler'
        output = folder / 'Çıktılar'
        source.mkdir()
        for name in ('çizim.SLDDRW', 'ikinci.SLDDRW'):
            (source / name).write_bytes(b'disposable fake CAD source')
        originals = {p: p.read_bytes() for p in source.iterdir()}
        with patch.dict('os.environ', LOCALAPPDATA=str(folder / 'local')):
            window = MainWindow(folder / 'settings.json')
            window.show()
            page = window.pages['pdf']
            page.source.setText(str(source))
            page.output.setText(str(output))
            gui_receivers = []
            page.results.model.dataChanged.connect(lambda *args:
                gui_receivers.append(QThread.currentThread() is app.thread()), Qt.DirectConnection)
            timer = QTimer(window)
            timer.setInterval(10)
            timer.timeout.connect(lambda: heartbeat.append(time.perf_counter()))
            timer.start()
            modes = list(window.pages)
            durations = []
            with patch.object(pdf, '_command', lambda request:
                    [sys.executable, str(helper), 'delayed_crash', str(request)]):
                for index in range(cycles):
                    start = time.perf_counter()
                    before = len(heartbeat)
                    window.navigate('pdf')
                    page.start_button.click()
                    assert window.jobs.busy
                    window.navigate(modes[(index % (len(modes) - 1)) + 1])
                    # Exercise the same native event dispatcher as app.exec().
                    # Bound each job with a Qt timer rather than repeatedly
                    # entering synthetic QTest polling waits.
                    loop=QEventLoop();deadline=QTimer()
                    deadline.setSingleShot(True);deadline.timeout.connect(loop.quit)
                    def completed(busy):
                        if not busy:loop.quit()
                    window.jobs.busyChanged.connect(completed)
                    try:
                        deadline.start(10000)
                        if window.jobs.busy:loop.exec()
                    finally:
                        deadline.stop();window.jobs.busyChanged.disconnect(completed)
                    assert not window.jobs.busy, 'Worker recovery did not complete'
                    assert len(heartbeat) > before
                    assert window.isVisible() and page.start_button.isEnabled()
                    assert not page.stop_button.isEnabled()
                    assert page.results.model.rowCount() == 2
                    assert [r['status'] for r in page.results.results] == ['success', 'error']
                    assert 'PDF kaydı' in page.status_text and '23' in page.status_text
                    assert (output / 'çizim.pdf').is_file()
                    assert not list(output.glob('.gokworks-*.pdf'))
                    assert all(p.read_bytes() == content for p, content in originals.items())
                    durations.append(round((time.perf_counter() - start) * 1000, 2))
                    page.results.clear_button.click()
                    assert page.results.model.rowCount() == 0 and not page.results.log.toPlainText()
            timer.stop()
            assert gui_receivers and all(gui_receivers)
            assert not any(thread.isRunning() for thread in window.findChildren(QThread))
            window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    report = dict(status='passed',qt_platform=app.platformName(),cycles=cycles,
        worker_expected_exit_code=23,recovery_durations_ms=durations,heartbeat_count=len(heartbeat),
        all_result_callbacks_on_gui_thread=True,source_files_preserved=True,
        clear_after_failure=True,solidworks_live_tested=False)
    destination = Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--cycles',type=int,default=20)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 100:
        parser.error('cycles must be between 1 and 100')
    # A C++ deadlock cannot reliably be interrupted by pytest's signal timeout.
    faulthandler.dump_traceback_later(60,exit=True)
    try:
        validate(args.destination,args.cycles)
    finally:
        faulthandler.cancel_dump_traceback_later()
