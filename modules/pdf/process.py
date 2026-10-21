"""Run SolidWorks PDF COM calls outside the Qt application process.

The frozen, windowless executable invokes itself with a private worker flag.
File-based JSON messages also work when PyInstaller supplies no stdout/stderr.
Only plain values cross the process boundary; COM objects never do.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from solidworks import diagnostics
from solidworks.process_watch import start_watch


WORKER_FLAG = '--pdf-export-worker'
PROTOCOL = 1
_EVENTS = {'worker_ready', 'files', 'total', 'phase', 'log', 'current',
           'result', 'counts', 'progress', 'done'}
_PHASES = {
    'scan': 'klasör taraması', 'connect': 'SolidWorks bağlantısı',
    'drawing': 'teknik resim aktarımı', 'prepare_pdf': 'PDF hazırlığı',
    'open_document': 'teknik resmi açma', 'pdf_options': 'PDF ayarları',
    'activate_document': 'teknik resmi etkinleştirme', 'save_pdf': 'PDF kaydı',
    'validate_pdf': 'PDF doğrulaması', 'publish_pdf': 'PDF çıktısını yerleştirme',
    'close_document': 'teknik resmi kapatma', 'restore_document': 'önceki belgeye dönüş',
    'release_application': 'SolidWorks nesnelerini bırakma',
    'uninitialize_com': 'COM bağlantısını kapatma',
}


def _command(request):
    entry = [] if getattr(sys, 'frozen', False) else [str(Path(__file__).resolve().parents[2]/'main.py')]
    return [sys.executable, *entry, WORKER_FLAG, str(request)]


class _Sink:
    def __init__(self, stream):
        self.stream = stream

    def put(self, event):
        self.stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False)+'\n')
        self.stream.flush()


class _Stop:
    def __init__(self, path):
        self.path = path

    def is_set(self):
        return self.path.exists()


def run_worker(request_path):
    """Internal CLI entry point. Do not import or initialize Qt here."""
    request_path = Path(request_path)
    config = json.loads(request_path.read_text(encoding='utf-8'))
    if config.get('protocol') != PROTOCOL:
        raise ValueError('PDF yardımcı süreç sürümü uyumsuz.')
    for name in ('recursive', 'overwrite'):
        if type(config.get(name)) is not bool:
            raise ValueError('Geçersiz PDF aktarım seçeneği.')
    folder = request_path.parent
    diagnostics.enable('pdf-worker', config.get('diagnostic_log'))
    context = {}

    def checkpoint(phase, **values):
        if phase == 'drawing':
            context.clear()
        context.update(values, phase=phase)
        diagnostics.record(f'pdf_phase phase={phase} index={context.get("index", 0)}')
        try:
            temporary = folder/'phase.tmp'
            temporary.write_text(json.dumps(context, ensure_ascii=False), encoding='utf-8')
            os.replace(temporary, folder/'phase.json')
        except OSError:
            pass  # Diagnostics must never turn a successful export into a failure.

    with (folder/'events.jsonl').open('a', encoding='utf-8', buffering=1) as stream:
        sink = _Sink(stream)
        sink.put(('worker_ready', {'protocol': PROTOCOL, 'pid': os.getpid()}))
        try:
            from modules.pdf.exporter import export_drawings
            export_drawings(config['source'], config['output'], config['recursive'],
                            config['overwrite'], sink, _Stop(folder/'stop'), checkpoint=checkpoint)
        except Exception as error:
            sink.put(('done', dict(state='error', total=0, processed=0, succeeded=0,
                                   skipped=0, failed=0, error=str(error))))
            return 1
    return 0


def _context(folder):
    try:
        value = json.loads((folder/'phase.json').read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _cleanup_temporary(context, output):
    """Only remove this exporter's uniquely named, unpublished PDF."""
    try:
        path = Path(context.get('temporary', ''))
        if re.fullmatch(r'\.gokworks-[0-9a-f]{32}\.pdf', path.name):
            if path.resolve().is_relative_to(Path(output).resolve()):
                path.unlink(missing_ok=True)
    except (OSError, ValueError, RuntimeError):
        pass


