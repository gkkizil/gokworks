"""Independent interval arithmetic and positive/negative clearance GUI audit."""

import csv
import json
import unittest
from fractions import Fraction
from itertools import product
from pathlib import Path
from unittest.mock import patch


from modules.iso_fits import rules
from modules.iso_fits.manual import calculate_manual
from modules.iso_fits.ui import SAMPLES


class ToleranceArithmeticAuditTests(unittest.TestCase):
    def test_every_iso_pair_at_boundaries_and_just_above_with_fraction_oracle(self):
        table = json.loads((Path(__file__).parents[3]/'modules/iso_fits/tables.json').read_text())
        sizes = {Fraction(1), Fraction(400)}
        for bound in table['bounds_mm']:
            sizes.add(Fraction(bound))
            if bound < 400:
                sizes.add(Fraction(bound)+Fraction(1, 1000000))
        for size, hole, shaft in product(sorted(sizes), table['holes'], table['shafts']):
            index = sum(Fraction(bound) < size for bound in table['bounds_mm'])
            hu, hl = table['classes'][hole][index]
            su, sl = table['classes'][shaft][index]
            D0, D1 = size+Fraction(hl, 1000000), size+Fraction(hu, 1000000)
            d0, d1 = size+Fraction(sl, 1000000), size+Fraction(su, 1000000)
            fit = rules.calculate(str(float(size)), hole, shaft)
            expected = 'clearance' if D0 >= d1 else 'interference' if D1 <= d0 else 'transition'
            self.assertEqual(fit.kind, expected, (size, hole, shaft))
            self.assertEqual(Fraction(fit.minimum_clearance_nm, 1000000), D0-d1)
            self.assertEqual(Fraction(fit.maximum_clearance_nm, 1000000), D1-d0)
            for sample, pair in zip(SAMPLES, ((D0, d1), ((D0+D1)/2, (d0+d1)/2), (D1, d0))):
                self.assertEqual(tuple(Fraction(str(v)) for v in fit.sample(sample)), pair)

    def test_manual_interval_grid_with_signed_raw_input_oracle(self):
        values = ('-0.05', '-0.02', '0', '0.02', '0.05')
        for a, b, c, d in product(values, repeat=4):
            if Fraction(a) > Fraction(b) or Fraction(c) > Fraction(d):
                continue
            fit = calculate_manual('50', a, b, c, d)
            minimum, maximum = Fraction(a)-Fraction(d), Fraction(b)-Fraction(c)
            expected = 'clearance' if minimum >= 0 else 'interference' if maximum <= 0 else 'transition'
            self.assertEqual(fit.kind, expected, (a, b, c, d))
            self.assertEqual(Fraction(fit.minimum_clearance_nm, 1000000), minimum)
            self.assertEqual(Fraction(fit.maximum_clearance_nm, 1000000), maximum)
        with self.assertRaises(ValueError):
            calculate_manual('50', '0', '0.02%', '0', '0')




if __name__ == '__main__':
    unittest.main()
