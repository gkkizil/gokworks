"""Capture the native bolt calculator with reproducible input cases."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

import customtkinter as ctk
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pdf.window import GokworksPdfApp


def main():
    output = ROOT/'docs/reports/bolt/screenshots'
    output.mkdir(parents=True, exist_ok=True)
    errors = []
    with TemporaryDirectory() as folder:
        app = GokworksPdfApp(settings_path=Path(folder)/'settings.json')
        app.report_callback_exception = lambda *args: errors.append(str(args))
        try:
            app._switch_mode('bolt')
            for name, theme, mode, tension, shear, unit, size in (
                ('tension-light', 'Açık', 'Çekme', '1000', '400', 'kg', '1240x860'),
                ('combined-dark', 'Koyu', 'Birleşik yük', '10000', '4000', 'N', '1240x860'),
                ('unsafe-dark-small', 'Koyu', 'Birleşik yük', '12', '8', 'kN', '1000x690')):
                app._change_theme(theme)
                app.geometry(size+'+20+20')
                app.bolt_state['unit'].set(unit)
                for key, value in dict(mode=mode, tension=tension, shear=shear).items():
                    app.bolt_state[key].set(value)
                deadline = time.monotonic()+.4
                while time.monotonic() < deadline:
                    app.update()
                    time.sleep(.01)
                x, y = app.winfo_rootx(), app.winfo_rooty()
                ImageGrab.grab(bbox=(x, y, x+app.winfo_width(), y+app.winfo_height())).save(output/(name+'.png'))
        finally:
            ctk.set_widget_scaling(1)
            app._on_close()
    assert not errors, errors
    print('3 native bolt calculator screenshots saved.')


if __name__ == '__main__':
    main()
