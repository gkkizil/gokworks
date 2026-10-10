"""Measure Tk event rendering using synthetic results, without SolidWorks."""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('repo', help='Checkout to measure (e.g. .)')
parser.add_argument('output', help='Output JSON path')
args = parser.parse_args()
sys.path.insert(0, str(Path(args.repo).resolve()))
from pdf.window import GokworksPdfApp

with TemporaryDirectory() as temporary:
    app = GokworksPdfApp(settings_path=Path(temporary)/'settings.json')
    app.update()
    app.after_cancel(app._poll_id)
    app.after_cancel(app._preload_id)
    app._preload_id = None
    for mode in ('dxf_dwg', 'k_factor', 'iso_fits', 'geometric_tolerances', 'pdf'):
        app._switch_mode(mode)
        app.update_idletasks()
    switches = []
    for _ in range(10):
        for mode in ('dxf_dwg', 'k_factor', 'iso_fits', 'geometric_tolerances', 'pdf'):
            start = time.perf_counter()
            app._switch_mode(mode)
            app.update_idletasks()
            switches.append((time.perf_counter()-start)*1000)
    paths = [str(Path(temporary)/f'part-{i:05}.slddrw') for i in range(2000)]

    def fill_events():
        app._reset()
        app._fill_files(paths)
        app._set_busy(True)
        for index, path in enumerate(paths[:500], 1):
            app.events.put(('current', path))
            app.events.put(('result', dict(source=path, output=path+'.pdf',
                                           status='success', detail='Aktarım tamamlandı')))
            app.events.put(('counts', dict(total=2000, succeeded=index, skipped=0, failed=0)))
            app.events.put(('progress', (index, 2000)))
        app.events.put(('done', dict(state='completed', total=2000, processed=500,
                                     succeeded=500, skipped=0, failed=0, error='')))

    def drain():
        durations = []
        while app.busy:
            start = time.perf_counter()
            app._process_events()
            durations.append((time.perf_counter()-start)*1000)
            app.after_cancel(app._poll_id)
            app.update_idletasks()
        assert len(app.results) == 500
        assert app.stat_values['succeeded'].cget('text') == '500'
        assert 'Tamamlandı' in app.status_label.cget('text')
        return durations

    elapsed, callbacks = [], []
    for _ in range(3):
        fill_events()
        start = time.perf_counter()
        callbacks.extend(drain())
        elapsed.append((time.perf_counter()-start)*1000)
    # Count paints separately so instrumentation does not inflate timings.
    fill_events()
    with patch.object(app.log_box, 'insert', wraps=app.log_box.insert) as logs, \
            patch.object(app.progress, 'set', wraps=app.progress.set) as progress:
        drain()
        paints = dict(log_inserts=logs.call_count, progress_updates=progress.call_count)
    data = dict(warm_switch_median_ms=statistics.median(switches),
                burst_median_ms=statistics.median(elapsed), burst_runs_ms=elapsed,
                callback_median_ms=statistics.median(callbacks), callback_max_ms=max(callbacks),
                redraw_calls=paints)
    Path(args.output).write_text(json.dumps(data, indent=2))
    print(json.dumps(data, indent=2))
    app._on_close()