def export_drawings(source_folder, output_folder, include_subfolders,
                    overwrite_existing, events, stop_event=None):
    """Queue-compatible wrapper. The terminal event waits for clean worker exit.

    Cancellation is cooperative: finish an in-flight SaveAs, then stop. Never
    terminate SolidWorks or a thread in the middle of a CAD operation.
    """
    summary = dict(state='completed', total=0, processed=0, succeeded=0,
                   skipped=0, failed=0, error='')
    terminal = None
    current = None
    current_reported = False
    diagnostic_log = diagnostics.new_log_path('pdf-worker')
    process = None
    fault = None
    context = {}

    def receive(line):
        nonlocal terminal, current, current_reported
        event = json.loads(line)
        if not isinstance(event, list) or len(event) != 2 or event[0] not in _EVENTS:
            raise ValueError('Geçersiz PDF yardımcı süreç mesajı.')
        kind, value = event
        if terminal is not None:
            raise ValueError('PDF bitişinden sonra beklenmeyen mesaj alındı.')
        if kind == 'worker_ready':
            if not isinstance(value, dict) or value.get('protocol') != PROTOCOL:
                raise ValueError('PDF yardımcı süreç sürümü uyumsuz.')
            pid = value.get('pid')
            if type(pid) is not int or pid <= 0:
                raise ValueError('PDF yardımcı süreç kimliği okunamadı.')
            # In onefile mode Popen.pid may belong to the extraction launcher.
            # Observe the actual Python worker for native exit/event matching.
            start_watch(pid, diagnostic_log, 'pdf-worker')
            diagnostics.record('pdf_transport_ready')
            return
        if kind not in ('counts', 'progress', 'total'):
            diagnostics.record('pdf_transport_event='+kind)
        if kind in ('counts', 'done'):
            if not isinstance(value, dict):
                raise ValueError('PDF aktarım özeti okunamadı.')
            for key in ('total', 'processed', 'succeeded', 'skipped', 'failed'):
                if type(value.get(key)) is not int or value[key] < 0:
                    raise ValueError('PDF aktarım sayıları okunamadı.')
            summary.update({key: value[key] for key in summary if key in value})
        if kind == 'done':
            if value.get('state') not in ('completed', 'empty', 'cancelled', 'error'):
                raise ValueError('PDF aktarım sonucu okunamadı.')
            terminal = value
            return  # CoUninitialize / interpreter shutdown may still crash.
        if kind == 'total':
            if type(value) is not int or value < 0:
                raise ValueError('PDF dosya sayısı okunamadı.')
            summary['total'] = value
        elif kind == 'current':
            current, current_reported = value, False
        elif kind == 'result':
            counter = {'success': 'succeeded', 'skipped': 'skipped', 'error': 'failed'}[value['status']]
            summary[counter] += 1
            summary['processed'] += 1
            if value['source'] == current:
                current_reported = True
        events.put((kind, value))

    with tempfile.TemporaryDirectory(prefix='gokworks-pdf-') as directory:
        folder = Path(directory)
        request = folder/'request.json'
        event_path = folder/'events.jsonl'
        try:
            request.write_text(json.dumps(dict(protocol=PROTOCOL, source=str(source_folder),
                output=str(output_folder), recursive=bool(include_subfolders),
                overwrite=bool(overwrite_existing),
                diagnostic_log=str(diagnostic_log) if diagnostic_log else None),
                ensure_ascii=False), encoding='utf-8')
            event_path.touch()
            # The owned worker always finishes before normal GUI shutdown, so
            # it can reuse the live onefile extraction. Independent exit
            # observers still use RESET_ENVIRONMENT=1 to outlive the GUI.
            env = dict(os.environ)
            env.pop('PYINSTALLER_RESET_ENVIRONMENT', None)
            process = subprocess.Popen(_command(request), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            diagnostics.record(f'pdf_process_started pid={process.pid}')
            pending = b''
            with event_path.open('rb') as stream:
                while True:
                    if stop_event is not None and stop_event.is_set():
                        (folder/'stop').touch(exist_ok=True)
                    chunk = stream.read(64*1024)
                    if chunk:
                        pending += chunk
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n', 1)
                            receive(line)
                        if len(pending) > 32*1024*1024:
                            raise ValueError('PDF yardımcı süreç mesajı çok büyük.')
                    elif process.poll() is not None:
                        # poll() can race with the child's final flush: drain once more.
                        tail = stream.read()
                        pending += tail
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n', 1)
                            receive(line)
                        if pending:
                            raise ValueError('PDF yardımcı süreç mesajı yarım kaldı.')
                        break
                    else:
                        time.sleep(.02)
            if process.returncode != 0 or terminal is None:
                raise RuntimeError('PDF yardımcı süreci beklenmedik şekilde kapandı.')
        except Exception as error:
            fault = str(error)
        finally:
            if process is not None and process.poll() is None:
                # Keep request/IPC files alive until the owned helper has stopped.
                # A user cancellation must not kill an active SolidWorks SaveAs.
                (folder/'stop').touch(exist_ok=True)
                process.wait()
            context = _context(folder)
            _cleanup_temporary(context, output_folder)

    if fault is not None:
        diagnostics.record('pdf_transport_failed')
        phase = context.get('phase', '')
        code = process.returncode if process is not None else None
        exit_code = f'{code} (0x{code & 0xffffffff:08X})' if code is not None and os.name == 'nt' else str(code)
        stage = _PHASES.get(phase, 'yardımcı süreci başlatma')
        detail = f'{fault} Aşama: {stage}. Çıkış kodu: {exit_code}.'
        if terminal and terminal.get('error'):
            detail += ' '+terminal['error']
        if diagnostic_log:
            diagnostics.record(f'worker_failure phase={phase} index={context.get("index", 0)} exit={exit_code}', diagnostic_log)
            detail += f' Tanılama kaydı: {diagnostic_log}'
        if current and not current_reported:
            summary['failed'] += 1
            summary['processed'] += 1
            events.put(('result', dict(source=current, status='error', detail=detail)))
        summary.update(state='error', error=detail)
    events.put(('done', summary))
    diagnostics.record('pdf_transport_done state='+summary['state'])
