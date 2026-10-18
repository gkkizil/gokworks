import csv
import json
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import customtkinter as ctk
from support.gui import GuiTestCase

from gui.theme import INPUT
from iso_fits import rules
from iso_fits.window import SAMPLES, VIEWS, SECTION_HELP


class IsoRulesTests(unittest.TestCase):
    def test_known_h8_f7_limits_and_clearances(self):
        fit = rules.calculate(50)
        self.assertEqual((fit.hole.minimum_mm, fit.hole.maximum_mm),
                         (Decimal('50'), Decimal('50.039')))
        self.assertEqual((fit.shaft.minimum_mm, fit.shaft.maximum_mm),
                         (Decimal('49.950'), Decimal('49.975')))
        self.assertEqual((fit.minimum_clearance_nm, fit.maximum_clearance_nm), (25000, 89000))
        self.assertEqual(fit.kind, 'clearance')

    def test_classification_including_touching_and_diameter_dependent_presets(self):
        for shaft, bounds, kind in [('h6', (0, 41000), 'clearance'),
                                    ('k6', (-18000, 23000), 'transition'),
                                    ('p6', (-42000, -1000), 'interference')]:
            with self.subTest(shaft=shaft):
                fit = rules.calculate(50, 'H7', shaft)
                self.assertEqual((fit.minimum_clearance_nm, fit.maximum_clearance_nm), bounds)
                self.assertEqual(fit.kind, kind)
        fit = rules.calculate(50, 'H7', 'p6')
        self.assertEqual((fit.minimum_interference_nm, fit.maximum_interference_nm), (1000, 42000))
        self.assertEqual(rules.calculate(3, 'H7', 'p6').kind, 'transition')

    def test_comma_input_and_inclusive_upper_bound(self):
        self.assertEqual(rules.diameter('24,5'), Decimal('24.5'))
        for value, width in [('1', 14000), ('3', 14000), ('3.000000001', 18000),
                             ('50', 39000), ('50,000000001', 46000), ('400', 89000)]:
            with self.subTest(value=value):
                self.assertEqual(rules.limits(value, 'H8', 'hole').tolerance_nm, width)

    def test_invalid_input_and_case_are_rejected(self):
        for value in [True, '', 'NaN', 'inf', '1e2', '-1', '0', '.9', '400.000000001',
                      '500', '50 mm', '1,2.3', '50.0000000001']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                rules.calculate(value)
        for feature, code in [('hole', 'h7'), ('shaft', 'F7'), ('hole', 'Q7'),
                              ('hole', 'H18'), ('shaft', 'z9')]:
            with self.subTest(code=code), self.assertRaises(ValueError):
                rules.limits(50, code, feature)
        with self.assertRaises(ValueError):
            rules.classes('invalid')

    def test_half_micron_and_independent_table_values(self):
        self.assertEqual((rules.limits(10, 'JS7', 'hole').upper_nm,
                          rules.limits(10, 'js6', 'shaft').upper_nm), (7500, 4500))
        band = rules.limits(3, 'F8', 'hole')
        self.assertEqual((band.upper_nm, band.lower_nm, band.tolerance_nm), (20000, 6000, 14000))
        self.assertEqual(rules.limits(100, 'H7', 'hole').upper_nm, 35000)
        self.assertEqual(rules.limits(188, 'e8', 'shaft').lower_nm, -172000)

    def test_dataset_consistency_and_standard_it_widths(self):
        data = json.loads(Path(rules.__file__).with_name('tables.json').read_text())
        self.assertEqual((len(rules.classes('hole')), len(rules.classes('shaft'))), (11, 18))
        self.assertEqual(data['bounds_mm'], sorted(set(data['bounds_mm'])))
        for code, rows in data['classes'].items():
            with self.subTest(code=code):
                self.assertEqual(len(rows), 23)
                self.assertTrue(all(isinstance(v, int) for row in rows for v in row))
                self.assertTrue(all(upper > lower for upper, lower in rows))
        for nominal, widths in [(3, (6, 10, 14)), (50, (16, 25, 39)),
                                 (100, (22, 35, 54)), (400, (36, 57, 89))]:
            self.assertEqual(tuple(rules.limits(nominal, code, 'hole').tolerance_nm//1000
                                   for code in ('H6', 'H7', 'H8')), widths)

    def test_all_pairs_sample_endpoints_stay_inside_limits(self):
        for nominal in (1, 3, '3.001', 50, 400):
            for hole in rules.classes('hole'):
                for shaft in rules.classes('shaft'):
                    fit = rules.calculate(nominal, hole, shaft)
                    for sample in SAMPLES:
                        d, s = fit.sample(sample)
                        self.assertTrue(fit.hole.minimum_mm <= d <= fit.hole.maximum_mm)
                        self.assertTrue(fit.shaft.minimum_mm <= s <= fit.shaft.maximum_mm)
                        self.assertTrue(rules.mm(fit.minimum_clearance_nm) <= d-s <= rules.mm(fit.maximum_clearance_nm))
                    self.assertEqual(fit.sample(SAMPLES[0])[0]-fit.sample(SAMPLES[0])[1], rules.mm(fit.minimum_clearance_nm))
                    self.assertEqual(fit.sample(SAMPLES[2])[0]-fit.sample(SAMPLES[2])[1], rules.mm(fit.maximum_clearance_nm))
        with self.assertRaises(ValueError):
            rules.calculate(50).sample('unknown')

    def test_formats_keep_precision_and_units(self):
        self.assertEqual(rules.format_deviation(25000), '+0,025000 mm')
        self.assertEqual(rules.format_deviation(4500, 'µm'), '+4,5 µm')
        self.assertEqual(rules.format_mm(Decimal('50.000000001')), '50,000000001')
        self.assertEqual(rules.format_mm(Decimal('-0'), signed=True), '+0,000000')
        with self.assertRaises(ValueError):
            rules.format_deviation(1, 'inch')


