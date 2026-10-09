"""Gerçek Tk penceresinden ISO ekranlarını ve görüntü hashlerini kaydet."""

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
    folder = ROOT/'docs/reports/iso-fits'
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
        finally:
            app._on_close()
    if errors:
        raise RuntimeError(errors)
    (folder/'screenshots.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'{len(records)} gerçek pencere görüntüsü kaydedildi.')


if __name__ == '__main__':
    main()
