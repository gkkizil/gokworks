import csv
from decimal import Decimal
import os
import unittest
from unittest.mock import patch

from iso_fits.manual import calculate_manual, compare_classes, deviation_nm, usage_hint
from iso_fits.rules import calculate, format_deviation, mm
import test_export_window as fixtures
import test_iso_fits as iso_tests


class ManualIsoRulesTests(unittest.TestCase):
    def test_user_unilateral_example_and_actual_dimensions(self):
        fit = calculate_manual('50', '0', '+0,02', '-0,02', '0')
        self.assertEqual((fit.hole.minimum_mm, fit.hole.maximum_mm), (Decimal(50), Decimal('50.02')))
        self.assertEqual((fit.shaft.minimum_mm, fit.shaft.maximum_mm), (Decimal('49.98'), Decimal(50)))
        self.assertEqual((fit.minimum_clearance_nm, fit.maximum_clearance_nm, fit.kind), (0, 40000, 'clearance'))
        self.assertIn('Kayar', usage_hint(fit))

    def test_bilateral_and_measured_point_have_different_results(self):
        bilateral = calculate_manual(50, '-.02', '.02', '-.02', '.02')
        self.assertEqual((bilateral.minimum_clearance_nm, bilateral.maximum_clearance_nm, bilateral.kind), (-40000, 40000, 'transition'))
        measured = calculate_manual(50, '.02', '.02', '-.02', '-.02')
        self.assertEqual((measured.minimum_clearance_nm, measured.maximum_clearance_nm), (40000, 40000))
        self.assertEqual(measured.sample('Orta değer'), (Decimal('50.02'), Decimal('49.98')))

    def test_known_tight_transition_sliding_and_oil_candidates(self):
        for shaft, kind, term in [('p6', 'interference', 'Sıkı'), ('k6', 'transition', 'Ara'),
                                  ('h6', 'clearance', 'Kayar'), ('g6', 'clearance', 'yağlı')]:
            with self.subTest(shaft=shaft):
                iso = calculate(50, 'H7', shaft)
                fit = calculate_manual(50, mm(iso.hole.lower_nm), mm(iso.hole.upper_nm),
                                       mm(iso.shaft.lower_nm), mm(iso.shaft.upper_nm))
                self.assertEqual(fit.kind, kind)
                self.assertIn(term, usage_hint(fit))
        self.assertIn('Bol', usage_hint(calculate(50, 'H11', 'c11')))
        self.assertIn('temas', usage_hint(calculate_manual(50, 0, 0, 0, 0)))

    def test_signed_input_and_nanometre_precision(self):
        for text, expected in [('+0,020', 20000), ('−0,02', -20000), (' .000001 ', 1), ('-0', 0)]:
            self.assertEqual(deviation_nm(text), expected)
        self.assertEqual(format_deviation(1, 'µm'), '+0,001 µm')
        self.assertEqual(format_deviation(-11, 'µm'), '-0,011 µm')

    def test_invalid_missing_nonfinite_or_rounded_input_is_rejected(self):
        for value in (True, '', 'NaN', 'inf', '1e-2', '+', '1,2.3', '.0000001', '-401', '401', '50 mm'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                deviation_nm(value)
        for inputs in [(50, '.03', '.02', 0, 0), (50, 0, 0, '.03', '.02'),
                       (50, -50, 0, 0, 0), (50, 0, 0, -51, 0), (401, 0, 0, 0, 0)]:
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                calculate_manual(*inputs)

    def test_nearest_class_is_distinct_from_exact_equality(self):
        fit = calculate_manual(50, 0, '.02', '-.02', 0)
        hole = compare_classes(fit.hole, 'hole')
        shaft = compare_classes(fit.shaft, 'shaft')
        self.assertFalse(any(item.exact for item in hole+shaft))
        self.assertEqual((hole[0].code, hole[0].lower_difference_nm, hole[0].upper_difference_nm), ('H6', 0, 4000))
        self.assertEqual((shaft[0].code, shaft[0].lower_difference_nm, shaft[0].upper_difference_nm), ('h6', -4000, 0))
        changed = calculate_manual(50, 0, '.020001', '-.02', 0)
        self.assertEqual(compare_classes(changed.hole, 'hole')[0].upper_difference_nm, 4001)
        with self.assertRaises(ValueError):
            compare_classes(fit.hole, 'unsupported')

    def test_every_supported_class_at_boundaries_matches_exactly(self):
        from iso_fits.rules import classes, limits
        for size in (1, 3, '3.000000001', 50, '50.000000001', 400):
            for feature in ('hole', 'shaft'):
                for code in classes(feature):
                    with self.subTest(size=size, feature=feature, code=code):
                        band = limits(size, code, feature)
                        from iso_fits.manual import manual_band
                        custom = manual_band(size, mm(band.lower_nm), mm(band.upper_nm), feature)
                        self.assertIn(code, [item.code for item in compare_classes(custom, feature) if item.exact])

    def test_half_micron_and_extreme_samples_are_preserved(self):
        fit = calculate_manual(10, '-.0075', '.0075', '-.0045', '.0045')
        self.assertEqual(compare_classes(fit.hole, 'hole')[0].code, 'JS7')
        self.assertTrue(compare_classes(fit.hole, 'hole')[0].exact)
        self.assertEqual((fit.minimum_clearance_nm, fit.maximum_clearance_nm), (-12000, 12000))
        for sample, difference in [('En az boşluk', '-.012'), ('En çok boşluk', '.012')]:
            hole, shaft = fit.sample(sample)
            self.assertEqual(hole-shaft, Decimal(difference))


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'GUI requires a display')
class ManualIsoGuiTests(unittest.TestCase):
    setUp = fixtures.WindowTests.setUp
    close_app = fixtures.WindowTests.close_app
    settle = iso_tests.IsoGuiTests.settle

    def manual(self):
        self.app.nav_buttons['iso_fits'].invoke()
        self.app.iso_widgets['method']._buttons_dict['Manuel kontrol'].invoke()
        self.settle()

    def test_real_method_button_and_example_results(self):
        self.manual()
        self.assertEqual(self.app.iso_widgets['minimum'].cget('text'), '+0,000000 mm')
        self.assertEqual(self.app.iso_widgets['maximum'].cget('text'), '+0,040000 mm')
        self.assertIn('Kayar', self.app.iso_widgets['explanation'].cget('text'))
        self.assertIn('Tam ISO eşleşmesi yok', self.app.iso_widgets['iso_comparison'].cget('text'))
        self.assertIn('H6', self.app.iso_widgets['iso_comparison'].cget('text'))
        self.assertFalse(self.app.iso_widgets['presets'].winfo_viewable())

    def test_live_inputs_units_exact_comparison_and_invalid_recovery(self):
        self.manual()
        self.app.iso_state['hole_upper'].set('+0,025')
        self.app.iso_state['shaft_lower'].set('-0,016')
        self.assertIn('Tam eşleşme: H7', self.app.iso_widgets['iso_comparison'].cget('text'))
        self.app.iso_widgets['manual_unit']._dropdown_menu.invoke(1)
        self.assertEqual(self.app.iso_widgets['maximum'].cget('text'), '+41,0 µm')
        self.app.iso_state['hole_lower'].set('.03')
        self.assertIsNone(self.app.iso_result)
        self.assertEqual(self.app.iso_widgets['iso_comparison'].cget('text'), '—')
        self.assertEqual(self.app.iso_widgets['copy'].cget('state'), 'disabled')
        self.app.iso_widgets['manual_example'].invoke()
        self.assertEqual(self.app.iso_result.maximum_clearance_nm, 40000)

    def test_iso_selection_manual_values_and_restart_remain_independent(self):
        self.manual()
        self.app.iso_state['hole_upper'].set('.03')
        self.app.iso_widgets['method']._buttons_dict['ISO seçimi'].invoke()
        self.assertEqual(self.app.iso_result.maximum_clearance_nm, 89000)
        self.assertFalse(self.app.iso_widgets['comparison'].winfo_manager())
        self.app.iso_state['shaft'].set('g6')
        self.app.iso_widgets['method']._buttons_dict['Manuel kontrol'].invoke()
        self.assertEqual(self.app.iso_result.maximum_clearance_nm, 50000)
        self.app._switch_mode('pdf')
        self.app._switch_mode('iso_fits')
        self.assertEqual(self.app.iso_state['method'].get(), 'Manuel kontrol')
        self.app._on_close()
        self.app = fixtures.GokworksPdfApp(settings_path=self.settings)
        self.app.report_callback_exception = lambda *args: self.errors.append(args)
        self.app._switch_mode('iso_fits')
        self.settle()
        self.assertEqual(self.app.iso_state['hole_upper'].get(), '.03')
        self.assertEqual(self.app.iso_state['shaft'].get(), 'g6')
        self.assertEqual(self.app.iso_state['method'].get(), 'Manuel kontrol')

    def test_manual_csv_and_clipboard_include_actual_values_and_match_scope(self):
        self.manual()
        path = self.root/'manual.csv'
        with patch('iso_fits.window.filedialog.asksaveasfilename', return_value=str(path)):
            self.app.iso_widgets['export'].invoke()
        with path.open(encoding='utf-8-sig', newline='') as stream:
            rows = dict(list(csv.reader(stream, delimiter=';'))[1:])
        self.assertEqual(rows['Hesap yöntemi'], 'Manuel kontrol')
        self.assertEqual(rows['Delik maksimum (mm)'], '50,020000')
        self.assertEqual(rows['Maksimum delik − mil (mm)'], '+0,040000')
        self.assertIn('Tam ISO eşleşmesi yok', rows['Delik ISO kontrolü'])
        self.assertIn('öneri', ' '.join(rows))
        self.app.iso_widgets['copy'].invoke()
        self.assertIn('Manuel kontrol', self.app.clipboard_get())

    def test_manual_focus_diagrams_and_both_themes(self):
        self.manual()
        for theme in ('Açık', 'Koyu'):
            self.app._change_theme(theme)
            self.app._focus_search()
            self.settle()
            self.assertEqual(self.app.focus_get(), self.app.iso_widgets['hole_upper']._entry)
            for view in ('Montaj kesiti', 'Tolerans bölgeleri'):
                self.app.iso_state['view'].set(view)
                self.assertGreater(len(self.app.iso_widgets['canvas'].find_all()), 4)

    def test_small_large_scaled_forms_and_comparison_are_reachable(self):
        import customtkinter as ctk
        self.manual()
        try:
            for size, scale in [('1000x690', 1), ('1400x900', 1.25), ('1920x1080', 1.5)]:
                for theme in ('Açık', 'Koyu'):
                    with self.subTest(size=size, scale=scale, theme=theme):
                        ctk.set_widget_scaling(scale); self.settle(1.05)
                        self.app.geometry(size); self.app._change_theme(theme); self.settle(.3)
                        self.assertEqual((self.app.winfo_width(), self.app.winfo_height()), tuple(map(int, size.split('x'))))
                        for key in ('hole_upper', 'hole_lower', 'shaft_upper', 'shaft_lower', 'method', 'diameter'):
                            widget = self.app.iso_widgets[key]
                            self.assertTrue(widget.winfo_viewable())
                            self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(), self.app.winfo_rootx()+self.app.winfo_width())
                        details = self.app.iso_widgets['details']._parent_canvas
                        details.yview_moveto(1); self.app.update()
                        comparison = self.app.iso_widgets['comparison']
                        self.assertGreaterEqual(comparison.winfo_rooty(), details.winfo_rooty())
                        self.assertLessEqual(comparison.winfo_rooty()+comparison.winfo_height(), details.winfo_rooty()+details.winfo_height())
        finally:
            ctk.set_widget_scaling(1)
