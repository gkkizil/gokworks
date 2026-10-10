import csv
import unittest
from decimal import Decimal
from unittest.mock import patch

from support.gui import GuiTestCase

from iso_fits.manual import (
    TARGETS,
    calculate_manual,
    closest_pair,
    closest_preset,
    compare_classes,
    compatibility,
    deviation_nm,
    usage_hint,
)
from iso_fits.rules import calculate, format_deviation, mm


class ManualIsoRulesTests(unittest.TestCase):
    def test_corrected_point_zero_five_example_and_targets(self):
        fit = calculate_manual(50, '-0,05', '0', '-0,1', '+0,1')
        self.assertEqual((fit.hole.minimum_mm, fit.hole.maximum_mm), (Decimal('49.95'), Decimal(50)))
        self.assertEqual((fit.shaft.minimum_mm, fit.shaft.maximum_mm), (Decimal('49.9'), Decimal('50.1')))
        self.assertEqual((fit.minimum_clearance_nm, fit.maximum_clearance_nm, fit.kind), (-150000, 100000, 'transition'))
        self.assertEqual(compatibility(fit).status, 'conditional')
        self.assertEqual(compatibility(fit, 'Serbest / kayar').status, 'incompatible')
        self.assertEqual(compatibility(fit, 'Ara / konumlandırma').status, 'compatible')
        self.assertEqual(compatibility(fit, 'Sıkı / pres').status, 'incompatible')
        self.assertEqual(deviation_nm('-0,05'), -50000)
        with self.assertRaises(ValueError):
            deviation_nm('-5%')

    def test_target_boundary_and_contact_cases_are_not_guarantees(self):
        strict_clearance = calculate(50, 'H7', 'g6')
        strict_interference = calculate(50, 'H7', 'p6')
        touching_clearance = calculate(50, 'H7', 'h6')
        touching_interference = calculate_manual(50, 0, '.025', '.025', '.041')
        self.assertEqual(compatibility(strict_clearance, 'Serbest / kayar').status, 'compatible')
        self.assertEqual(compatibility(touching_clearance, 'Serbest / kayar').status, 'boundary')
        self.assertEqual(compatibility(strict_interference, 'Sıkı / pres').status, 'compatible')
        self.assertEqual(compatibility(touching_interference, 'Sıkı / pres').status, 'boundary')
        self.assertEqual(compatibility(calculate_manual(50, 0, 0, 0, 0), 'Sıkı / pres').status, 'incompatible')
        self.assertEqual(compatibility(strict_clearance, 'Ara / konumlandırma').status, 'incompatible')
        self.assertEqual(compatibility(strict_interference).status, 'conditional')
        self.assertEqual(compatibility(strict_clearance).status, 'info')
        with self.assertRaises(ValueError):
            compatibility(strict_clearance, 'unrecognised target')

    def test_joint_iso_pair_and_common_preset_are_distinct(self):
        fit = calculate_manual(50, 0, '.02', '-.02', 0)
        pair, preset = closest_pair(fit), closest_preset(fit)
        self.assertEqual((pair.code, pair.distance_nm), ('H6/h6', 8000))
        self.assertEqual((preset.code, preset.distance_nm), ('H7/h6', 9000))
        self.assertFalse(pair.beyond_reference_width)
        self.assertEqual(pair.worst_limit_difference_nm, 4000)

    def test_reference_type_does_not_replace_actual_transition(self):
        fit = calculate_manual(50, '-.05', 0, '-.1', '.1')
        pair, preset = closest_pair(fit), closest_preset(fit)
        self.assertEqual(pair.code, 'N7/h9')
        self.assertEqual(pair.distance_nm, 163000)
        self.assertEqual(pair.fit.kind, 'transition')
        self.assertEqual(preset.code, 'N7/h6')
        self.assertEqual(preset.distance_nm, 209000)
        self.assertEqual(preset.fit.kind, 'transition')
        self.assertEqual(fit.kind, 'transition')

    def test_large_distance_to_iso_is_explicitly_flagged(self):
        pair = closest_pair(calculate_manual(50, '-.05', 0, '-.1', '.1'))
        self.assertTrue(pair.beyond_reference_width)
        exact = closest_pair(calculate(50, 'H7', 'k6'))
        self.assertFalse(exact.beyond_reference_width)
        self.assertEqual((exact.distance_nm, exact.worst_limit_difference_nm), (0, 0))

    def test_all_common_fits_keep_exact_reference_at_four_sizes(self):
        from iso_fits.rules import PRESETS
        for size in (1, 3, 50, 400):
            for preset in PRESETS:
                fit = calculate(size, preset.hole, preset.shaft)
                with self.subTest(size=size, preset=preset.code):
                    self.assertEqual(closest_pair(fit).distance_nm, 0)
                    self.assertEqual(closest_preset(fit).distance_nm, 0)
                    self.assertEqual(closest_preset(fit).fit.kind, fit.kind)

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
        for hole in ('F8', 'G7'):
            self.assertIn('yağlı', usage_hint(calculate(50, hole, 'h6')))
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


