"""Capture the real desktop and profile the same navigation/resize sequence."""

import argparse
import cProfile
import json
from pathlib import Path
import pstats
import sys
from tempfile import TemporaryDirectory
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PIL import ImageGrab
from pdf.settings import save_settings
from pdf.window import GokworksPdfApp


def audit(destination):
    destination.mkdir(parents=True, exist_ok=True)
    errors, steps = [], []
    with TemporaryDirectory() as temporary:
        settings = Path(temporary) / 'settings.json'
        save_settings({'appearance': 'dark'}, settings)
        app = GokworksPdfApp(settings_path=settings, prepare_navigation=True)
        app.report_callback_exception = lambda *args: errors.append(str(args))

        def settle(seconds=.12):
            deadline = time.perf_counter() + seconds
            while time.perf_counter() < deadline:
                app.update()
                time.sleep(.002)

        def capture(name, description):
            settle()
            x, y = app.winfo_rootx(), app.winfo_rooty()
            width, height = app.winfo_width(), app.winfo_height()
            assert app.winfo_viewable() and width >= 1000 and height >= 690
            filename = name + '.png'
            ImageGrab.grab(bbox=(x, y, x+width, y+height)).save(destination / filename)
            steps.append({'screenshot': filename, 'description': description, 'mode': app.mode,
                          'window_title': app.title(), 'bounds': [x, y, width, height]})

        try:
            app.geometry('1240x860+0+0')
            capture('01-pdf', 'Normal açılış: PDF çalışma alanı')
            app.nav_buttons['iso_fits'].invoke()
            app.update()
            capture('02-iso', 'Menüden ISO geçmeleri: seçim ve kesit')
            app.nav_buttons['weight'].invoke()
            app.update()
            app.geometry('1000x690+0+0')
            capture('03-compact', 'Ağırlık hesabı: küçük penceredeki içerik')
            app.geometry('1440x900+0+0')
            capture('04-expanded', 'Ağırlık hesabı: yeniden büyütülen pencere')
            profile = cProfile.Profile()
            profile.enable()
            for _ in range(2):
                for mode in app._MODES:
                    app.nav_buttons[mode].invoke()
                    app.update()
                for width in range(1000, 1441, 20):
                    app.geometry(f'{width}x780')
                    app.update()
            profile.disable()
            with (destination / 'profile.txt').open('w') as stream:
                pstats.Stats(profile, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(45)
            assert not errors, errors
            result = {'steps': steps, 'errors': errors,
                      'environment': 'Linux/Xvfb, Python 3.13/Tk8.6; real desktop screenshot at Tk window bounds; no Windows/SolidWorks performance claim'}
            (destination / 'capture.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            app._on_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    audit(parser.parse_args().destination)
