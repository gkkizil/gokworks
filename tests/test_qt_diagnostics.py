"""Native Qt aborts must leave useful records even without a console."""

from pathlib import Path
from queue import Queue
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
import weakref

from gui_qt import services


def test_application_records_clean_window_and_python_shutdown(tmp_path):
    script = '''
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from gui_qt import app
class AutoClose(app.MainWindow):
    def __init__(self):
        super().__init__(Path(sys.argv[1])/'settings.json')
        QTimer.singleShot(30, self.close)
app.MainWindow = AutoClose
raise SystemExit(app.main())
'''
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env={**os.environ, 'LOCALAPPDATA': str(tmp_path), 'QT_QPA_PLATFORM': 'offscreen'},
                            cwd=Path(__file__).resolve().parents[1], timeout=20)
    log = next((tmp_path/'GOKWORKS/logs').glob('GOKWORKS-gui-*.log')).read_text()
    assert result.returncode == 0, log
    for marker in ('qt_runtime', 'gui_ready', 'gui_close_accepted', 'gui_about_to_quit',
                   'gui_event_loop_returned code=0', 'normal_python_shutdown'):
        assert marker in log


def test_native_qt_fatal_records_message_and_stack_before_abort(tmp_path):
    log = tmp_path/'gui-native.log'
    script = '''
import os, sys
if os.name == 'nt':
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(2)
    ctypes.CDLL('ucrtbase')._set_abort_behavior(0, 3)
else:
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
from solidworks import diagnostics
from gui_qt.diagnostics import install
from PySide6.QtCore import qFatal, qWarning
assert diagnostics.enable('gui', sys.argv[1])
install()
sys.stderr = None
qWarning('Customer drawing C:/PRIVATE/customer.SLDDRW')
qFatal('QThread: Destroyed while thread is still running')
'''
    result = subprocess.run([sys.executable, '-c', script, str(log)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            cwd=Path(__file__).resolve().parents[1], timeout=15)
    assert result.returncode != 0
    text = log.read_text()
    assert 'level=QtFatalMsg' in text and 'QThread: Destroyed' in text
    assert 'qt_native_failure_stack' in text and 'Current thread' in text
    assert 'PRIVATE' not in text and 'customer' not in text


def test_connection_probe_releases_application_before_com_shutdown():
    references, released = [], []
    class Application:
        RevisionNumber = '33.5.0'
    def connect():
        app = Application()
        references.append(weakref.ref(app))
        return app
    com = SimpleNamespace(CoInitialize=lambda: None,
        CoUninitialize=lambda: released.append(references[0]() is None))
    events = Queue()
    with patch.dict(sys.modules, pythoncom=com), patch('solidworks.connection.connect_to_solidworks', new=connect):
        services.check_connection(events, None)
    assert released == [True]
    assert events.get() == ('connection_done', dict(connected=True, revision='33.5.0'))
