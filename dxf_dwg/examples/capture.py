"""Capture the thickness-folder option from the native DXF/DWG workspace."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import customtkinter as ctk
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
            app._switch_mode('dxf_dwg')
            app._change_theme('Koyu')
            app.geometry('1240x860+20+20')
            app.group_by_thickness.set(True)
            checkbox = next(control for control in app.controls
                            if isinstance(control, ctk.CTkCheckBox)
                            and control.cget('text') == 'Sac kalınlığına göre klasörle')
            end = time.monotonic()+.35
            while time.monotonic() < end:
                app.update()
                time.sleep(.01)
            app.settings_body._parent_canvas.yview_moveto(1)
            app.update()
            assert checkbox.get()
            assert checkbox.winfo_viewable()
            assert checkbox.winfo_rooty()+checkbox.winfo_height() <= app.winfo_rooty()+app.winfo_height()
            x, y = app.winfo_rootx(), app.winfo_rooty()
            output = Path(__file__).with_name('thickness-folders-dark.png')
            ImageGrab.grab(bbox=(x, y, x+app.winfo_width(), y+app.winfo_height())).save(output)
            print(output)
        finally:
            app._on_close()
    assert not errors, errors


if __name__ == '__main__':
    main()
