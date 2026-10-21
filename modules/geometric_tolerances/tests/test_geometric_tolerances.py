import csv
import unittest
from decimal import Decimal
from math import atan2, cos, degrees, hypot, radians
from unittest.mock import patch


from modules.geometric_tolerances.catalog import (
    ACTIVE,
    CATALOG,
    CHARACTERISTICS,
    GUIDE,
    MEASUREMENT_INPUTS,
)
from modules.geometric_tolerances.rules import DATUM_CHOICES, fmt, fmt_mm, specify
from shared.theme import INPUT
from shared.settings import load_settings, save_settings


class GeometricRulesTests(unittest.TestCase):
    def test_asme_mm_frame_keeps_leading_zero_and_exact_decimal_point(self):
        for raw, expected in [('0,000001', '0.000001'), ('0.050000', '0.05'),
                              ('1.000000', '1'), ('999.999999', '999.999999'), ('1000', '1000')]:
            with self.subTest(value=raw):
                spec = specify('position', '50', raw, 'A | B | C')
                self.assertEqual(fmt_mm(spec.tolerance), expected)
                self.assertEqual(spec.frame, f'Konum | ⌀{expected} | A | B | C')

    def test_position_independent_pythagorean_examples_use_diametral_error(self):
        # Exact 3-4-5 triangle; the GUI input is the evaluated diameter error.
        for dx, dy, t, expected in [('0.015', '0.020', '0.05', True),
                                    ('0.018', '0.024', '0.05', False),
                                    ('-0.018', '0.024', '0.06', True)]:
            with self.subTest(dx=dx, dy=dy, t=t):
                radial = (Decimal(dx)**2+Decimal(dy)**2).sqrt()
                spec = specify('position', '50', t, measured=str(2*radial))
                self.assertEqual(spec.accepted, expected)
                self.assertEqual(4*(Decimal(dx)**2+Decimal(dy)**2) <= Decimal(t)**2, expected)

    def test_centered_profile_uses_absolute_normal_deviation_not_peak_to_peak(self):
        for key in ('line_profile', 'surface_profile'):
            for deviations, equivalent, accepted in [
                (('0.01', '0.04'), '0.08', False),
                (('-0.025', '0.025'), '0.05', True),
                (('-0.025001', '0.001'), '0.050002', False)]:
                with self.subTest(key=key, deviations=deviations):
                    points = tuple(Decimal(point) for point in deviations)
                    total = 2*max(map(abs, points))
                    self.assertEqual(total, Decimal(equivalent))
                    spec = specify(key, '50', '0.05', measured=str(total))
                    self.assertEqual(spec.accepted, accepted)
                    self.assertEqual(all(abs(point) <= Decimal('0.025') for point in points), accepted)
        self.assertEqual(set(MEASUREMENT_INPUTS), {item.key for item in ACTIVE})

    def test_radial_form_width_and_runout_tir_are_not_doubled(self):
        for key in ('circularity', 'cylindricity', 'circular_runout', 'total_runout'):
            with self.subTest(key=key):
                # Evaluated bounding radii share an axis; radial width is 0.05.
                width = Decimal('25.025')-Decimal('24.975')
                self.assertEqual(width, Decimal('0.05'))
                self.assertTrue(specify(key, '50', '0.05', measured=str(width)).accepted)
                self.assertFalse(specify(key, '50', '0.05', measured='0.050001').accepted)

    def test_asme_2018_has_twelve_active_and_two_deleted_characteristics(self):
        self.assertEqual(len(ACTIVE), 12)
        self.assertEqual({item.key for item in CATALOG if not item.active}, {'concentricity', 'symmetry'})
        for key in ('concentricity', 'symmetry'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'ASME Y14.5-2018'):
                specify(key, '100', '0.05')
        self.assertTrue(all(item.reference for item in CATALOG))
        self.assertIn('Ek D', GUIDE)

    def test_surface_form_must_be_less_than_associated_size_tolerance(self):
        for key in ('straightness', 'flatness', 'circularity', 'cylindricity'):
            with self.subTest(key=key):
                spec = specify(key, '100', '0,05', size_tolerance='0,050001')
                self.assertEqual(spec.size_tolerance, Decimal('0.050001'))
                for size_t in ('0.05', '0.049999', '0', 'NaN'):
                    with self.subTest(size_t=size_t), self.assertRaises(ValueError):
                        specify(key, '100', '0.05', size_tolerance=size_t)
                self.assertIsNone(specify(key, '100', '0.05').size_tolerance)
        # Cached form input does not create a size relationship on profile/runout.
        self.assertIsNone(specify('surface_profile', '100', '0.05', size_tolerance='0.01').size_tolerance)

    def test_default_rfs_rmb_has_no_material_modifiers_and_position_example_requires_datum(self):
        spec = specify('position', '100', '0.05', 'A | B | C')
        self.assertEqual(spec.frame, 'Konum | ⌀0.05 | A | B | C')
        self.assertIn('unrelated AME', spec.characteristic.zone)
        with self.assertRaisesRegex(ValueError, 'datum referansı'):
            specify('position', '100', '0.05', 'Yok')
        self.assertIn('5.9.1', GUIDE)
        self.assertIn('5.9.2', GUIDE)
        self.assertIn('RFS ve RMB aynı kavram değildir', GUIDE)

    def test_total_width_is_not_plus_minus_or_a_general_grade(self):
        spec = specify('cylindricity', '100', '0,3')
        self.assertEqual(spec.tolerance, Decimal('0.3'))
        self.assertEqual(spec.frame, 'Silindiriklik | 0.3')
        self.assertNotIn('±', spec.frame)
        self.assertEqual(spec.datums, ())
        self.assertEqual(spec.tolerance, specify('cylindricity', '500', '0,3').tolerance)
        self.assertIn('f/m/c/v', GUIDE)
        self.assertIn('geometrik tolerans üretilmez', GUIDE)

    def test_cylindrical_position_region_is_diameter_not_radius(self):
        spec = specify('position', '50', '0,3', 'A | B | C')
        self.assertEqual(spec.frame, 'Konum | ⌀0.3 | A | B | C')
        self.assertEqual(spec.tolerance/2, Decimal('0.15'))
        self.assertEqual(spec.datums, ('A', 'B', 'C'))
        self.assertIn('t/2', spec.characteristic.zone)

    def test_form_ignores_cached_datums_optional_and_required_are_distinct(self):
        for item in CATALOG:
            with self.subTest(kind=item.key):
                if not item.active:
                    with self.assertRaisesRegex(ValueError, 'kaldırıldı'):
                        specify(item.key, '100', '0.05')
                    continue
                for datum in DATUM_CHOICES:
                    if datum == 'Yok' and item.datum == 'required':
                        with self.assertRaisesRegex(ValueError, 'datum referansı'):
                            specify(item.key, '100', '0.05', datum)
                    else:
                        spec = specify(item.key, '100', '0.05', datum)
                        expected = () if item.datum == 'none' or datum == 'Yok' else tuple(datum.split(' | '))
                        self.assertEqual(spec.datums, expected)
        for datum in ('A | A', 'B | A', 'A||B', 'Z', None):
            with self.subTest(datum=datum), self.assertRaises(ValueError):
                specify('parallelism', '100', '0.05', datum)

    def test_error_comparison_equal_and_one_nanometre_above_limit(self):
        for measured, expected, margin in [('0', True, '0.05'), ('0.049999', True, '0.000001'),
                                           ('0.050000', True, '0'), ('0.050001', False, '-0.000001')]:
            with self.subTest(measured=measured):
                spec = specify('flatness', '100', '0.05', measured=measured)
                self.assertIs(spec.accepted, expected)
                self.assertEqual(spec.margin, Decimal(margin))
        absent = specify('flatness', '100', '0.05')
        self.assertIsNone(absent.accepted)
        self.assertIsNone(absent.margin)

    def test_invalid_inputs_do_not_create_a_specification(self):
        for key in ('size', 'tolerance', 'measured'):
            for value in ('', '-0.01', 'NaN', 'Infinity', '1e-2', '0.0000001', '0,0.5', True, '10001'):
                if key == 'measured' and value == '':
                    continue
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    args = dict(key='position', size='50', tolerance='0.05', measured='')
                    args[key] = value
                    specify(**args)
        for key in ('size', 'tolerance'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                args = dict(key='flatness', size='100', tolerance='0.05')
                args[key] = '0'
                specify(**args)
        for key in ('bad', None):
            with self.assertRaises(ValueError):
                specify(key, '100', '.05')

    def test_limits_and_decimal_display_have_no_implicit_rounding(self):
        spec = specify('circularity', '0.000001', '+0,000001', measured='0.000001')
        self.assertEqual(fmt(spec.tolerance), '0,000001')
        self.assertEqual(fmt(Decimal('-0.000001')), '-0,000001')
        self.assertEqual(fmt(specify('flatness', '10000', '1000').size), '10000')
        with self.assertRaises(ValueError):
            specify('flatness', '10000.000001', '0.05')
        with self.assertRaises(ValueError):
            specify('flatness', '100', '1000.000001')

    def test_catalog_distinguishes_form_runout_and_theoretical_dimensions(self):
        self.assertEqual(len(CATALOG), 14)
        self.assertEqual(len(CHARACTERISTICS), 14)
        self.assertEqual({i.key for i in CATALOG if i.datum == 'none'},
                         {'straightness', 'flatness', 'circularity', 'cylindricity'})
        self.assertIn('radyal mesafe', CHARACTERISTICS['cylindricity'].zone)
        self.assertIn('basit toplamı değildir', CHARACTERISTICS['cylindricity'].note)
        self.assertIn('Kesitler ayrı', CHARACTERISTICS['circular_runout'].zone)
        self.assertIn('bağımsız sıfırlanmaz', CHARACTERISTICS['total_runout'].zone)
        self.assertIn('teorik 45°', CHARACTERISTICS['angularity'].zone)
        self.assertIn('Rule #1', GUIDE)
        self.assertIn('Rule #2', GUIDE)
        self.assertIn("CAD'e yazılmaz", GUIDE)
        for item in CATALOG:
            with self.subTest(kind=item.key):
                self.assertTrue(all((item.description, item.zone, item.measurement, item.note, item.example)))




if __name__ == '__main__':
    unittest.main()