class ManualIsoGuiTests(GuiTestCase):
    def manual(self):
        self.app.nav_buttons['iso_fits'].invoke()
        self.app.iso_widgets['method']._buttons_dict['Manuel kontrol'].invoke()
        self.settle()

    def test_actual_example_button_and_every_target_menu(self):
        self.manual()
        self.app.iso_widgets['compatibility_example'].invoke()
        self.assertEqual(self.app.iso_result.kind, 'transition')
        self.assertEqual(self.app.iso_result.minimum_clearance_nm, -150000)
        self.assertIn('N7/h9', self.app.iso_widgets['explanation'].cget('text'))
        self.assertNotIn('H8/e8', self.app.iso_widgets['compatibility_text'].cget('text'))
        self.assertIn('eşit uzaklıktaki sınıflar', self.app.iso_widgets['compatibility_text'].cget('text'))
        self.assertIn('genişliğini aşıyor', self.app.iso_widgets['compatibility_text'].cget('text'))
        for index, target in enumerate(TARGETS):
            self.app.iso_widgets['target']._dropdown_menu.invoke(index)
            self.assertEqual(self.app.iso_state['target'].get(), target)
            self.assertEqual(self.app.iso_widgets['compatibility_title'].cget('text'), compatibility(self.app.iso_result, target).title)

    def test_compatibility_clears_on_invalid_input_and_hides_in_iso_mode(self):
        self.manual()
        self.app.iso_state['hole_lower'].set('wrong')
        for key in ('compatibility_title', 'compatibility_text'):
            self.assertEqual(self.app.iso_widgets[key].cget('text'), '—')
        self.app.iso_widgets['compatibility_example'].invoke()
        self.assertNotEqual(self.app.iso_widgets['compatibility_title'].cget('text'), '—')
        self.app.iso_widgets['method']._buttons_dict['ISO seçimi'].invoke()
        self.settle()
        self.assertFalse(self.app.iso_widgets['assessment'].winfo_viewable())

    def test_joint_report_includes_target_reference_and_actual_values(self):
        self.manual()
        self.app.iso_widgets['compatibility_example'].invoke()
        self.app.iso_state['target'].set('Serbest / kayar')
        self.app.iso_widgets['copy'].invoke()
        report = self.app.clipboard_get()
        self.assertIn('Serbest / kayar', report)
        self.assertIn('N7/h9', report)
        self.assertNotIn('H8/e8', report)
        self.assertIn('-0,150000', report)
        self.assertIn('uygun değil', report)

    def test_target_persistence_and_assessment_can_be_scrolled_into_view(self):
        self.manual()
        self.app.iso_state['target'].set('Sıkı / pres')
        self.app._on_close()
        self.open_app()
        self.app._switch_mode('iso_fits'); self.settle()
        self.assertEqual(self.app.iso_state['target'].get(), 'Sıkı / pres')
        self.app.geometry('1000x690'); self.settle(.3)
        details = self.app.iso_widgets['details']
        assessment = self.app.iso_widgets['assessment']
        details._parent_canvas.yview_moveto(max(0, assessment.winfo_y()-10)/details.winfo_height())
        self.app.update()
        viewport = details._parent_canvas
        self.assertGreaterEqual(assessment.winfo_rooty(), viewport.winfo_rooty())
        self.assertLessEqual(assessment.winfo_rooty()+assessment.winfo_height(), viewport.winfo_rooty()+viewport.winfo_height())

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
        self.open_app()
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
