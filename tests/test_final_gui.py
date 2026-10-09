"""Son GUI denetimi: tüm sayfalar, gerçek menü komutları ve DPI ölçeği."""

import os
import time
import unittest
from unittest.mock import patch

import customtkinter as ctk

import test_export_window as fixtures
from k_factor.window import AUTOMATIC_TAB, MANUAL_TAB
from gui import theme


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'GUI requires a display')
class FinalGUIAuditTests(unittest.TestCase):
    setUp = fixtures.WindowTests.setUp
    close_app = fixtures.WindowTests.close_app

    def settle(self):
        self.app.update()
        deadline = time.monotonic() + 3
        while self.app._layout_fit_id is not None and time.monotonic() < deadline:
            self.app.update()
            time.sleep(.005)
        self.assertIsNone(self.app._layout_fit_id, 'Layout did not converge')

    def assert_inside(self, child, parent):
        self.assertTrue(child.winfo_viewable())
        self.assertGreaterEqual(child.winfo_rootx(), parent.winfo_rootx())
        self.assertGreaterEqual(child.winfo_rooty(), parent.winfo_rooty())
        self.assertLessEqual(child.winfo_rootx()+child.winfo_width(),
                             parent.winfo_rootx()+parent.winfo_width()+1)
        self.assertLessEqual(child.winfo_rooty()+child.winfo_height(),
                             parent.winfo_rooty()+parent.winfo_height()+1)

    def test_all_pages_results_tabs_and_resolution_scale_matrix(self):
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        cases = [('1000x690', 1), ('1240x860', 1), ('1366x768', 1),
                 ('1600x900', 1), ('1920x1080', 1),
                 ('1400x900', 1.25), ('1920x1080', 1.5)]
        for size, scale in cases:
            if self.app.settings_body._get_widget_scaling() != scale:
                ctk.set_widget_scaling(scale)
                # CTk 6.0 locks the window size for 1000 ms during a DPI
                # transition. Wait for that documented source behavior before
                # requesting the next resolution, then verify the actual size.
                deadline = time.monotonic() + 1.05
                while time.monotonic() < deadline:
                    self.app.update()
                    time.sleep(.005)
            self.app.geometry(size+'+0+0')
            for appearance in ('Açık', 'Koyu'):
                self.app.theme_selector._buttons_dict[appearance].invoke()
                for mode, assignment in [('pdf', None), ('dxf_dwg', None),
                                         ('k_factor', AUTOMATIC_TAB), ('k_factor', MANUAL_TAB)]:
                    self.app.nav_buttons[mode].invoke()
                    if assignment:
                        self.app.k_widgets['assignment_tabs']._buttons_dict[assignment].invoke()
                    for result_tab in ('Dosyalar', 'Günlük'):
                        with self.subTest(size=size, scale=scale, theme=appearance,
                                          page=mode, assignment=assignment, result_tab=result_tab):
                            self.app.result_tabs._segmented_button._buttons_dict[result_tab].invoke()
                            self.settle()
                            self.assertEqual(f'{self.app.winfo_width()}x{self.app.winfo_height()}', size)
                            for child in (self.app.start_button, self.app.stop_button,
                                          self.app.theme_selector, self.app.progress, self.app.scan_button):
                                self.assert_inside(child, self.app)
                            self.assertEqual(tuple(self.app.start_button.cget('fg_color')), theme.ACCENT)
                            for button in self.app.nav_buttons.values():
                                self.assert_inside(button, self.app.sidebar)
                            if result_tab == 'Dosyalar':
                                self.assertGreater(self.app.table.winfo_height(), 80)
                                for child in (self.app.search_entry, self.app.filter_menu, self.app.table):
                                    self.assert_inside(child, self.app)
                            else:
                                self.assertGreater(self.app.log_box.winfo_height(), 80)
                                self.assert_inside(self.app.log_box, self.app)

    def test_every_dropdown_value_runs_its_real_menu_command(self):
        for appearance in ('Açık', 'Koyu'):
            self.app._change_theme(appearance)
            for mode in ('pdf', 'dxf_dwg', 'k_factor'):
                self.app.nav_buttons[mode].invoke()
                menus = [self.app.filter_menu]
                if mode == 'k_factor':
                    menus.extend(widget for widget in self.app.k_widgets.values()
                                 if isinstance(widget, (ctk.CTkOptionMenu, ctk.CTkComboBox)))
                for menu in menus:
                    for index, value in enumerate(menu.cget('values')):
                        with self.subTest(theme=appearance, page=mode, value=value):
                            menu._dropdown_menu.invoke(index)
                            self.app.update()
                            self.assertEqual(menu.get(), value)
                if mode == 'dxf_dwg':
                    selector = next(w for w in self.app.controls if isinstance(w, ctk.CTkSegmentedButton))
                    for value in ('DXF', 'DWG', 'DXF + DWG'):
                        selector._buttons_dict[value].invoke()
                        self.assertEqual(self.app.output_format.get(), value)

    def test_all_k_fields_can_be_scrolled_into_settings_viewport(self):
        self.app.geometry('1000x690')
        self.app.nav_buttons['k_factor'].invoke()
        for assignment in (AUTOMATIC_TAB, MANUAL_TAB):
            self.app.k_widgets['assignment_tabs']._buttons_dict[assignment].invoke()
            self.settle()
            canvas = self.app.settings_body._parent_canvas
            for key, field in self.app.k_widgets.items():
                if not isinstance(field, (ctk.CTkOptionMenu, ctk.CTkComboBox, ctk.CTkEntry)):
                    continue
                if key.startswith('manual_') != (assignment == MANUAL_TAB):
                    continue
                with self.subTest(assignment=assignment, field=key):
                    canvas.yview_moveto(0)
                    self.app.update()
                    field_y = field.winfo_rooty() - self.app.settings_body.winfo_rooty()
                    # Center the entry: Linux CTk uses 30 px scroll increments.
                    margin = (canvas.winfo_height()-field.winfo_height())/2
                    canvas.yview_moveto(max(0, field_y-margin)/self.app.settings_body.winfo_height())
                    self.app.update()
                    self.assert_inside(field, canvas)

    def test_readable_theme_contrast_and_green_primary_buttons(self):
        def luminance(color):
            rgb = [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]
            linear = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in rgb]
            return sum(a*b for a, b in zip(linear, (.2126, .7152, .0722)))
        for index, appearance in enumerate(('Açık', 'Koyu')):
            self.app._change_theme(appearance)
            for foreground, background in [(theme.TEXT[index], theme.PANEL[index]),
                                           (theme.MUTED[index], theme.PANEL[index]),
                                           (self.app.start_button.cget('text_color')[index], theme.ACCENT[index])]:
                with self.subTest(theme=appearance, foreground=foreground, background=background):
                    low, high = sorted((luminance(foreground), luminance(background)))
                    self.assertGreaterEqual((high+.05)/(low+.05), 4.5)

    def test_startup_fits_supported_monitor_sizes_and_window_dpi(self):
        self.app._on_close()
        self.addCleanup(lambda: ctk.set_window_scaling(1))
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        for screen, scale in [((1366, 768), 1), ((1920, 1080), 1.25), ((1920, 1080), 1.5)]:
            with self.subTest(screen=screen, scale=scale):
                ctk.set_widget_scaling(scale)
                ctk.set_window_scaling(scale)
                with patch.object(ctk.CTk, 'winfo_screenwidth', return_value=screen[0]), \
                     patch.object(ctk.CTk, 'winfo_screenheight', return_value=screen[1]):
                    self.app = fixtures.GokworksPdfApp(settings_path=self.settings)
                self.app.report_callback_exception = lambda *args: self.errors.append(args)
                self.settle()
                self.assertLessEqual(self.app.winfo_width(), screen[0])
                self.assertLessEqual(self.app.winfo_height()+32, screen[1])
                self.assertGreater(self.app.table.winfo_height(), 80)
                self.app._on_close()


if __name__ == '__main__':
    unittest.main()
