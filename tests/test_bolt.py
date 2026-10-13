"""Engineering examples, limits and units for the static bolt calculator."""

import math
import unittest

from bolt.rules import calculate


class BoltCalculationTests(unittest.TestCase):
    def test_m10_88_tension_matches_tabulated_area_and_hand_calculation(self):
        r = calculate(tension='10')
        self.assertAlmostEqual(r.tensile_area, 58.0, delta=.05)
        self.assertEqual(r.proof_stress, 580)
        self.assertEqual(r.allowable_stress, 290)
        self.assertAlmostEqual(r.tensile_stress, 172.4, delta=.1)
        self.assertAlmostEqual(r.tension_capacity_n, 16820, delta=15)
        self.assertTrue(r.safe)
        self.assertFalse(calculate(tension='20').safe)

    def test_shear_uses_thread_root_and_double_shear_shares_load(self):
        single = calculate(mode='Kesme', shear='10')
        double = calculate(mode='Kesme', shear='10', planes='Çift kesme')
        shank = calculate(mode='Kesme', shear='10', section='Dişsiz gövde')
        self.assertAlmostEqual(single.shear_area, 52.29, delta=.01)
        self.assertAlmostEqual(single.equivalent_stress, 331.3, delta=.1)
        self.assertFalse(single.safe)
        self.assertTrue(double.safe)
        self.assertAlmostEqual(double.shear_stress, single.shear_stress/2)
        self.assertAlmostEqual(double.shear_capacity_n, single.shear_capacity_n*2)
        self.assertAlmostEqual(shank.shear_area, math.pi*25)
        self.assertTrue(shank.safe)

    def test_combined_load_can_fail_when_each_load_passes_alone(self):
        self.assertTrue(calculate(tension='12').safe)
        self.assertTrue(calculate(mode='Kesme', shear='8').safe)
        combined = calculate(mode='Birleşik yük', tension='12', shear='8')
        self.assertFalse(combined.safe)
        self.assertAlmostEqual(combined.equivalent_stress, 336, delta=1)

    def test_counts_and_safety_factor_change_capacity_without_changing_material(self):
        one = calculate()
        two = calculate(count='2')
        strict = calculate(safety_factor='4')
        self.assertEqual(two.tensile_stress, one.tensile_stress/2)
        self.assertEqual(two.tension_capacity_n, one.tension_capacity_n*2)
        self.assertEqual(strict.tension_capacity_n, one.tension_capacity_n/2)
        self.assertFalse(strict.safe)

    def test_grade_and_diameter_boundary(self):
        self.assertEqual(calculate(metric='M16').proof_stress, 580)
        self.assertEqual(calculate(metric='M18').proof_stress, 600)
        self.assertEqual(calculate(grade='4.6').proof_stress, 225)
        self.assertEqual(calculate(grade='12.9').proof_stress, 970)
        self.assertAlmostEqual(calculate(metric='M12').tensile_area, 84.3, delta=.05)
        self.assertAlmostEqual(calculate(metric='M20').tensile_area, 245, delta=.3)

    def test_force_units_and_decimal_comma(self):
        self.assertAlmostEqual(calculate(tension='1,25').tension_n, 1250)
        self.assertEqual(calculate(tension='1250', unit='N').tension_n, 1250)
        self.assertAlmostEqual(calculate(tension='100', unit='kgf').tension_n, 980.665)

    def test_boundary_and_unloaded_state(self):
        r = calculate()
        for factor, safe in ((1-1e-8, True), (1+1e-8, False)):
            self.assertEqual(calculate(tension=r.tension_capacity_n*factor, unit='N').safe, safe)
        zero = calculate(tension='0')
        self.assertFalse(zero.loaded)
        self.assertIsNone(zero.available_factor)
        self.assertEqual(zero.utilization, 0)

    def test_invalid_active_inputs_rejected_and_inactive_load_ignored(self):
        for key, value in (('tension', ''), ('tension', 'nan'), ('tension', 'inf'), ('shear', '-1'),
                           ('count', '0'), ('count', '1.5'), ('safety_factor', '.5'),
                           ('metric', 'M11'), ('grade', 'A2-70'), ('unit', 'kg')):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                calculate(**{**dict(mode='Birleşik yük'), key: value})
        self.assertEqual(calculate(mode='Kesme', tension='invalid', shear='2').tension_n, 0)
        self.assertEqual(calculate(mode='Çekme', shear='invalid').shear_n, 0)