class IsoGuiTests(GuiTestCase):
    def iso(self):
        self.app.nav_buttons['iso_fits'].invoke()
        self.settle()

    def test_minimal_selection_keeps_samples_filters_and_manual_panels(self):
        self.iso()
        widgets = self.app.iso_widgets
        self.assertFalse(widgets['basis'].winfo_viewable())
        self.assertTrue(widgets['view'].winfo_viewable())
        self.assertTrue(widgets['sample'].winfo_viewable())
        self.assertEqual(widgets['diagram'].grid_info()['row'], 0)
        widgets['filters'].invoke()
        self.assertTrue(widgets['basis'].winfo_manager())
        self.app.iso_state['basis'].set('Mil esaslı')
        visible = [p for p in rules.PRESETS if widgets['preset_buttons'][p.code].winfo_manager()]
        self.assertTrue(visible)
        self.assertTrue(all(p.basis == 'Mil esaslı' for p in visible))
        widgets['filters'].invoke()
        self.assertEqual(widgets['filters'].cget('text'), 'Filtreli')
        self.app.iso_state['method'].set('Manuel kontrol')
        self.assertEqual(widgets['diagram'].grid_info()['row'], 1)
        self.assertEqual(widgets['result_card'].grid_info()['row'], 0)
        for key in ('manual_inputs', 'comparison', 'assessment'):
            self.assertTrue(widgets[key].winfo_manager())
        self.assertEqual(widgets['section_help'].cget('text'), SECTION_HELP)

    def test_compact_iso_section_uses_exact_selected_sample_and_keeps_overall_kind(self):
        self.iso()
        self.app.iso_state['hole'].set('H7')
        self.app.iso_state['shaft'].set('k6')
        fit = self.app.iso_result
        canvas = self.app.iso_widgets['canvas']
        for sample, tag in ((SAMPLES[0], 'overlap'), (SAMPLES[2], 'clearance')):
            self.app.iso_state['sample'].set(sample)
            self.app.update()
            self.assertIs(self.app.iso_result, fit)
            self.assertEqual(len(canvas.find_withtag(tag)), 2)
            self.assertEqual(self.app.iso_widgets['kind'].cget('text'), 'Ara geçme')
            hole, shaft = fit.sample(sample)
            text = ' '.join(canvas.itemcget(item, 'text') for item in canvas.find_all()
                            if canvas.type(item) == 'text')
            self.assertIn(rules.format_mm(hole), text)
            self.assertIn(rules.format_mm(shaft), text)

    def test_default_and_every_preset(self):
        self.iso()
        self.assertEqual(self.app.iso_widgets['minimum'].cget('text'), '+0,025000 mm')
        self.assertEqual(self.app.iso_widgets['maximum'].cget('text'), '+0,089000 mm')
        for preset in rules.PRESETS:
            self.app.iso_widgets['preset_buttons'][preset.code].invoke()
            self.assertEqual((self.app.iso_result.hole.code, self.app.iso_result.shaft.code), (preset.hole, preset.shaft))

    def test_every_dropdown_item(self):
        self.iso()
        for key, values in [('hole', rules.classes('hole')), ('shaft', rules.classes('shaft')), ('unit', ('mm', 'µm'))]:
            for index, value in enumerate(values):
                self.app.iso_widgets[key]._dropdown_menu.invoke(index)
                self.app.update()
                self.assertEqual(self.app.iso_state[key].get(), value)
                self.assertIsNotNone(self.app.iso_result)

    def test_invalid_input_clears_values_and_disables_export(self):
        self.iso()
        self.app.iso_state['diameter'].set('0')
        self.assertIsNone(self.app.iso_result)
        self.assertEqual(self.app.iso_widgets['minimum'].cget('text'), '—')
        self.assertEqual(self.app.iso_widgets['export'].cget('state'), 'disabled')
        self.assertEqual(len(self.app.iso_widgets['canvas'].find_all()), 1)
        with patch('iso_fits.window.filedialog.asksaveasfilename') as dialog:
            self.app._save_iso_report()
            dialog.assert_not_called()
        self.app.iso_state['diameter'].set('50,000000001')
        self.assertEqual(self.app.iso_result.hole.tolerance_nm, 46000)

    def test_interference_and_transition_metrics(self):
        self.iso()
        self.app.iso_state['hole'].set('H7')
        for shaft, title, minimum, maximum in [('p6', 'MİNİMUM SIKILIK', '+0,001000 mm', '+0,042000 mm'),
                                                ('k6', 'MAKSİMUM SIKILIK', '+0,018000 mm', '+0,023000 mm')]:
            self.app.iso_state['shaft'].set(shaft)
            self.assertEqual(self.app.iso_widgets['minimum_title'].cget('text'), title)
            self.assertEqual(self.app.iso_widgets['minimum'].cget('text'), minimum)
            self.assertEqual(self.app.iso_widgets['maximum'].cget('text'), maximum)

    def test_both_views_and_three_sample_sizes(self):
        self.iso()
        coordinates = []
        for view in VIEWS:
            self.app.iso_state['view'].set(view)
            for sample in SAMPLES:
                self.app.iso_state['sample'].set(sample)
                self.app.update()
                canvas = self.app.iso_widgets['canvas']
                self.assertGreater(len(canvas.find_all()), 4)
                if view == VIEWS[0]:
                    rectangles = [item for item in canvas.find_all() if canvas.type(item) == 'rectangle']
                    coordinates.append(canvas.coords(rectangles[2]))
        self.assertNotEqual(coordinates[0], coordinates[2])

    def test_csv_clipboard_cancel_and_write_error(self):
        self.iso()
        target = self.root/'ISO.csv'
        with patch('iso_fits.window.filedialog.asksaveasfilename', return_value=str(target)):
            self.app.iso_widgets['export'].invoke()
        with target.open(encoding='utf-8-sig', newline='') as stream:
            rows = dict(list(csv.reader(stream, delimiter=';'))[1:])
        self.assertEqual(rows['Delik maksimum (mm)'], '50,039000')
        self.assertEqual(rows['Minimum delik − mil (mm)'], '+0,025000')
        self.app.iso_widgets['copy'].invoke()
        self.assertIn('Mil sınıfı: f7', self.app.clipboard_get())
        with patch('iso_fits.window.filedialog.asksaveasfilename', return_value=''), patch('iso_fits.window.open', create=True) as output:
            self.app._save_iso_report()
            output.assert_not_called()
        with patch('iso_fits.window.filedialog.asksaveasfilename', return_value=str(target)), patch('iso_fits.window.open', side_effect=OSError('disk dolu'), create=True):
            self.app._save_iso_report()
        self.assertIn('CSV kaydedilemedi', self.app.status_label.cget('text'))

    def test_navigation_theme_and_preferences_after_restart(self):
        self.iso()
        for key, value in [('diameter', '24,5'), ('hole', 'H7'), ('shaft', 'k6')]:
            self.app.iso_state[key].set(value)
        self.app._switch_mode('k_factor')
        self.app._change_theme('Koyu')
        self.app._switch_mode('iso_fits')
        self.assertEqual(self.app.iso_widgets['canvas'].cget('background'), INPUT[1])
        self.assertEqual(self.app.iso_state['diameter'].get(), '24,5')
        self.app._on_close()
        self.open_app()
        self.iso()
        self.assertEqual(self.app.iso_state['diameter'].get(), '24,5')
        self.assertEqual(self.app.iso_state['shaft'].get(), 'k6')

    def test_search_sources_dialog_and_catalog_link(self):
        self.iso()
        self.app.iso_search.set('H7/k6')
        visible = [code for code, button in self.app.iso_widgets['preset_buttons'].items() if button.winfo_manager()]
        self.assertEqual(visible, ['H7 / k6'])
        self.app.iso_widgets['sources'].invoke()
        self.settle()
        dialog = self.app.detail_window
        box = next(widget for widget in dialog.winfo_children() if isinstance(widget, ctk.CTkTextbox))
        self.assertIn('ISO 286-2:2010', box.get('1.0', 'end'))
        actions = [widget for widget in dialog.winfo_children() if isinstance(widget, ctk.CTkFrame)][0]
        catalog = next(widget for widget in actions.winfo_children() if isinstance(widget, ctk.CTkButton) and widget.cget('text') == 'ISO 286 kataloğu')
        with patch('iso_fits.window.webbrowser.open') as browser:
            catalog.invoke()
            self.assertIn('iso:286:-2:', browser.call_args.args[0])
        self.app._close_detail()
        self.assertIsNone(self.app.detail_window)

    def test_resolutions_themes_scaling_and_scroll_reachability(self):
        self.iso()
        try:
            for size, scale in [('1000x690', 1), ('1240x860', 1), ('1366x768', 1),
                                 ('1400x900', 1.25), ('1920x1080', 1.5)]:
                for theme in ('Açık', 'Koyu'):
                    with self.subTest(size=size, scale=scale, theme=theme):
                        ctk.set_widget_scaling(scale)
                        self.settle(1.05)
                        self.app.geometry(size)
                        self.app._change_theme(theme)
                        self.settle(.3)
                        self.assertEqual((self.app.winfo_width(), self.app.winfo_height()), tuple(map(int, size.split('x'))))
                        for key in ('diameter', 'hole', 'shaft', 'sources', 'export', 'canvas'):
                            widget = self.app.iso_widgets[key]
                            self.assertGreater(widget.winfo_width(), 20)
                            self.assertGreaterEqual(widget.winfo_rootx(), self.app.winfo_rootx())
                            self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(), self.app.winfo_rootx()+self.app.winfo_width())
                        details = self.app.iso_widgets['details']
                        details._parent_canvas.yview_moveto(1)
                        self.app.update()
                        button = self.app.iso_widgets['copy']
                        viewport = details._parent_canvas
                        self.assertGreaterEqual(button.winfo_rooty(), viewport.winfo_rooty())
                        self.assertLessEqual(button.winfo_rooty()+button.winfo_height(), viewport.winfo_rooty()+viewport.winfo_height())
        finally:
            ctk.set_widget_scaling(1)
