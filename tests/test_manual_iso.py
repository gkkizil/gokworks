import csv
import unittest
from decimal import Decimal
from unittest.mock import patch


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
