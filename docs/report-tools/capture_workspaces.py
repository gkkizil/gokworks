"""Capture native workspaces and their geometry without a SolidWorks connection."""

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
from pdf.window import GokworksPdfApp
from k_factor.window import MANUAL_TAB, AUTOMATIC_TAB


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    folder = parser.parse_args().output_dir.resolve()
    images = folder/'screenshots'
    images.mkdir(parents=True, exist_ok=True)
    records, errors = [], []
    with TemporaryDirectory() as temporary:
        app = GokworksPdfApp(settings_path=Path(temporary)/'settings.json')
        app.report_callback_exception = lambda *args: errors.append(str(args))
        try:
            cases = [(mode, theme, '1240x860', '')
                     for mode in ('pdf', 'dxf_dwg', 'k_factor', 'iso_fits', 'geometric_tolerances')
                     for theme in ('Açık', 'Koyu')]
            cases += [('k_factor', theme, '1240x860', 'manual') for theme in ('Açık', 'Koyu')]
            cases += [('k_factor', theme, '1240x860', 'calibration') for theme in ('Açık', 'Koyu')]
            cases += [('iso_fits', 'Koyu', '1240x860', variant) for variant in ('manual-h6', 'manual-h8', 'manual-comparison')]
            cases += [('iso_fits', theme, '1240x860', 'shaft-basis') for theme in ('Açık', 'Koyu')]
            cases += [('k_factor', 'Koyu', '1000x690', 'manual'), ('dxf_dwg', 'Koyu', '1000x690', '')]
            for mode, theme, size, variant in cases:
                app._switch_mode(mode)
                app._change_theme(theme)
                app.geometry(size+'+40+40')
                if mode == 'k_factor':
                    app.k_state['method'].set('BA ölçümü' if variant == 'calibration' else 'Tablo')
                    app.k_state['radius'].set('2' if variant == 'calibration' else '')
                    app.k_state['ba'].set('4,08407044966673' if variant == 'calibration' else '')
                    app._select_k_assignment(MANUAL_TAB if variant == 'manual' else AUTOMATIC_TAB)
                    for key, value in [('manual_thickness', '2'), ('manual_k', '0,274'), ('manual_r', '2')]:
                        app.k_state[key].set(value)
                    app.settings_body._parent_canvas.yview_moveto(0)
                if mode == 'iso_fits':
                    manual = variant.startswith('manual')
                    app.iso_state['method'].set('Manuel kontrol' if manual else 'ISO seçimi')
                    app.iso_state['basis'].set('Mil esaslı' if variant == 'shaft-basis' else 'Tümü')
                    if variant == 'shaft-basis':
                        app.iso_state['hole'].set('K7'); app.iso_state['shaft'].set('h6')
                        app.update_idletasks()
                        app.iso_widgets['presets']._parent_canvas.yview_moveto(.4)
                    if not manual:
                        app.iso_widgets['details']._parent_canvas.yview_moveto(0)
                    if manual:
                        app._fill_manual_example()
                        if variant == 'manual-h8':
                            app.iso_state['hole_upper'].set('0,039')
                        app.iso_widgets['details']._parent_canvas.yview_moveto(1 if variant == 'manual-comparison' else .25)
                until = time.monotonic()+.6
                while time.monotonic() < until:
                    app.update(); time.sleep(.01)
                assert f'{app.winfo_width()}x{app.winfo_height()}' == size
                name = '-'.join(filter(None, (mode.replace('_', '-'), variant,
                            'light' if theme == 'Açık' else 'dark', 'small' if size == '1000x690' else '')))
                path = images/(name+'.png')
                x, y = app.winfo_rootx(), app.winfo_rooty()
                ImageGrab.grab(bbox=(x, y, x+app.winfo_width(), y+app.winfo_height())).save(path)
                record = dict(file=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                              mode=mode, theme=theme, size=size, variant=variant, native_tk_capture=True,
                              real_solidworks_executed=False)
                if mode in ('pdf', 'dxf_dwg', 'k_factor'):
                    record.update(table_height_px=app.table.winfo_height(), results_width_px=app.result_tabs.master.winfo_width(),
                                  form_width_px=app.form_panel.winfo_width())
                records.append(record)
        finally:
            app._on_close()
    assert not errors, errors
    (folder/'screenshots.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'{len(records)} native Tk screenshots saved.')


if __name__ == '__main__':
    main()
