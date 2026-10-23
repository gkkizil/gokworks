"""Measure the source Qt application; no SolidWorks or production CAD required."""

import json
from pathlib import Path
try:
    import resource
except ImportError:
    resource = None  # Windows has no stdlib resource module.
import statistics
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
started, cpu = time.perf_counter(), time.process_time()
from gui_qt.app import MainWindow, create_application
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


def main():
    application = create_application([])
    with TemporaryDirectory() as folder:
        window = MainWindow(Path(folder)/'settings.json'); window.show()
        application.processEvents()
        startup = (time.perf_counter()-started)*1000
        before = len(QApplication.allWidgets()); timings = []; ticks = []
        timer = QTimer(); timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(time.perf_counter()))
        timer.start()
        for _ in range(10):
            for mode in window.pages:
                begin = time.perf_counter(); window.navigate(mode); application.processEvents()
                timings.append((time.perf_counter()-begin)*1000)
        timer.stop()
        after = len(QApplication.allWidgets())
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None
        data = dict(platform=sys.platform, backend='source / Qt '+application.platformName(),
                    startup_including_imports_ms=startup,
                    navigation_events=len(timings), navigation_median_ms=statistics.median(timings),
                    navigation_max_ms=max(timings),
                    timer_max_gap_ms=max((b-a)*1000 for a,b in zip(ticks,ticks[1:])),
                    widget_count_before=before, widget_count_after=after,
                    peak_rss_kib=peak,
                    cpu_seconds=time.process_time()-cpu, solidworks_live=False,
                    limitations='Linux source measurement, not Windows EXE/native CAD performance or a heap leak proof.')
        destination = Path(sys.argv[1]); destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
        window.close()
        print(json.dumps(data))


if __name__ == '__main__':
    main()
