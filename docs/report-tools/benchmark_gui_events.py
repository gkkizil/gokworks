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
    startup_begin = time.perf_counter()
    app = GokworksPdfApp(settings_path=Path(temporary)/'settings.json')
    app.update()
    startup_ms = (time.perf_counter()-startup_begin)*1000
    app.after_cancel(app._poll_id)
    app.after_cancel(app._preload_id)
    app._preload_id = None
    first_switches = {}
    for mode in ('dxf_dwg', 'k_factor', 'iso_fits', 'geometric_tolerances', 'pdf'):
        start = time.perf_counter()
        app._switch_mode(mode)
        app.update_idletasks()
        first_switches[mode] = (time.perf_counter()-start)*1000
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
    data.update(startup_ms=startup_ms, first_switch_ms=first_switches)
    large_paths = [str(Path(temporary)/f'part-{i:05}.slddrw') for i in range(10000)]
    def prepare_large():
        app._reset()
        app._fill_files(large_paths)
        for index in range(0, 10000, 100):
            app._update_row(large_paths[index], 'error', 'Synthetic error')
        app.table.selection_set('file_0')
        app.search_query.set('part-00')
        app.status_filter.set('Hatalı')
        assert len(app.table.get_children()) == 10

    def measure_operation(operation):
        delays = []
        begin = time.perf_counter()
        app.after(0, lambda: delays.append((time.perf_counter()-begin)*1000))
        operation()
        elapsed = (time.perf_counter()-begin)*1000
        app.update()
        assert delays
        return elapsed, delays[0]

    clear_runs, reset_runs = [], []
    alternating_runs = []
    for _ in range(3):
        prepare_large()
        def alternate_filters():
            for query, status in (('part-00', 'Tüm durumlar'), ('part-09', 'Hatalı'),
                                  ('part-00', 'Hatalı')):
                app.search_query.set(query)
                app.status_filter.set(status)
        alternating_runs.append(measure_operation(alternate_filters))
        assert len(app.table.get_children()) == 10
        clear_runs.append(measure_operation(app._clear_filters))
        assert app.table.get_children() == tuple(f'file_{i}' for i in range(10000))
        assert app.table.selection() == ('file_0',)
        app.search_query.set('part-00')
        app.status_filter.set('Hatalı')
        reset_runs.append(measure_operation(app._reset))
        assert not app.row_ids and not app.table.get_children()
    counters = {}
    for name in ('clear', 'reset'):
        prepare_large()
        operation = app._clear_filters if name == 'clear' else app._reset
        with patch.object(app.table, 'set_children', wraps=app.table.set_children) as bulk, \
                patch.object(app.table, 'item', wraps=app.table.item) as items:
            operation()
            counters[name] = dict(bulk_filters=bulk.call_count, row_calls=items.call_count)
    data['large_list'] = dict(rows=10000, clear_runs_ms=clear_runs, reset_runs_ms=reset_runs,
                             alternating_filter_runs_ms=alternating_runs,
                             clear_median_ms=statistics.median(x[0] for x in clear_runs),
                             reset_median_ms=statistics.median(x[0] for x in reset_runs),
                             counters=counters)
    Path(args.output).write_text(json.dumps(data, indent=2))
    print(json.dumps(data, indent=2))
    app._on_close()
