"""Measure native Tk resize work after preparing all application pages."""

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import sys
from tempfile import TemporaryDirectory
import time
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from modules.pdf.window import GokworksPdfApp


def measure():
    with TemporaryDirectory() as temporary:
        app = GokworksPdfApp(settings_path=Path(temporary)/'settings.json', prepare_navigation=True)
        errors, measurements = [], []
        app.report_callback_exception = lambda *args: errors.append(str(args))

        def settle(seconds=.12):
            until = time.perf_counter()+seconds
            while time.perf_counter() < until:
                app.update()
                time.sleep(.002)

        counts = Counter()
        for mode, page in app._pages.items():
            workspace = page['workspace']
            tk.Misc.bind(workspace, '<Configure>',
                         lambda event, owner=workspace, key=mode:
                         counts.update([key]) if event.widget is owner else None, add='+')
        try:
            for active in ('pdf', 'weight'):
                app._switch_mode(active)
                app.geometry('1000x690')
                settle()
                counts.clear()
                times = []
                for width, height in ([(1100, 720), (1200, 750), (1300, 800), (1440, 900),
                                       (1300, 800), (1200, 750), (1100, 720), (1000, 690)]*2):
                    started = time.perf_counter()
                    app.geometry(f'{width}x{height}')
                    app.update()
                    times.append((time.perf_counter()-started)*1000)
                settle()
                measurements.append(dict(mode=active, resize_median_ms=statistics.median(times),
                                         resize_max_ms=max(times), configure_by_page=dict(counts),
                                         inactive_configure_events=sum(n for key, n in counts.items() if key != active)))
            assert not errors, errors
            return dict(pages_prepared=len(app._pages), measurements=measurements,
                        method='One Linux/Xvfb run; production startup, all nine pages prepared. '
                               'Sixteen window size changes from 1000×690 to 1440×900 and back per page, '
                               'each followed by real Tk update(). Not a Windows frame-rate measurement.')
        finally:
            app._on_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    args = parser.parse_args()
    data = measure()
    Path(args.output).write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(data, indent=2))
