"""Exercise packaged modules and all GUI pages without a SolidWorks session."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
import traceback


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
            app = GokworksPdfApp(settings_path=Path(directory)/'settings.json')
            errors = []
            app.report_callback_exception = lambda *args: errors.append(str(args))
            pages = app._MODES
            for mode in pages:
                app._switch_mode(mode)
                end = time.monotonic()+.15
                while time.monotonic() < end:
                    app.update()
                    time.sleep(.01)
            # Inputs update the live result only while their workspace is active.
            # Naming is now the last page in the package-wide opening check.
            app._switch_mode('bolt')
            app.bolt_state['unit'].set('kg')
            app.bolt_state['tension'].set('100')
            assert abs(app.bolt_result.tension_n-980.665) < 1e-6
            assert not calculate(tension='20').safe
            assert calculate(tension='20', grade='12.9').safe
            workbook = openpyxl.Workbook()
            workbook.save(Path(directory)/'check.xlsx')
            ezdxf.new('R2010').saveas(Path(directory)/'check.dxf')
            assert not errors, errors
            result.update(status='passed', pages=list(pages), tk=app.tk.call('info', 'patchlevel'),
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
