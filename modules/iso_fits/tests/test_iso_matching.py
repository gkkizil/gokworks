"""Manual ISO identification with independent Ø50 mm reference values.

Hole numbers: lachr/Passungsrechner 0289439b1883db363d92e38f1ab352817b4d5a47,
src/data/tolerances.json (EI, ES in µm). No H7 default or preset is a match.
"""

import unittest
from decimal import Decimal


from modules.iso_fits.manual import closest_classes, manual_band
from modules.iso_fits.rules import PRESETS
from modules.iso_fits.ui import BASES

HOLES_50 = {'H6': (0, 16), 'H7': (0, 25), 'H8': (0, 39), 'H9': (0, 62),
            'H11': (0, 160), 'F8': (25, 64), 'G7': (9, 34),
            'JS7': (-12.5, 12.5), 'K7': (-18, 7), 'N7': (-33, -8), 'P7': (-42, -17)}


def from_um(value):
    return str(Decimal(str(value))/1000)


class ManualMatchingRulesTests(unittest.TestCase):
    def test_independent_hole_values_identify_their_own_class(self):
        for code, (lower, upper) in HOLES_50.items():
            with self.subTest(code=code):
                band = manual_band(50, from_um(lower), from_um(upper), 'hole')
                matches = closest_classes(band, 'hole')
                self.assertEqual([(item.code, item.exact) for item in matches], [(code, True)])
                self.assertEqual((band.lower_nm, band.upper_nm), (lower*1000, upper*1000))

    def test_equal_distance_is_not_a_unique_iso_identification(self):
        band = manual_band(50, '-0,05', '0', 'hole')
        matches = closest_classes(band, 'hole')
        self.assertEqual([(item.code, item.distance_nm) for item in matches], [('N7', 25000), ('P7', 25000)])
        self.assertFalse(any(item.exact for item in matches))

    def test_manual_band_has_no_reference_class_and_rejects_wrong_feature(self):
        band = manual_band('50.000000001', '-0,02', '0,02', 'hole')
        self.assertEqual((band.code, band.bracket_mm), ('Manuel', (50, 65)))
        self.assertEqual(band.minimum_mm, Decimal('49.980000001'))
        self.assertFalse(any(item.exact for item in closest_classes(band, 'hole')))
        with self.assertRaises(ValueError):
            manual_band(50, 0, '.02', 'bad feature')




if __name__ == '__main__':
    unittest.main()
