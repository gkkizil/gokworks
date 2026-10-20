"""Capture the actual Qt tooling helper; no SolidWorks session is contacted."""

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gui_qt.app import create_application, MainWindow


def main():
    app = create_application([])
    output = ROOT / 'docs/kr-tooling'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gokworks-tooling-capture-') as folder:
        window = MainWindow(Path(folder) / 'settings.json')
        window.resize(1680, 960)
        window.show()
        window.navigate('k_factor')
        page = window.pages['k_factor']
        page.tabs.setCurrentIndex(1)
        records = []
        for name, theme, size, values in (
            ('straight-single-v-dark', 'dark', (1680, 960),
             dict(punch_type='Düz bıçak', die_type='Tek V kalıp', punch='4',
                  punch_angle='67', die_angle='60', thickness='2', angle='90')),
            ('gooseneck-double-v-dark', 'dark', (1680, 960),
             dict(punch_type='Kaz boynu', die_type='Çift V kalıp', punch='1,5', die='24',
                  punch_angle='60', die_angle='60', thickness='3', angle='110', radius='4,5')),
            ('gooseneck-double-v-light', 'light', (1680, 960), {}),
            ('compact-dark', 'dark', (1024, 700), {}),
        ):
            window.set_theme(theme)
            window.resize(*size)
            for key, value in values.items():
                page.helper.set_value(key, value)
            page.calculate_helper()
            app.processEvents()
            assert page.helper_result is not None
            assert window.grab().save(str(output / (name + '.png')))
            records.append(dict(name=name, theme=theme, size=size, inputs=page.helper.values(),
                                result=vars(page.helper_result), compact=page.helper_workspace.compact))
        (output / 'captures.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        assert window.settings.flush()
        window.close()


if __name__ == '__main__':
    main()
