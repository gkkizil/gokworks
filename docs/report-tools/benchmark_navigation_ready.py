"""Measure normal startup, idle work, and menu clicks with a full Tk event loop."""

import argparse
import inspect
import json
from pathlib import Path
import statistics
import sys
from tempfile import TemporaryDirectory
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from modules.pdf.window import GokworksPdfApp


def measure():
    with TemporaryDirectory() as temporary:
        started = time.perf_counter()
        options = {'prepare_navigation': True} if 'prepare_navigation' in inspect.signature(GokworksPdfApp).parameters else {}
        app = GokworksPdfApp(settings_path=Path(temporary)/'settings.json', **options)
        app.update()
        startup_ms = (time.perf_counter()-started)*1000
        errors, gaps, clicks = [], [], []
        app.report_callback_exception = lambda *args: errors.append(str(args))
        built_during_navigation = 0
        build = app._build_window

        def tracked_build():
            nonlocal built_during_navigation
            built_during_navigation += 1
            return build()

        app._build_window = tracked_build
        last_beat = time.perf_counter()

        def heartbeat():
            nonlocal last_beat
            now = time.perf_counter()
            gaps.append((now-last_beat)*1000)
            last_beat = now
            app.after(16, heartbeat)

        def pump(seconds):
            until = time.perf_counter()+seconds
            while time.perf_counter() < until:
                app.update()
                time.sleep(.001)

        app.after(16, heartbeat)
        pages_at_ready = len(app._pages)
        try:
            # Keep the production idle preloader enabled in the baseline.
            pump(.95)
            for mode in app._MODES[1:]:
                started = time.perf_counter()
                app.nav_buttons[mode].invoke()
                app.update()
                clicks.append({'mode': mode, 'click_and_events_ms': (time.perf_counter()-started)*1000})
                assert app.mode == mode
                pump(.1)
            pump(.2)
            assert not errors, errors
            return dict(startup_until_ready_ms=startup_ms, pages_at_ready=pages_at_ready,
                        page_builds_after_ready=built_during_navigation,
                        click_median_ms=statistics.median(item['click_and_events_ms'] for item in clicks),
                        click_max_ms=max(item['click_and_events_ms'] for item in clicks),
                        heartbeat_max_gap_ms=max(gaps), heartbeat_samples=len(gaps), clicks=clicks,
                        method='One run, Linux/Xvfb, real Tk events; normal startup path, 950 ms idle, '
                               'eight menu clicks with 100 ms dwell. Heartbeat requested every 16 ms. '
                               'Startup time includes preparing all pages where supported. '
                               'Baseline idle preloading remains enabled. No native Windows/SolidWorks measurement.')
        finally:
            app._on_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    args = parser.parse_args()
    data = measure()
    Path(args.output).write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(data, indent=2))
