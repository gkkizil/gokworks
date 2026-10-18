"""Capture native Qt screens and replay the original navigation/resize profile."""

import argparse
import cProfile
import json
from pathlib import Path
import pstats
import sys
from tempfile import TemporaryDirectory
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gui_qt.app import create_application, MainWindow
from gui_qt.package_check import run
from PySide6.QtWidgets import QApplication


def audit(destination):
    destination.mkdir(parents=True,exist_ok=True)
    app = create_application([])
    with TemporaryDirectory() as folder:
        w = MainWindow(Path(folder)/'settings.json')
        w.show()
        w.set_theme('dark')
        w.resize(1366,900)
        app.processEvents()
        for mode in w.pages:
            w.navigate(mode)
            app.processEvents()
            w.grab().save(str(destination/(mode+'-dark.png')))
        w.set_theme('light')
        w.navigate('bolt')
        app.processEvents()
        w.grab().save(str(destination/'bolt-light.png'))
        w.set_theme('dark')
        w.navigate('weight')
        w.resize(1024,700)
        app.processEvents()
        w.grab().save(str(destination/'weight-compact.png'))
        # Match the baseline's expanded weight page and original _MODES order.
        w.resize(1440,900)
        app.processEvents()
        replay_modes = ('pdf','dxf_dwg','k_factor','iso_fits','geometric_tolerances',
                        'bom','bolt','naming','weight')
        profile = cProfile.Profile()
        profile.enable()
        start = time.perf_counter()
        for _ in range(2):
            for mode in replay_modes:
                w.navigation[mode].click()
                app.processEvents()
            for width in range(1000,1441,20):
                w.resize(width,780)
                app.processEvents()
        elapsed = time.perf_counter()-start
        profile.disable()
        with (destination/'profile.txt').open('w') as stream:
            pstats.Stats(profile,stream=stream).strip_dirs().sort_stats('cumulative').print_stats(45)
        result = dict(replay_seconds=elapsed,sequence='2 × (9 navigation clicks + 23 resizes)',
                      widget_count=len(QApplication.allWidgets()),solidworks_live=False)
        (destination/'replay.json').write_text(json.dumps(result,indent=2)+'\n')
        w.close()
    raise SystemExit(run(destination/'linux-smoke.json'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    audit(parser.parse_args().destination)
