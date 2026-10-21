"""Geometrik tolerans ekranının gerçek Tk görüntülerini kaydet."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from modules.pdf.window import GokworksPdfApp
from modules.geometric_tolerances.catalog import CHARACTERISTICS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'docs/reports/geometric-tolerances')
    parser.add_argument('--dimension-audit', action='store_true')
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    images = folder/'screenshots'
    images.mkdir(parents=True, exist_ok=True)
    records, errors = [], []
    cases = [('gdt-dark', 'Koyu', 'cylindricity', '0,05', 'A', '', '1240x860', 0),
             ('gdt-light', 'Açık', 'cylindricity', '0,05', 'A', '', '1240x860', 0),
             ('gdt-position-dark', 'Koyu', 'position', '0,3', 'A | B | C', '', '1240x860', 0),
             ('gdt-total-runout-dark', 'Koyu', 'total_runout', '0,05', 'A', '', '1240x860', 0),
             ('gdt-measurement-dark', 'Koyu', 'flatness', '0,05', 'A', '0,050001', '1240x860', 1),
             ('gdt-small-dark', 'Koyu', 'circularity', '0,05', 'A', '', '1000x690', 0),
             ('gdt-legacy-dark', 'Koyu', 'concentricity', '0,05', 'A', '', '1240x860', 0)]
    if args.dimension_audit:
        cases += [('gdt-angularity-dark', 'Koyu', 'angularity', '0,05', 'A', '', '1240x860', 0),
                  ('gdt-profile-dark', 'Koyu', 'surface_profile', '0,05', 'A | B | C', '', '1240x860', 0),
                  ('gdt-long-frame-dark', 'Koyu', 'position', '999,999999', 'A | B | C', '', '1000x690', 0)]
    with TemporaryDirectory() as temp:
        app = GokworksPdfApp(settings_path=Path(temp)/'settings.json')
        app.report_callback_exception = lambda *args: errors.append(str(args))
        try:
            app._switch_mode('geometric_tolerances')
            for name, theme, kind, tolerance, datum, measured, size, scroll in cases:
                app.geometry(size+'+40+40')
                app._change_theme(theme)
                app._select_gdt(kind)
                for key, value in [('tolerance', tolerance), ('datum', datum), ('measured', measured)]:
                    app.gdt_state[key].set(value)
                if name == 'gdt-measurement-dark':
                    app.gdt_state['size_tolerance'].set('0,1')
                app.gdt_widgets['details']._parent_canvas.yview_moveto(scroll)
                if kind == 'total_runout':
                    app.gdt_widgets['listing']._parent_canvas.yview_moveto(1)
                deadline = time.monotonic()+.6
                while time.monotonic() < deadline:
                    app.update(); time.sleep(.01)
                assert (app.gdt_result is not None) == CHARACTERISTICS[kind].active
                assert f'{app.winfo_width()}x{app.winfo_height()}' == size
                x, y = app.winfo_rootx(), app.winfo_rooty()
                path = images/(name+'.png')
                ImageGrab.grab(bbox=(x, y, x+app.winfo_width(), y+app.winfo_height())).save(path)
                records.append({'file': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'theme': theme, 'size': [app.winfo_width(), app.winfo_height()], 'kind': kind,
                    'name': CHARACTERISTICS[kind].name, 'tolerance_mm': tolerance,
                    'datum': list(app.gdt_result.datums) if app.gdt_result is not None else [],
                    'asme_2018_active': CHARACTERISTICS[kind].active, 'standard': 'ASME Y14.5-2018',
                    'size_tolerance_mm': app.gdt_state['size_tolerance'].get(), 'measured_error_mm': measured,
                    'view': 'Ölçüm karşılaştırması' if scroll else 'Tolerans çerçevesi ve bölge',
                    'native_tk_capture': True, 'solidworks_required': False})
        finally:
            app._on_close()
    assert not errors, errors
    (folder/'screenshots.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n')
    print(f'{len(records)} gerçek Tk ekranı kaydedildi.')


if __name__ == '__main__':
    main()
