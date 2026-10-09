"""Gerçek Tk penceresinden ISO ekranlarını ve görüntü hashlerini kaydet."""

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'docs/reports/iso-fits')
    folder = parser.parse_args().output_dir.resolve()
    images = folder/'screenshots'
    images.mkdir(parents=True, exist_ok=True)
    records, errors = [], []
    with TemporaryDirectory() as temp:
        app = GokworksPdfApp(settings_path=Path(temp)/'settings.json')
        app.report_callback_exception = lambda *args: errors.append(str(args))
        try:
            app.geometry('1240x860+40+40')
            app._switch_mode('iso_fits')
            cases = [('iso-light', 'Açık', 'H8', 'f7', 'Montaj kesiti'),
                     ('iso-dark', 'Koyu', 'H8', 'f7', 'Montaj kesiti'),
                     ('iso-zones-dark', 'Koyu', 'H8', 'f7', 'Tolerans bölgeleri'),
                     ('iso-transition-dark', 'Koyu', 'H7', 'k6', 'Montaj kesiti'),
                     ('iso-interference-dark', 'Koyu', 'H7', 'p6', 'Montaj kesiti')]
            for name, theme, hole, shaft, view in cases:
                app._change_theme(theme)
                for key, value in [('hole', hole), ('shaft', shaft), ('view', view)]:
                    app.iso_state[key].set(value)
                app.iso_widgets['details']._parent_canvas.yview_moveto(0)
                deadline = time.monotonic()+.6
                while time.monotonic() < deadline:
                    app.update(); time.sleep(.01)
                x, y = app.winfo_rootx(), app.winfo_rooty()
                path = images/(name+'.png')
                ImageGrab.grab(bbox=(x, y, x+app.winfo_width(), y+app.winfo_height())).save(path)
                records.append({'file': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                'theme': theme, 'size': [app.winfo_width(), app.winfo_height()],
                                'nominal_mm': '50', 'hole': hole, 'shaft': shaft, 'view': view,
                                'native_tk_capture': True, 'solidworks_required': False})
            app.iso_state['method'].set('Manuel kontrol')
            app.iso_state['view'].set('Montaj kesiti')
            app._fill_manual_example()
            for name, theme, scroll in [('iso-manual-light', 'Açık', 0), ('iso-manual-dark', 'Koyu', 0),
                                        ('iso-manual-comparison-dark', 'Koyu', 1)]:
                app._change_theme(theme)
                app.iso_widgets['details']._parent_canvas.yview_moveto(scroll)
                deadline = time.monotonic()+.6
                while time.monotonic() < deadline:
                    app.update(); time.sleep(.01)
                x, y = app.winfo_rootx(), app.winfo_rooty()
                path = images/(name+'.png')
                ImageGrab.grab(bbox=(x, y, x+app.winfo_width(), y+app.winfo_height())).save(path)
                records.append({'file': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                'theme': theme, 'size': [app.winfo_width(), app.winfo_height()],
                                'nominal_mm': '50', 'hole': 'Manuel', 'shaft': 'Manuel', 'method': 'Manuel kontrol',
                                'hole_deviations_mm': ['0', '0.02'], 'shaft_deviations_mm': ['-0.02', '0'],
                                'view': 'ISO karşılaştırması' if scroll else 'Montaj kesiti',
                                'native_tk_capture': True, 'solidworks_required': False})
            app._fill_compatibility_example()
            app.iso_state['target'].set('Serbest / kayar')
            app.update()
            details = app.iso_widgets['details']
            details._parent_canvas.yview_moveto(max(0, app.iso_widgets['assessment'].winfo_y()-10)/details.winfo_height())
            deadline = time.monotonic()+.6
            while time.monotonic() < deadline:
                app.update(); time.sleep(.01)
            x, y = app.winfo_rootx(), app.winfo_rooty()
            path = images/'iso-compatibility-dark.png'
            ImageGrab.grab(bbox=(x, y, x+app.winfo_width(), y+app.winfo_height())).save(path)
            records.append({'file': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'theme': 'Koyu', 'size': [app.winfo_width(), app.winfo_height()], 'nominal_mm': '50',
                            'hole': 'Manuel', 'shaft': 'Manuel', 'method': 'Manuel kontrol',
                            'hole_deviations_mm': ['-0.05', '0'], 'shaft_deviations_mm': ['-0.1', '0.1'],
                            'target': 'Serbest / kayar', 'view': 'Montaj uyumu',
                            'native_tk_capture': True, 'solidworks_required': False})
        finally:
            app._on_close()
    if errors:
        raise RuntimeError(errors)
    (folder/'screenshots.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'{len(records)} gerçek pencere görüntüsü kaydedildi.')


if __name__ == '__main__':
    main()
