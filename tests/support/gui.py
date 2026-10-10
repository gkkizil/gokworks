"""Real Tk fixture and event pumping shared by all GUI test modules."""

import gc
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pdf.settings import save_settings
from pdf.window import GokworksPdfApp


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'),
                     'GUI requires a display (use DISPLAY=:99 on cloud)')
class GuiTestCase(unittest.TestCase):
    settle_seconds = .25

    def setUp(self):
        # Retired Tk fonts must be collected on the GUI thread, before a new
        # export worker can trigger cyclic GC (notably on Python 3.13/Tk 8.6).
        gc.collect()
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = self.root/'settings.json'
        save_settings({'unrelated_setting': 'keep'}, self.settings)
        self.errors = []
        self.open_app()
        self.addCleanup(self.close_app)

    def open_app(self):
        self.app = GokworksPdfApp(settings_path=self.settings)
        self.app.report_callback_exception = lambda *args: self.errors.append(args)
        self.app.update()

    def close_app(self):
        if not self.app._closed:
            self.app._on_close()
        self.assertFalse(self.errors)

    def pump_until(self, predicate, timeout=5, message='GUI condition did not complete'):
        deadline = time.monotonic()+timeout
        while not predicate() and time.monotonic() < deadline:
            self.app.update()
            time.sleep(.005)
        self.app.update()
        self.assertTrue(predicate(), message)

    def wait_idle(self):
        self.pump_until(lambda: not self.app.busy, message='worker did not complete')

    def wait_layout(self, timeout=2):
        self.app.update()
        self.pump_until(lambda: self.app._layout_fit_id is None, timeout,
                        'Layout did not converge')

    def settle(self, seconds=None):
        deadline = time.monotonic()+(self.settle_seconds if seconds is None else seconds)
        while time.monotonic() < deadline:
            self.app.update()
            time.sleep(.005)
        self.app.update()

    def assert_inside(self, child, parent=None, *, left=0, right=1, mapped=False):
        parent = self.app if parent is None else parent
        self.assertTrue(child.winfo_ismapped() if mapped else child.winfo_viewable())
        for coordinate, extent in (('winfo_rootx', 'winfo_width'), ('winfo_rooty', 'winfo_height')):
            start, bound = getattr(child, coordinate)(), getattr(parent, coordinate)()
            self.assertGreaterEqual(start, bound-left)
            self.assertLessEqual(start+getattr(child, extent)(), bound+getattr(parent, extent)()+right)


class LayoutGuiTestCase(GuiTestCase):
    layout_timeout = 2

    def settle(self):
        self.wait_layout(self.layout_timeout)
