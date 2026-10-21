"""Engineering examples, limits and units for the static bolt calculator."""

import math
import unittest

from modules.bolt.rules import FINE_PITCHES, THREADS, calculate, pitch_choices


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

    def test_fine_pitch_matches_reference_stress_areas(self):
        # BAT's rounded fine-thread geometry: M10x1.25 As61.195; M10x1 As64.497.
        for pitch, area in (('1,25', 61.195), ('1,00', 64.497)):
            with self.subTest(pitch=pitch):
                r = calculate(thread_series='İnce diş', pitch=pitch)
                self.assertAlmostEqual(r.tensile_area, area, delta=.01)
                self.assertEqual(r.thread_series, 'İnce diş')
                self.assertEqual(r.pitch, float(pitch.replace(',', '.')))
        self.assertEqual(calculate(thread_series='İnce diş').pitch, 1.25)
        self.assertEqual(pitch_choices('M10'), (1.5,))
        self.assertEqual(pitch_choices('M10', 'İnce diş'), (1.25, 1., .75))

    def test_fine_pitch_changes_thread_capacity_and_required_count(self):
        coarse = calculate(grade='10.9', tension='25')
        fine = calculate(grade='10.9', tension='25', thread_series='İnce diş', pitch='1.25')
        self.assertFalse(coarse.safe)
        self.assertTrue(fine.safe)
        self.assertEqual(coarse.minimum_count, 2)
        self.assertEqual(fine.minimum_count, 1)
        self.assertGreater(fine.shear_capacity_n, coarse.shear_capacity_n)
        # Thread selection does not enlarge the unthreaded shank.
        shank = dict(grade='10.9', section='Dişsiz gövde', mode='Kesme', shear='10')
        self.assertEqual(calculate(**shank).shear_capacity_n,
                         calculate(**shank, thread_series='İnce diş', pitch='1').shear_capacity_n)

    def test_fine_pitch_combinations_and_invalid_selections(self):
        self.assertEqual(set(FINE_PITCHES), set(THREADS))
        for metric, pitches in FINE_PITCHES.items():
            for pitch in pitches:
                with self.subTest(metric=metric, pitch=pitch):
                    self.assertLess(pitch, THREADS[metric][1])
                    self.assertGreater(pitch, 0)
                    fine = calculate(metric=metric, thread_series='İnce diş', pitch=pitch)
                    self.assertGreater(fine.tensile_area, calculate(metric=metric).tensile_area)
        for options in (dict(thread_series='Yanlış'), dict(thread_series='İnce diş', pitch='1.5'),
                        dict(thread_series='İnce diş', pitch='0'),
                        dict(thread_series='İnce diş', pitch='nan'), dict(pitch='1.25')):
            with self.subTest(options=options), self.assertRaises(ValueError):
                calculate(**options)

    def test_force_units_and_decimal_comma(self):
        self.assertAlmostEqual(calculate(tension='1,25').tension_n, 1250)
        self.assertEqual(calculate(tension='1250', unit='N').tension_n, 1250)
        self.assertAlmostEqual(calculate(tension='100', unit='kgf').tension_n, 980.665)
        kg = calculate(mode='Birleşik yük', tension='100', shear='50', unit='kg')
        newton = calculate(mode='Birleşik yük', tension='980,665', shear='490,3325', unit='N')
        self.assertAlmostEqual(kg.tension_n, newton.tension_n)
        self.assertAlmostEqual(kg.shear_n, newton.shear_n)
        self.assertAlmostEqual(kg.utilization, newton.utilization)

    def test_boundary_and_unloaded_state(self):
        r = calculate()
        for factor, safe in ((1-1e-8, True), (1+1e-8, False)):
            self.assertEqual(calculate(tension=r.tension_capacity_n*factor, unit='N').safe, safe)
        zero = calculate(tension='0')
        self.assertFalse(zero.loaded)
        self.assertIsNone(zero.available_factor)
        self.assertEqual(zero.utilization, 0)

    def test_proportional_margin_and_combined_load_limits(self):
        reference = calculate(tension='0')
        # The normalized interaction is a 3-4-5 triangle: usage 0.5.
        r = calculate(mode='Birleşik yük', unit='N',
                      tension=.3*reference.tension_capacity_n,
                      shear=.4*reference.shear_capacity_n)
        self.assertAlmostEqual(r.tension_utilization, .3)
        self.assertAlmostEqual(r.shear_utilization, .4)
        self.assertAlmostEqual(r.utilization, .5)
        self.assertAlmostEqual(r.safety_margin, 1.)
        self.assertAlmostEqual(r.tension_limit_with_shear_n,
                               math.sqrt(.84)*reference.tension_capacity_n)
        self.assertAlmostEqual(r.shear_limit_with_tension_n,
                               math.sqrt(.91)*reference.shear_capacity_n)
        # These are TOTAL load limits with the other load held fixed.
        on_limit = calculate(mode='Birleşik yük', unit='N',
                             tension=r.tension_limit_with_shear_n, shear=r.shear_n)
        self.assertAlmostEqual(on_limit.utilization, 1.)
        above = calculate(mode='Birleşik yük', unit='N',
                          tension=r.tension_limit_with_shear_n*1.0001, shear=r.shear_n)
        self.assertFalse(above.safe)

    def test_minimum_count_passes_while_one_fewer_fails(self):
        for inputs in (dict(tension='20'), dict(mode='Kesme', shear='30'),
                       dict(mode='Birleşik yük', tension='12', shear='8'),
                       dict(mode='Birleşik yük', tension='70', shear='45', count='3',
                            planes='Çift kesme', section='Dişsiz gövde', safety_factor='3')):
            with self.subTest(inputs=inputs):
                r = calculate(**inputs)
                self.assertGreater(r.minimum_count, 1)
                self.assertTrue(calculate(**{**inputs, 'count': str(r.minimum_count)}).safe)
                self.assertFalse(calculate(**{**inputs, 'count': str(r.minimum_count-1)}).safe)

    def test_minimum_count_integer_boundary_and_ui_limit(self):
        limit = calculate(tension='0').tension_capacity_n
        for force in (math.nextafter(2*limit, 0), 2*limit,
                      math.nextafter(2*limit, math.inf), 2*limit*1.000001):
            r = calculate(tension=force, unit='N')
            self.assertEqual(r.minimum_count, 2 if calculate(tension=force, unit='N', count='2').safe else 3)
        large = calculate(tension=1000.5*limit, unit='N', count='1000')
        self.assertFalse(large.safe)
        self.assertEqual(large.minimum_count, 1001)

    def test_overloaded_companion_has_no_feasible_limit_and_zero_is_distinct(self):
        reference = calculate(tension='0')
        for mode, field, capacity, limit_field in (
                ('Birleşik yük', 'shear', reference.shear_capacity_n, 'tension_limit_with_shear_n'),
                ('Birleşik yük', 'tension', reference.tension_capacity_n, 'shear_limit_with_tension_n')):
            with self.subTest(field=field):
                r = calculate(**{**dict(mode=mode, unit='N', tension='0', shear='0'),
                                 field: capacity*1.1})
                self.assertIsNone(getattr(r, limit_field))
                self.assertLess(r.safety_margin, 0)
        self.assertIsNone(reference.minimum_count)
        self.assertIsNone(reference.safety_margin)
        self.assertEqual(reference.tension_limit_with_shear_n, reference.tension_capacity_n)
        self.assertEqual(reference.shear_limit_with_tension_n, reference.shear_capacity_n)

    def test_invalid_active_inputs_rejected_and_inactive_load_ignored(self):
        for key, value in (('tension', ''), ('tension', 'nan'), ('tension', 'inf'), ('shear', '-1'),
                           ('count', '0'), ('count', '1.5'), ('safety_factor', '.5'),
                           ('metric', 'M11'), ('grade', 'A2-70'), ('unit', 'lb')):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                calculate(**{**dict(mode='Birleşik yük'), key: value})
        self.assertEqual(calculate(mode='Kesme', tension='invalid', shear='2').tension_n, 0)
        self.assertEqual(calculate(mode='Çekme', shear='invalid').shear_n, 0)
