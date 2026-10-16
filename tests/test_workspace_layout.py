"""Native geometry checks for usable work areas independent of form scrolling."""

import unittest
from collections import Counter
import time
import tkinter as tk
from unittest.mock import patch

import customtkinter as ctk
from support.gui import GuiTestCase

from k_factor.window import AUTOMATIC_TAB, MANUAL_TAB, RESULTS_TAB
from gui.window_geometry import window_sizes


class WindowBoundsTests(unittest.TestCase):
    def test_default_and_minimum_sizes_fit_available_screen_at_display_dpi(self):
        for width, height, scale in ((1920, 1040, 1), (1366, 728, 1.25), (1920, 1040, 1.5), (2560, 1400, 2)):
            with self.subTest(width=width, height=height, scale=scale):
                initial, minimum = window_sizes(width, height, scale)
                self.assertLessEqual(minimum[0], initial[0])
                self.assertLessEqual(minimum[1], initial[1])
                self.assertLessEqual((initial[0]+24)*scale, width)
                self.assertLessEqual((initial[1]+48)*scale, height)
        self.assertEqual(window_sizes(1920, 1040, 1), ((1240, 860), (1000, 690)))


class WorkspaceLayoutTests(GuiTestCase):
    def test_only_active_page_resizes_without_unmapping_cached_native_surfaces(self):
        from gui.startup import prepare_pages
        prepare_pages(self.app)
        self.wait_layout()
        counts, unmapped = Counter(), []
        for mode, page in self.app._pages.items():
            owner = page['workspace']
            self.assertIs(owner.master, self.app.viewport)
            tk.Misc.bind(owner, '<Configure>', lambda event, key=mode, widget=owner:
                         counts.update([key]) if event.widget is widget else None, add='+')
            tk.Misc.bind(owner, '<Unmap>', lambda event, key=mode, widget=owner:
                         unmapped.append(key) if event.widget is widget else None, add='+')
        self.app._switch_mode('weight')
        self.wait_layout()
        self.assertEqual(unmapped, [])
        parked = {mode: (page['workspace'].winfo_width(), page['workspace'].winfo_height())
                  for mode, page in self.app._pages.items() if mode != 'weight'}
        counts.clear()
        for size in ('1000x690', '1440x900', '1100x740'):
            self.app.geometry(size)
            self.wait_layout()
            self.assertEqual((self.app.workspace.winfo_width(), self.app.workspace.winfo_height()),
                             (self.app.viewport.winfo_width(), self.app.viewport.winfo_height()))
        self.assertGreater(counts['weight'], 0)
        self.assertEqual(set(counts), {'weight'})
        self.assertEqual(unmapped, [])
        for mode, size in parked.items():
            owner = self.app._pages[mode]['workspace']
            self.assertEqual((owner.winfo_width(), owner.winfo_height()), size)
            self.assertTrue(owner.winfo_viewable())
        self.app._switch_mode('pdf')
        self.wait_layout()
        self.assertEqual(self.app.workspace.winfo_width(), self.app.viewport.winfo_width())
        self.assertEqual(unmapped, [])

    def test_layout_follows_continuous_resize_before_drag_ends(self):
        self.wait_layout()
        applied = []
        fit = self.app._fit_pdf_settings

        def record_fit():
            applied.append(self.app.workspace.winfo_width())
            fit()

        with patch.object(self.app, '_fit_pdf_settings', side_effect=record_fit):
            for width in range(1020, 1321, 20):
                self.app.geometry(f'{width}x740')
                self.app.update()
                # More frequent events than the old 35 ms trailing debounce.
                until = time.monotonic()+.008
                while time.monotonic() < until:
                    self.app.update()
                    time.sleep(.001)
            self.assertGreaterEqual(len(set(applied)), 2)
            self.wait_layout()
        self.assertAlmostEqual(self.app.form_panel.cget('width'),
                               max(288, min(350, (self.app.workspace.winfo_width()-60)*.35)), delta=1)

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
                            if mode == 'k_factor':
                                self.assertTrue(form.winfo_viewable())
                                self.assertFalse(result.winfo_viewable())
                                self.assertGreater(form.winfo_width(), 600*scale)
                                selector = self.app.k_widgets['assignment_tabs']
                                self.assertTrue(selector.winfo_viewable())
                                # The current three-way K/R selector is 42
                                # logical pixels, including before this change.
                                self.assertGreaterEqual(selector.winfo_height(), round(42*scale))
                                if assignment == MANUAL_TAB:
                                    for key in ('manual_thickness', 'manual_k', 'manual_r'):
                                        field = self.app.k_widgets[key]
                                        self.assertTrue(field.winfo_viewable())
                                        self.assertGreaterEqual(field.winfo_height(), round(42*scale))
                                self.app._select_k_view(RESULTS_TAB)
                                self.settle(.04)
                                self.assertFalse(form.winfo_viewable())
                                self.assertTrue(result.winfo_viewable())
                                self.assertEqual(result.winfo_width(), form.winfo_width())
                            else:
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
                if mode == 'k_factor':
                    self.app._select_k_view(RESULTS_TAB)
                    self.settle()
                self.assertGreater(self.app.table.winfo_height(), 300)


if __name__ == '__main__':
    unittest.main()
