"""Hand-calculated areas, SI units, active input isolation and invalid sections."""

import math
import unittest

from weight import rules


class WeightTests(unittest.TestCase):
    def test_sheet_one_piece_and_total_are_distinct(self):
        result = rules.calculate(kind='Sac levha', b=1000, t=2, length=2000, count=3)
        self.assertEqual(result.area_mm2, 2000)
        self.assertAlmostEqual(result.volume_m3, .004)
        self.assertAlmostEqual(result.mass_kg, 31.4)
        self.assertAlmostEqual(result.total_volume_m3, .012)
        self.assertAlmostEqual(result.total_mass_kg, 94.2)
        self.assertAlmostEqual(result.kg_per_m, 15.7)
        self.assertEqual(result.piece_text, '31,4 kg')
        self.assertEqual(result.total_text, '94,2 kg')
        self.assertFalse(result.approximate)

    def test_mm_cm_and_m_produce_the_same_physical_piece(self):
        results = [rules.calculate(b=100, t=5, length=1000, unit='mm'),
                   rules.calculate(b=10, t=.5, length=100, unit='cm'),
                   rules.calculate(b=.1, t=.005, length=1, unit='m')]
        for result in results:
            self.assertAlmostEqual(result.mass_kg, 3.925)
            self.assertEqual(result.dimensions_mm, {'b': 100, 't': 5})
            self.assertEqual(result.length_mm, 1000)

    def test_every_shape_matches_an_independent_hand_area(self):
        expected = {'Kutu profil': 1700, 'Sac levha': 500, 'Boru': 225 * math.pi,
                    'Köşebent': 875, 'Kare demir': 10000, 'T profil': 896,
                    'U profil': 1472, 'HEA': 1472, 'HP': 1472, 'HD': 1472,
                    'HL': 1472, 'IPN': 1472, 'UPE': 1472, 'HE': 1472,
                    'IPE': 1472, 'UPN': 1472, 'Altıköşe': 450 * math.sqrt(3),
                    'Mil': 625 * math.pi, 'Silme lama': 500}
        self.assertEqual(set(expected), set(rules.KINDS))
        for kind, area in expected.items():
            with self.subTest(kind=kind):
                result = rules.calculate(kind=kind, b=100, h=80, t=5, tw=4, tf=6, d=50, s=30)
                self.assertAlmostEqual(result.area_mm2, area)
                self.assertAlmostEqual(result.mass_kg, area * .00785)

    def test_material_and_custom_density_change_mass_without_changing_geometry(self):
        for material, expected in (('Demir / Çelik', 7.85), ('Alüminyum', 2.7),
                                   ('Delrin (POM-H)', 1.42), ('Kestamit (PA6G)', 1.15)):
            with self.subTest(material=material):
                result = rules.calculate(material=material, b=100, t=10, count=2)
                self.assertAlmostEqual(result.mass_kg, expected)
                self.assertAlmostEqual(result.total_mass_kg, 2 * expected)
        result = rules.calculate(material='Özel malzeme', density='2000', b=100, t=10)
        self.assertEqual(result.mass_kg, 2)
        self.assertEqual(result.density, 2000)

    def test_catalog_area_is_cm2_and_ignores_all_geometry_fields(self):
        result = rules.calculate(kind='IPE', method='Katalog alanından', area_cm2='12,34',
                                 length=2, unit='m', b='hatalı', h=-1, tw=float('nan'), tf=None)
        self.assertAlmostEqual(result.area_mm2, 1234)
        self.assertAlmostEqual(result.volume_m3, .002468)
        self.assertAlmostEqual(result.mass_kg, 19.3738)
        self.assertEqual(result.dimensions_mm, {})
        self.assertFalse(result.approximate)

    def test_only_active_dimension_fields_are_parsed(self):
        result = rules.calculate(kind='Mil', d=20, b='geçersiz', h=-1, t=float('nan'),
                                 tw=None, tf=False, s='sonsuz', area_cm2='geçersiz')
        self.assertAlmostEqual(result.area_mm2, 100 * math.pi)
        self.assertEqual(result.dimensions_mm, {'d': 20})

    def test_turkish_decimal_comma_and_whitespace(self):
        result = rules.calculate(b=' 100,5 ', t='2,5', length='1000,5', count='2,0', density='7850,0')
        self.assertAlmostEqual(result.area_mm2, 251.25)
        self.assertAlmostEqual(result.mass_kg, .000251375625 * 7850)
        self.assertEqual(result.count, 2)
        self.assertEqual(rules.fmt(12.500), '12,5')
        self.assertNotEqual(rules.fmt(.000001), '0')

    def test_nonphysical_walls_and_overlapping_flanges_are_rejected(self):
        cases = [('Kutu profil', {'b': 10, 'h': 20, 't': 5}),
                 ('Boru', {'d': 10, 't': 5}),
                 ('Köşebent', {'b': 10, 'h': 20, 't': 10}),
                 ('T profil', {'b': 20, 'h': 10, 'tf': 10, 'tw': 5}),
                 ('T profil', {'b': 20, 'h': 30, 'tf': 5, 'tw': 20}),
                 ('IPE', {'b': 20, 'h': 10, 'tf': 5, 'tw': 3}),
                 ('U profil', {'b': 10, 'h': 20, 'tf': 2, 'tw': 10})]
        for kind, dimensions in cases:
            with self.subTest(kind=kind, dimensions=dimensions), self.assertRaises(ValueError):
                rules.calculate(kind=kind, **dimensions)

    def test_invalid_and_nonfinite_inputs_do_not_produce_a_result(self):
        cases = [{'kind': 'Bilinmeyen'}, {'material': 'Bilinmeyen'}, {'unit': 'inch'},
                 {'method': 'Bilinmeyen'}, {'density': 0}, {'density': 30001},
                 {'density': float('inf')}, {'count': 1.5}, {'count': 1000001},
                 {'count': True}, {'length': 0}, {'length': float('nan')},
                 {'b': -1}, {'t': None}, {'b': '1.000,5'},
                 {'method': 'Katalog alanından'},
                 {'method': 'Katalog alanından', 'area_cm2': 0}]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ValueError):
                rules.calculate(**values)

    def test_numeric_overflow_is_a_validation_error(self):
        for values in ({'b': '1e308', 't': '1e308'},
                       {'kind': 'Kare demir', 'b': '1e308'},
                       {'method': 'Katalog alanından', 'area_cm2': '1e308'},
                       {'unit': 'm', 'length': '1e308'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                rules.calculate(**values)


if __name__ == '__main__':
    unittest.main()
