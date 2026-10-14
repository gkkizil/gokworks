"""Measure first paints, cached navigation and queued clicks with real Tk."""

import argparse
import gc
import json
import statistics
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output')
parser.add_argument('--runs', type=int, default=3)
args = parser.parse_args()
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pdf.window import GokworksPdfApp

MODES = ('dxf_dwg', 'k_factor', 'iso_fits', 'geometric_tolerances', 'bom', 'bolt')
cold = {mode: [] for mode in MODES}
warm, preload, bursts = [], [], []


def open_app(path):
    gc.collect()
    app = GokworksPdfApp(settings_path=path)
    app.after_cancel(app._preload_id)
    app._preload_id = None
    app.update()
    return app


def paint_switch(app, mode):
    start = time.perf_counter()
    app._switch_mode(mode)
    app.update_idletasks()
    return (time.perf_counter()-start)*1000


for run in range(args.runs):
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        app = open_app(root/'navigation.json')
        try:
            for mode in MODES:
                cold[mode].append(paint_switch(app, mode))
            for _ in range(5):
                for mode in ('pdf', *MODES):
                    warm.append(paint_switch(app, mode))
        finally:
            app._on_close()

        app = open_app(root/'preload.json')
        try:
            for _ in MODES:
                app._last_ui_activity = time.monotonic()-2
                start = time.perf_counter()
                app._preload_page()
                app.update_idletasks()
                preload.append((time.perf_counter()-start)*1000)
                app.after_cancel(app._preload_id)
                app._preload_id = None
            assert app.mode == 'pdf'
            assert all(not page['workspace'].winfo_viewable()
                       for mode, page in app._pages.items() if mode != 'pdf')
        finally:
            app._on_close()

        app = open_app(root/'burst.json')
        try:
            start = time.perf_counter()
            for mode in MODES:
                app.nav_buttons[mode].invoke()
            app.update()
            bursts.append(dict(elapsed_ms=(time.perf_counter()-start)*1000,
                               pages_created=len(app._pages)-1))
            assert app.mode == MODES[-1]
        finally:
            app._on_close()

data = dict(runs=args.runs,
            first_paint_median_ms={mode: statistics.median(values) for mode, values in cold.items()},
            all_first_paints_median_ms=statistics.median([v for values in cold.values() for v in values]),
            cached_paint_median_ms=statistics.median(warm),
            cached_paint_max_ms=max(warm),
            preload_median_ms=statistics.median(preload),
            queued_clicks=bursts,
            note='Real Tk on Linux/Xvfb, no SolidWorks. Paint timings include update_idletasks; '
                 'exclude delayed layout callbacks and navigation animation completion.')
Path(args.output).write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
print(json.dumps(data, indent=2))
