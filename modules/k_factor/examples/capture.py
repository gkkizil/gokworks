"""Capture example user-entered thickness/K/radius rows without SolidWorks."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from modules.pdf.window import GokworksPdfApp


def main():
    with TemporaryDirectory() as temporary:
        app = GokworksPdfApp(settings_path=Path(temporary)/'settings.json', prepare_navigation=True)
        errors = []
        app.report_callback_exception = lambda *args: errors.append(str(args))
        try:
            app.geometry('1440x940+30+30')
            app._change_theme('Koyu')
            app._switch_mode('k_factor')
            for key, value in dict(manual_thickness='1,5', manual_k='0,274', manual_r='1,5').items():
                app.k_state[key].set(value)
            app._add_assignment_row({'thickness': '2', 'k': '0,30', 'r': '2'})
            app._add_assignment_row({'thickness': '3', 'k': '0,32', 'r': '3'})
            until = time.monotonic()+.3
            while time.monotonic() < until:
                app.update()
                time.sleep(.005)
            assert not errors, errors
            assert len(app._manual_k_recipe()[1].rows) == 3
            x, y = app.winfo_rootx(), app.winfo_rooty()
            path = Path(__file__).with_name('thickness-assignments-dark.png')
            ImageGrab.grab(bbox=(x, y, x+app.winfo_width(), y+app.winfo_height())).save(path)
            print(path)
        finally:
            app._on_close()


if __name__ == '__main__':
    main()
