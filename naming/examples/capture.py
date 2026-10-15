"""Capture the folder-based naming UI with clearly synthetic file records."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from naming.exporter import Document, Snapshot
from pdf.window import GokworksPdfApp


def main():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root/'DRM-MONTAJ'
        source.mkdir()
        definitions = {'DRM-ANA.SLDASM': ('DRM-ALT.SLDASM', 'TABAN.SLDPRT'),
                       'DRM-ALT.SLDASM': ('KAPAK.SLDPRT',), 'KAPAK.SLDPRT': (),
                       'TABAN.SLDPRT': (), 'KAPAK.SLDDRW': ('KAPAK.SLDPRT',)}
        for name in definitions:
            (source/name).write_text('Synthetic UI sample, not a SolidWorks document.')
        documents = tuple(Document(str(source/name), tuple(str(source/ref) for ref in refs), (0, 0))
                          for name, refs in definitions.items())
        app = GokworksPdfApp(settings_path=root/'settings.json', prepare_navigation=True)
        errors = []
        app.report_callback_exception = lambda *args: errors.append(str(args))
        try:
            app.geometry('1440x900+40+40')
            app._switch_mode('naming')
            app._change_theme('Koyu')
            app.naming_state['source_folder'].set(str(source))
            app._show_naming_sources((source/'DRM-ANA.SLDASM', source/'DRM-ALT.SLDASM'))
            app.naming_widgets['assembly'].set('DRM-ANA.SLDASM')
            app._select_naming_assembly('DRM-ANA.SLDASM')
            app.naming_state['destination'].set(str(root/'Yeni-montaj'))
            app.naming_state['mode'].set('Numaralı')
            app.naming_state['prefix'].set('DRM-TST-')
            app.naming_snapshot = Snapshot(str(source/'DRM-ANA.SLDASM'), documents,
                                           str(source/'DRM-ANA.SLDASM'), True)
            app._update_naming_preview()
            until = time.monotonic()+.4
            while time.monotonic() < until:
                app.update()
                time.sleep(.005)
            assert not errors, errors
            assert app.naming_widgets['save'].cget('state') == 'normal'
            x, y = app.winfo_rootx(), app.winfo_rooty()
            path = Path(__file__).with_name('naming-folders-dark.png')
            ImageGrab.grab(bbox=(x, y, x+app.winfo_width(), y+app.winfo_height())).save(path)
            print(path)
        finally:
            app._on_close()


if __name__ == '__main__':
    main()
