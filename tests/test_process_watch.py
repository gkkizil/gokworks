"""Exit traces must survive target termination without revealing CAD paths."""

from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from solidworks import process_watch as watch


def event_xml(pid='0x34c8', module='Qt6Gui.dll', exception='c0000005', event='1000', provider='Application Error', created='0x1dc400000000000'):
    return f'''<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System><Provider Name="{provider}"/><EventID>{event}</EventID></System>
    <EventData><Data Name="ProcessId">{pid}</Data><Data Name="ModuleName">{module}</Data>
    <Data Name="ProcessCreationTime">{created}</Data>
    <Data Name="ExceptionCode">{exception}</Data>
    <Data Name="AppPath">C:\\PRIVATE\\customer.SLDDRW</Data>
    <Data Name="ModulePath">C:\\PRIVATE\\Qt6Gui.dll</Data></EventData></Event>'''


def test_fault_report_matches_pid_and_preserves_only_module_and_exception():
    result = watch._fault_details(event_xml(module='C:\\PRIVATE\\Qt6Gui.dll'), 13512)
    assert result == 'windows_application_error module=Qt6Gui.dll exception=0xC0000005'
    assert 'PRIVATE' not in result and 'SLDDRW' not in result


def test_old_fault_from_reused_pid_is_not_this_process():
    created = 0x1DC400000000000
    assert watch._fault_details(event_xml(created=hex(created-1)), 13512, created) is None
    assert watch._fault_details(event_xml(created=''), 13512, created) is None
    assert watch._fault_details(event_xml(), 13512, created) is not None


@pytest.mark.parametrize('xml', [
    event_xml(pid='0x34c9'), event_xml(pid='invalid'), event_xml(event='1001'),
    event_xml(provider='Other application'), event_xml(exception='PRIVATE'),
    '<not-xml', 'x'*(256*1024+1),
])
def test_unrelated_or_invalid_event_is_not_a_cause(xml):
    assert watch._fault_details(xml, 13512) is None


def test_event_query_closes_all_handles_even_after_early_match():
    class Handle:
        def __init__(self, xml=None):self.xml, self.closed = xml, False
        def Close(self):self.closed = True
    query = Handle()
    events = [Handle(event_xml()), Handle(event_xml(pid='0x12'))]
    api = SimpleNamespace(EvtQueryChannelPath=1, EvtQueryReverseDirection=512,
        EvtRenderEventXml=1, EvtQuery=lambda *args: query, EvtNext=lambda *args: events,
        EvtRender=lambda event, flags: event.xml)
    with patch.dict(sys.modules, win32evtlog=api):
        assert watch._application_fault(13512).endswith('0xC0000005')
    assert query.closed and all(event.closed for event in events)


def test_observer_failure_cannot_prevent_export_or_leak_paths(tmp_path, monkeypatch):
    log = tmp_path/'gui.log'
    calls, closed = [], []
    api = SimpleNamespace(OpenProcess=lambda *args: calls.append(args) or 2468,
                          CloseHandle=closed.append)
    monkeypatch.setattr(watch.sys, 'platform', 'win32')
    monkeypatch.setattr(watch, '_kernel32', lambda: api)
    monkeypatch.setattr(watch.subprocess, 'STARTUPINFO', SimpleNamespace, raising=False)
    monkeypatch.setattr(watch.subprocess, 'CREATE_NO_WINDOW', 0, raising=False)
    with patch.object(watch.subprocess, 'Popen', side_effect=OSError('C:/PRIVATE/customer.SLDDRW')):
        assert watch.start_watch(123, log, 'gui') is None
    assert calls == [(0x00101000, True, 123)]  # No memory access/terminate permission.
    assert closed == [2468]
    text = log.read_text()
    assert 'process_watch_unavailable' in text and 'error=OSError' in text
    assert 'PRIVATE' not in text and 'customer' not in text


def test_observer_cli_bypasses_gui_and_cad_on_unsupported_platform(tmp_path):
    if sys.platform == 'win32':
        pytest.skip('The unsupported-platform case is specific to non-Windows.')
    # gui_qt.app fails immediately if the watcher accidentally imports Qt or CAD.
    script = '''
import runpy, sys
from pathlib import Path
sys.modules['gui_qt'] = None
sys.modules['pythoncom'] = None
sys.argv = [sys.argv[1], '--process-exit-watch', '1', '1', 'gui', sys.argv[2]]
runpy.run_path(sys.argv[0], run_name='__main__')
'''
    result = subprocess.run([sys.executable, '-c', script,
        str(Path(__file__).resolve().parents[1]/'main.py'), str(tmp_path/'trace.log')],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=10)
    assert result.returncode == 2, result.stderr.decode(errors='replace')
    assert not (tmp_path/'trace.log').exists()


@pytest.mark.skipif(sys.platform != 'win32', reason='Requires real Windows process handles')
@pytest.mark.parametrize('exit_code', [0, 0xC0000409])
def test_real_windows_observer_records_exit_after_target_is_gone(tmp_path, exit_code):
    # The native ExitProcess path bypasses all Python/Qt shutdown hooks, like
    # the user's incomplete logs. No actual SolidWorks session is used.
    script = '''
import ctypes, sys
from ctypes import wintypes
sys.stdin.buffer.read(1)
api = ctypes.WinDLL('kernel32')
api.ExitProcess.argtypes = [wintypes.UINT]
api.ExitProcess(int(sys.argv[1]))
'''
    target = subprocess.Popen([sys.executable, '-c', script, str(exit_code)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    observer = None
    log = tmp_path/'exit.log'
    try:
        observer = watch.start_watch(target.pid, log, 'pdf-worker')
        assert observer is not None, log.read_text() if log.exists() else 'observer did not start'
        # Release immediately, before the observer necessarily imports Python.
        # The already-inherited handle must still yield the exact exit code.
        target.stdin.write(b'1');target.stdin.close()
        assert target.wait(timeout=10) & 0xFFFFFFFF == exit_code
        assert observer.wait(timeout=15) == 0, log.read_text()
        text = log.read_text()
        assert f'process_exit target=pdf-worker pid={target.pid} code={exit_code} (0x{exit_code:08X})' in text
        assert 'process_watch_failed' not in text
    finally:
        if target.poll() is None:
            target.kill();target.wait(timeout=5)
        if observer is not None and observer.poll() is None:
            observer.kill();observer.wait(timeout=5)


def test_frozen_observer_uses_same_executable_and_no_gui_arguments(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    log = tmp_path/'exit.log'
    assert watch._command(2468, 13512, 'gui', log) == [
        sys.executable, watch.WATCH_FLAG, '2468', '13512', 'gui', str(log)]
