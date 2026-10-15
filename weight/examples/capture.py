"""Capture two reproducible native screens without changing user preferences."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab
from pdf.window import GokworksPdfApp


def main():
    errors = []
    with TemporaryDirectory() as folder:
        app = GokworksPdfApp(settings_path=Path(folder)/'settings.json')
        app.report_callback_exception = lambda *args: errors.append(str(args))
        try:
            if app._preload_id is not None:
                app.after_cancel(app._preload_id)
                app._preload_id = None
            app._switch_mode('weight')
            app.geometry('1240x860+20+20')
            for theme, name, values in (
                ('Koyu', 'weight-steel-dark', dict(kind='Kutu profil', material='S235JR',
                    b='100', h='100', t='5', length='2000', count='3')),
                ('Açık', 'weight-delrin-light', dict(kind='Mil', material='Delrin (POM-H)',
                    d='50', length='1000', count='2')),
            ):
                app._change_theme(theme)
                for key, value in values.items():
                    app.weight_state[key].set(value)
                app.weight_widgets['form']._parent_canvas.yview_moveto(0)
                app.weight_widgets['details']._parent_canvas.yview_moveto(0)
                end = time.monotonic()+.35
                while time.monotonic() < end:
                    app.update()
                    time.sleep(.01)
                assert app.weight_result is not None
                x, y = app.winfo_rootx(), app.winfo_rooty()
                ImageGrab.grab(bbox=(x, y, x+app.winfo_width(), y+app.winfo_height())).save(
                    Path(__file__).with_name(name+'.png'))
                print(name, app.weight_result.total_mass_kg, 'kg')
        finally:
            app._on_close()
    assert not errors, errors


if __name__ == '__main__':
    main()
