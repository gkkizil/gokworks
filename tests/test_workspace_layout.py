"""Native geometry checks for usable work areas independent of form scrolling."""

import os
import time
import unittest

import customtkinter as ctk

import test_export_window as fixtures
from k_factor.window import AUTOMATIC_TAB, MANUAL_TAB


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'GUI requires a display')
class WorkspaceLayoutTests(unittest.TestCase):
    setUp = fixtures.WindowTests.setUp
    close_app = fixtures.WindowTests.close_app

    def settle(self, seconds=.25):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            self.app.update()
            time.sleep(.005)

    def test_operation_work_areas_stay_large_when_scrolling_and_switching_forms(self):
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        for size, scale in [('1000x690', 1), ('1366x768', 1), ('1400x900', 1.25), ('1920x1080', 1.5)]:
            ctk.set_widget_scaling(scale)
            self.settle(1.05)
            self.app.geometry(size+'+0+0')
            for mode in ('pdf', 'dxf_dwg', 'k_factor'):
                self.app._switch_mode(mode)
                for appearance in ('Açık', 'Koyu'):
                    self.app._change_theme(appearance)
                    assignments = (AUTOMATIC_TAB, MANUAL_TAB) if mode == 'k_factor' else (None,)
                    for assignment in assignments:
                        if assignment:
                            self.app._select_k_assignment(assignment)
                        self.settle()
                        with self.subTest(size=size, scale=scale, mode=mode, theme=appearance, assignment=assignment):
                            self.assertEqual(f'{self.app.winfo_width()}x{self.app.winfo_height()}', size)
                            result = self.app.result_tabs.master
                            form = self.app.form_panel
                            self.assertGreaterEqual(result.winfo_rootx(), form.winfo_rootx()+form.winfo_width())
                            self.assertAlmostEqual(result.winfo_rooty(), form.winfo_rooty(), delta=1)
                            self.assertGreaterEqual(self.app.table.winfo_height(), 180*scale)
                            self.assertGreaterEqual(result.winfo_width(), 300*scale)
                            height = self.app.table.winfo_height()
                            for position in (0, 1):
                                self.app.settings_body._parent_canvas.yview_moveto(position)
                                self.settle(.04)
                                self.assertEqual(self.app.table.winfo_height(), height)
                            for control in (self.app.start_button, self.app.stop_button, self.app.search_entry,
                                            self.app.filter_menu, self.app.clear_filter_button, self.app.report_button):
                                self.assertGreaterEqual(control.winfo_rootx(), self.app.winfo_rootx())
                                self.assertLessEqual(control.winfo_rootx()+control.winfo_width(), self.app.winfo_rootx()+self.app.winfo_width()+1)

    def test_independent_reference_pages_keep_their_work_areas_after_operation_pages(self):
        for mode in ('k_factor', 'pdf', 'iso_fits', 'dxf_dwg', 'geometric_tolerances', 'k_factor', 'geometric_tolerances'):
            self.app._switch_mode(mode)
            self.settle()
            if mode in ('iso_fits', 'geometric_tolerances'):
                widgets = self.app.iso_widgets if mode == 'iso_fits' else self.app.gdt_widgets
                self.assertGreater(widgets['details']._parent_canvas.winfo_height(), 400)
                self.assertGreater(widgets['canvas'].winfo_width(), 400)
            else:
                self.assertGreater(self.app.table.winfo_height(), 300)


if __name__ == '__main__':
    unittest.main()
