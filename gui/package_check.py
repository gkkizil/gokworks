"""Exercise packaged modules and all GUI pages without a SolidWorks session."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
import traceback


def _windows_icon_signatures(app):
    """Read native small/large icon pixels; Tk's ICO query returns no filename."""
    import ctypes
    import hashlib
    import win32gui

    get_bits = ctypes.windll.gdi32.GetBitmapBits
    get_bits.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p]
    get_bits.restype = ctypes.c_long
    hwnd = win32gui.GetParent(app.winfo_id())
    signatures = []
    for size in (0, 1):  # WM_GETICON: ICON_SMALL, ICON_BIG
        hicon = win32gui.SendMessage(hwnd, 0x007F, size, 0)
        assert hicon, f'Windows icon missing: size={size}'
        _, _, _, mask, color = win32gui.GetIconInfo(hicon)
        try:
            assert color, f'Windows color icon missing: size={size}'
            bitmap = win32gui.GetObject(color)
            length = bitmap.bmWidthBytes * bitmap.bmHeight
            pixels = ctypes.create_string_buffer(length)
            assert get_bits(int(color), length, pixels) == length, 'Cannot read Windows icon pixels'
            signatures.append((bitmap.bmWidth, bitmap.bmHeight, bitmap.bmBitsPixel,
                               hashlib.sha256(pixels.raw).hexdigest()))
        finally:
            for handle in (mask, color):
                if handle:
                    win32gui.DeleteObject(handle)
    return signatures


def run(output):
    report = Path(output)
    result = {'status': 'failed', 'platform': sys.platform, 'frozen': bool(getattr(sys, 'frozen', False))}
    app = None
    try:
        import pythoncom
        import pywintypes
        import win32com.client
        import ezdxf
        import openpyxl
        from bolt.rules import calculate
        from pdf.window import GokworksPdfApp
        with TemporaryDirectory() as directory:
            app = GokworksPdfApp(settings_path=Path(directory)/'settings.json', prepare_navigation=True)
            errors = []
            app.report_callback_exception = lambda *args: errors.append(str(args))
            app.update()
            icons = _windows_icon_signatures(app) if sys.platform == 'win32' else None
            # Resolve both theme variants from the frozen bundle and render each.
            for theme in ('Açık', 'Koyu', 'Açık', 'Koyu'):
                app._change_theme(theme)
                end = time.monotonic()+.05
                while time.monotonic() < end:
                    app.update()
                    time.sleep(.005)
                if sys.platform == 'win32':
                    assert _windows_icon_signatures(app) == icons, f'Windows icons changed after {theme} theme'
            assert app.brand_logo.cget('light_image').size == (1024, 364)
            assert app.brand_logo.cget('dark_image').size == (1024, 364)
            pages = app._MODES
            for mode in pages:
                app._switch_mode(mode)
                end = time.monotonic()+.15
                while time.monotonic() < end:
                    app.update()
                    time.sleep(.01)
            # Inputs update the live result only while their workspace is active.
            # The package-wide opening check may finish on an independent page.
            app._switch_mode('bolt')
            app.bolt_state['unit'].set('kg')
            app.bolt_state['tension'].set('100')
            assert abs(app.bolt_result.tension_n-980.665) < 1e-6
            assert not calculate(tension='20').safe
            assert calculate(tension='20', grade='12.9').safe
            app._switch_mode('weight')
            app.weight_state['kind'].set('Sac levha')
            app.weight_state['material'].set('Demir / Çelik')
            for key, value in dict(unit='mm', method='Ölçülerden',
                                   b='1000', t='10', length='2000', count='1').items():
                app.weight_state[key].set(value)
            assert abs(app.weight_result.total_mass_kg-157) < 1e-8
            workbook = openpyxl.Workbook()
            workbook.save(Path(directory)/'check.xlsx')
            ezdxf.new('R2010').saveas(Path(directory)/'check.dxf')
            assert not errors, errors
            result.update(status='passed', pages=list(pages), tk=app.tk.call('info', 'patchlevel'),
                          branding_themes=['light', 'dark'],
                          windows_icon_theme_check='passed' if icons else 'not_run',
                          solidworks_connection_tested=False)
            app._on_close()
            app = None
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        if app is not None:
            app._on_close()
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['status'] == 'passed' else 1
