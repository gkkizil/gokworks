import csv
import json
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


from shared.theme import INPUT
from modules.iso_fits import rules
from modules.iso_fits.ui import SAMPLES, VIEWS, SECTION_HELP


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
