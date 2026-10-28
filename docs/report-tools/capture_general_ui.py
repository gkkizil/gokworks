"""Capture the shared native shell; no live SolidWorks session is required."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtTest import QTest
from gui_qt.app import MainWindow, create_application


def capture(destination):
    destination.mkdir(parents=True, exist_ok=True)
    app = create_application([])
    shots = []
    with TemporaryDirectory(prefix='gokworks-shell-') as folder:
        window = MainWindow(Path(folder) / 'settings.json')
        window.show()
        cases = (
            ('dark', 'pdf', 'dark', (1440, 900)),
            ('light', 'weight', 'light', (1440, 900)),
            ('compact', 'pdf', 'dark', (820, 560)),
            ('search-empty', 'pdf', 'dark', (1024, 700)),
            ('filtered-results', 'pdf', 'dark', (1440, 900)),
            ('gear-gray', 'gear_calculator', 'dark', (1440, 900)),
        )
        for name, mode, theme, size in cases:
            window.browser.search.clear()
            window.set_theme(theme); window.resize(*size); window.navigate(mode)
            if name == 'search-empty':
                window.browser.search.setText('xyz')
            if name == 'filtered-results':
                # Names illustrate the list only; no source CAD files are read.
                window.pages['pdf'].results.files(['Ornek.SLDDRW'])
                window.pages['pdf'].results.search.setText('bulunamayan')
            QTest.qWait(180)
            assert window.size().toTuple() == size
            assert window.grab().save(str(destination / (name + '.png')))
            shots.append(dict(file=name+'.png', mode=mode, theme=theme, size=size))
        window.closing = True
        window.close(); window.deleteLater()
    (destination / 'capture.json').write_text(json.dumps(dict(
        platform=app.platformName(), framework='PySide6 / Qt Widgets',
        screenshots=shots, live_solidworks_tested=False, windows_exe_built=False,
        scope='Shared navigation, theme, toolbar, empty and filtered results',
    ), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    capture(parser.parse_args().destination)
