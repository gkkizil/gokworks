"""Capture the real BOM window using synthetic components, without SolidWorks."""

import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

import customtkinter as ctk
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
from bom.exporter import collect
from gui.text import BOM_TREE_TAB
from pdf.window import GokworksPdfApp
from support.solidworks import FakeAssembly, FakeApp
from test_bom import Component


def settle(app, seconds=.35):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        app.update()
        time.sleep(.01)


def main():
    folder = ROOT/'docs/reports/bom/screenshots'
    folder.mkdir(parents=True, exist_ok=True)
    base = 'C:/Örnek/'
    part = Component(base+'P-002.sldprt', name='P-002-1')
    inner = Component(base+'ÖRNEK-M002.sldasm', name='ÖRNEK-M002-1', children=[
        Component(base+'P-010.sldprt', name='P-010-1')])
    result = collect(FakeApp(FakeAssembly(base+'ANA-MONTAJ.sldasm', children=[
        Component(base+'ÖRNEK-M001.sldasm', name='ÖRNEK-M001-1', children=[part, inner]),
        Component(base+'ÖRNEK-M001.sldasm', name='ÖRNEK-M001-2', children=[part, inner])])))
    records, errors = [], []
    with TemporaryDirectory() as temporary:
        app = GokworksPdfApp(settings_path=Path(temporary)/'settings.json')
        app.report_callback_exception = lambda *args: errors.append(str(args))
        try:
            app._switch_mode('bom')
            settle(app)
            app._bom_busy(True)
            app._start_bom_render(result)
            while app.busy:
                app.update()
                time.sleep(.01)
            cases = [(theme, view, '1240x860', 1, '')
                     for theme in ('Açık', 'Koyu') for view in ('parts', 'tree')]
            cases += [('Koyu', 'tree', '1000x690', 1, '-small'),
                      ('Koyu', 'tree', '1240x860', 1.25, '-125pct'),
                      ('Açık', 'parts', '1240x860', 1, '-empty')]
            for theme, view, size, scale, suffix in cases:
                app._change_theme(theme)
                ctk.set_widget_scaling(scale)
                app._set_scaled_min_max()  # Release CTk's temporary DPI resize lock.
                app.geometry(size+'+40+40')
                app.bom_widgets['tabs'].set('Parça listesi' if view == 'parts' else BOM_TREE_TAB)
                if suffix == '-empty':
                    app._clear_bom()
                    app._bom_busy(False)
                else:
                    identifier = 'part_0' if view == 'parts' else result.tree[0].number
                    app.bom_widgets[view].selection_set(identifier)
                    app._select_bom_row(view)
                app.status_label.configure(text='Örnek veri · SolidWorks montajı taranmadı.')
                settle(app)
                assert f'{app.winfo_width()}x{app.winfo_height()}' == size
                name = f'bom-{view}-{"light" if theme == "Açık" else "dark"}{suffix}.png'
                file = folder/name
                x, y = app.winfo_rootx(), app.winfo_rooty()
                ImageGrab.grab(bbox=(x, y, x+app.winfo_width(), y+app.winfo_height())).save(file)
                records.append(dict(file=str(file.relative_to(ROOT)),
                    sha256=hashlib.sha256(file.read_bytes()).hexdigest(), size=size, widget_scale=scale,
                    synthetic_data=True, real_tk_capture=True, native_solidworks_executed=False,
                    python=sys.version.split()[0], tk=app.tk.call('info', 'patchlevel'),
                    table_height_px=app.bom_widgets[view].winfo_height(),
                    inspector_visible=bool(app.bom_widgets['inspector'].winfo_viewable())))
        finally:
            ctk.set_widget_scaling(1)
            app._on_close()
    assert not errors, errors
    (folder.parent/'screenshots.json').write_text(json.dumps(records, indent=2)+'\n', encoding='utf-8')
    print(f'{len(records)} native BOM screenshots saved.')


if __name__ == '__main__':
    main()
