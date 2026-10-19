"""Subprocess fault injector; never contacts SolidWorks or starts Qt."""

import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

mode, request = sys.argv[1:]
folder = Path(request).parent
config = json.loads(Path(request).read_text(encoding='utf-8'))
source = Path(config['source'])
output = Path(config['output'])
output.mkdir(parents=True, exist_ok=True)


def emit(kind, value):
    with (folder/'events.jsonl').open('ab', buffering=0) as stream:
        stream.write((json.dumps([kind, value], ensure_ascii=False)+'\n').encode('utf-8'))


def summary(state='completed', total=1, processed=1, succeeded=1):
    return dict(state=state, total=total, processed=processed,
                succeeded=succeeded, skipped=0, failed=0, error='')


if mode in ('com_export', 'com_failure'):
    from types import SimpleNamespace
    from pdf import exporter
    from pdf.process import run_worker
    from tests.support.solidworks import FakeDrawing, FakePdfApp

    def variant(kind, value):
        return SimpleNamespace(kind=kind, value=value)

    drawing = FakeDrawing(source/'çizim.SLDDRW')
    drawing.save_ok = mode == 'com_export'
    application = FakePdfApp([drawing], opened=[])
    exporter.pythoncom = SimpleNamespace(VT_BYREF=1, VT_I4=2, VT_ARRAY=4, VT_BSTR=8,
                                        CoInitialize=lambda: None, CoUninitialize=lambda: None)
    exporter.win32com = SimpleNamespace(client=SimpleNamespace(VARIANT=variant,
        dynamic=SimpleNamespace(DumbDispatch=lambda value: value)))
    exporter.connect_to_solidworks = lambda: application
    code = run_worker(request)
    assert application.closed == ['çizim.SLDDRW']
    assert not any(name.startswith('PySide6') for name in sys.modules)
    raise SystemExit(code)

if mode == 'fragmented':
    # Split Turkish UTF-8 characters and JSON records across multiple reads.
    line = (json.dumps(['log', 'Ölçü çizimi aktarılıyor'], ensure_ascii=False)+'\n').encode('utf-8')
    with (folder/'events.jsonl').open('ab', buffering=0) as stream:
        for byte in line:
            stream.write(bytes([byte]))
            time.sleep(.003)
    emit('done', summary('empty', 0, 0, 0))
    raise SystemExit(0)

if mode == 'truncated':
    with (folder/'events.jsonl').open('ab') as stream:
        stream.write(b'["result", {"source":')
    raise SystemExit(0)

if mode == 'no_done':
    raise SystemExit(0)

emit('worker_ready', {'protocol': 1, 'pid': os.getpid()})
emit('files', [str(source/'çizim.SLDDRW'), str(source/'ikinci.SLDDRW')])
emit('total', 2)
first = str(source/'çizim.SLDDRW')
emit('current', first)
(output/'çizim.pdf').write_bytes(b'%PDF-1.7\nvalid complete PDF\n%%EOF\n')
emit('result', dict(source=first, output=str(output/'çizim.pdf'), status='success', detail='Aktarıldı.'))

if mode == 'cancel':
    deadline = time.monotonic()+10
    while not (folder/'stop').exists():
        if time.monotonic() > deadline:
            raise SystemExit(29)
        time.sleep(.01)
    emit('done', summary('cancelled', 2, 1, 1))
    raise SystemExit(0)

if mode == 'after_done':
    emit('done', summary('completed', 2, 1, 1))
    # A COM/interpreter shutdown failure must not become a completed UI job.
    os._exit(23)

second = str(source/'ikinci.SLDDRW')
emit('current', second)
temporary = output/('.gokworks-'+'a'*32+'.pdf')
temporary.write_bytes(b'incomplete export')
(folder/'phase.json').write_text(json.dumps(dict(phase='save_pdf', index=2,
    temporary=str(temporary), output=str(output/'ikinci.pdf'))), encoding='utf-8')
from solidworks import diagnostics
diagnostics.enable('pdf-worker', config['diagnostic_log'])
# Record a native-style traceback in this expendable process, not the Qt test.
import faulthandler
faulthandler.dump_traceback(file=diagnostics._stream, all_threads=True)
if mode == 'delayed_crash':
    time.sleep(.3)
os._exit(23)
