"""Real process/IPC/cancellation regressions, with CAD replaced at its boundary."""

from pathlib import Path
from queue import Queue
import subprocess
import sys
from threading import Event
from unittest.mock import patch

import pytest

from pdf import process as pdf


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'local'))
    source, output = tmp_path/'kaynak', tmp_path/'çıktı'
    source.mkdir()
    (source/'çizim.SLDDRW').write_bytes(b'untouched CAD source')
    (source/'ikinci.SLDDRW').write_bytes(b'untouched second source')
    output.mkdir()
    (output/'ikinci.pdf').write_bytes(b'original output')
    return source, output


def command(mode):
    helper = Path(__file__).parent/'support/pdf_worker.py'
    return lambda request: [sys.executable, str(helper), mode, str(request)]


def run(paths, mode, stop=None, events=None):
    source, output = paths
    events = Queue() if events is None else events
    with patch.object(pdf, '_command', command(mode)):
        pdf.export_drawings(source, output, True, True, events, stop)
    records = list(events.queue)
    assert sum(kind == 'done' for kind, value in records) == 1
    assert records[-1][0] == 'done'
    assert (source/'çizim.SLDDRW').read_bytes() == b'untouched CAD source'
    assert (output/'ikinci.pdf').read_bytes() == b'original output'
    return records, records[-1][1]


def test_real_cli_empty_source_starts_without_solidworks(paths):
    source, output = paths
    for path in source.iterdir():path.unlink()
    events = Queue()
    pdf.export_drawings(source, output, True, False, events)
    records = list(events.queue)
    assert records[-1][0] == 'done'
    assert records[-1][1]['state'] == 'empty'
    assert len([event for event in records if event[0] == 'done']) == 1


def test_real_worker_exports_all_sheets_with_fake_com_and_no_qt(paths):
    (paths[0]/'ikinci.SLDDRW').unlink()
    records, result = run(paths, 'com_export')
    assert result['state'] == 'completed', result
    assert result['succeeded'] == result['processed'] == result['total'] == 1
    assert (paths[1]/'çizim.pdf').read_bytes().startswith(b'%PDF-')
    assert not list(paths[1].glob('.gokworks-*.pdf'))


def test_failed_export_keeps_phase_history_in_worker_log(paths):
    (paths[0]/'ikinci.SLDDRW').unlink()
    records, result = run(paths, 'com_failure')
    assert result['failed'] == 1
    log = next((paths[0].parent/'local/GOKWORKS/logs').glob('GOKWORKS-pdf-worker-*.log')).read_text()
    assert 'pdf_phase phase=save_pdf index=1' in log
    assert 'pdf_phase phase=uninitialize_com index=1' in log
    assert 'normal_python_shutdown' in log
    assert 'çizim.SLDDRW' not in log and str(paths[0]) not in log


def test_abnormal_exit_keeps_parent_completed_files_and_originals(paths):
    records, result = run(paths, 'crash')
    assert result['state'] == 'error'
    assert (result['succeeded'], result['failed'], result['processed'], result['total']) == (1, 1, 2, 2)
    assert 'PDF kaydı' in result['error'] and '23' in result['error']
    assert (paths[1]/'çizim.pdf').read_bytes().endswith(b'%%EOF\n')
    assert not list(paths[1].glob('.gokworks-*.pdf'))
    assert [v['status'] for k, v in records if k == 'result'] == ['success', 'error']
    log = next((paths[0].parent/'local/GOKWORKS/logs').glob('GOKWORKS-pdf-worker-*.log')).read_text()
    assert 'phase=save_pdf index=2 exit=' in log
    assert 'untouched CAD' not in log and str(paths[0]) not in log
    assert 'Current thread' in log


def test_crash_after_done_is_not_success_and_does_not_invent_failed_file(paths):
    records, result = run(paths, 'after_done')
    assert result['state'] == 'error'
    assert result['succeeded'] == result['processed'] == 1
    assert result['failed'] == 0
    assert len([event for event in records if event[0] == 'result']) == 1


def test_cancellation_reaches_child_and_preserves_finished_pdf(paths):
    stop = Event()
    class StopAfterResult(Queue):
        def put(self, event):
            super().put(event)
            if event[0] == 'result':stop.set()
    records, result = run(paths, 'cancel', stop, StopAfterResult())
    assert result['state'] == 'cancelled', result
    assert result['succeeded'] == result['processed'] == 1
    assert (paths[1]/'çizim.pdf').exists()


def test_fragmented_json_and_utf8_are_not_lost(paths):
    records, result = run(paths, 'fragmented')
    assert result['state'] == 'empty', result
    assert ('log', 'Ölçü çizimi aktarılıyor') in records


@pytest.mark.parametrize('mode', ['truncated', 'no_done'])
def test_incomplete_protocol_cannot_report_completed(paths, mode):
    records, result = run(paths, mode)
    assert result['state'] == 'error'


def test_launch_failure_reports_done_without_raising_into_gui(paths):
    events = Queue()
    with patch.object(pdf.subprocess, 'Popen', side_effect=OSError('cannot launch helper')):
        pdf.export_drawings(*paths, True, False, events)
    assert list(events.queue)[-1][1]['state'] == 'error'
    assert 'cannot launch helper' in list(events.queue)[-1][1]['error']


def test_crash_cleanup_only_removes_owned_temporary_under_output(paths, tmp_path):
    external = tmp_path/('.gokworks-'+'b'*32+'.pdf')
    external.write_bytes(b'keep outside output')
    pdf._cleanup_temporary({'temporary': str(external)}, paths[1])
    pdf._cleanup_temporary({'temporary': str(paths[1]/'ikinci.pdf')}, paths[1])
    assert external.exists()
    assert (paths[1]/'ikinci.pdf').read_bytes() == b'original output'


def test_frozen_worker_invokes_same_executable_without_source_or_console(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    assert pdf._command(tmp_path/'request.json') == [sys.executable, pdf.WORKER_FLAG, str(tmp_path/'request.json')]


def test_exception_trace_does_not_log_cad_path_or_exception_contents(tmp_path):
    log = tmp_path/'fault.log'
    script = '''
import sys
from solidworks import diagnostics
assert diagnostics.enable('test', sys.argv[1])
raise RuntimeError(sys.argv[2])
'''
    result = subprocess.run([sys.executable, '-c', script, str(log), 'C:/PRIVATE/CAD/customer.SLDDRW'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            cwd=Path(__file__).resolve().parents[1], timeout=10)
    assert result.returncode != 0
    text = log.read_text()
    assert 'unhandled_exception=RuntimeError' in text and 'File ' in text
    assert 'customer' not in text and 'PRIVATE' not in text
