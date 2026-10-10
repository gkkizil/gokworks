"""Independent interval arithmetic and positive/negative clearance GUI audit."""

import csv
import json
import unittest
from fractions import Fraction
from itertools import product
from pathlib import Path
from unittest.mock import patch

from support.gui import GuiTestCase

from iso_fits import rules
from iso_fits.manual import calculate_manual
from iso_fits.window import SAMPLES


class ToleranceArithmeticAuditTests(unittest.TestCase):
    def test_every_iso_pair_at_boundaries_and_just_above_with_fraction_oracle(self):
        table = json.loads((Path(__file__).parents[1]/'iso_fits/tables.json').read_text())
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


class ToleranceGuiAuditTests(GuiTestCase):
    def manual(self, lower_hole, upper_hole, lower_shaft, upper_shaft):
        self.app._switch_mode('iso_fits')
        self.app.iso_state['method'].set('Manuel kontrol')
        self.app._set_manual_inputs(list(zip(('hole_lower', 'hole_upper', 'shaft_lower', 'shaft_upper'),
                                             (lower_hole, upper_hole, lower_shaft, upper_shaft))))
        self.app.update()
        return self.app.iso_widgets['canvas']

    def text(self, tag):
        canvas = self.app.iso_widgets['canvas']
        return canvas.itemcget(canvas.find_withtag(tag)[0], 'text')

    def test_positive_twenty_micron_clearance_never_disappears_with_common_offset(self):
        coordinates = []
        for hole, shaft in (('0.02', '0'), ('2.02', '2'), ('20.02', '20')):
            canvas = self.manual(hole, hole, shaft, shaft)
            self.assertEqual(self.app.iso_result.kind, 'clearance')
            self.assertEqual(self.app.iso_widgets['kind'].cget('text'), 'Boşluklu geçme')
            for sample in SAMPLES:
                self.app.iso_state['sample'].set(sample)
                self.assertIn('BOŞLUK VAR', self.text('sample_state'))
                self.assertIn('D − d = +0,020000 mm', self.text('diametral_result'))
                self.assertIn('g = 0,010000 mm (boşluk)', self.text('radial_result'))
                self.assertEqual(len(canvas.find_withtag('clearance')), 2)
                self.assertFalse(canvas.find_withtag('overlap'))
                radial = canvas.coords(canvas.find_withtag('radial_dimension')[0])
                self.assertGreaterEqual(radial[3]-radial[1], 6)
            coordinates.append(canvas.coords(canvas.find_withtag('radial_dimension')[0])[1::2])
        self.assertEqual(coordinates[0], coordinates[1])
        self.assertEqual(coordinates[0], coordinates[2])

    def test_twenty_micron_interference_has_negative_signed_difference(self):
        canvas = self.manual('2', '2', '2.02', '2.02')
        self.assertEqual(self.app.iso_widgets['kind'].cget('text'), 'Sıkı geçme')
        for sample in SAMPLES:
            self.app.iso_state['sample'].set(sample)
            self.assertIn('SIKILIK VAR', self.text('sample_state'))
            self.assertIn('D − d = -0,020000 mm', self.text('diametral_result'))
            self.assertFalse(canvas.find_withtag('clearance'))
            self.assertEqual(len(canvas.find_withtag('overlap')), 2)
        self.assertIn('Cmin = -0,020000 mm', self.app.iso_widgets['explanation'].cget('text'))
        self.assertIn('Cmax = -0,020000 mm', self.app.iso_widgets['explanation'].cget('text'))

    def test_unilateral_example_section_card_csv_and_clipboard_agree(self):
        self.manual('0', '+0,02', '-0,02', '0')
        output = self.root/'audit.csv'
        for sample, expected in zip(SAMPLES, ('+0,000000', '+0,020000', '+0,040000')):
            self.app.iso_state['sample'].set(sample)
            rows = dict(self.app._iso_report_rows())
            self.assertEqual(rows['Geçme türü'], 'Boşluklu geçme')
            self.assertEqual(rows['Örnek delik − mil (mm)'], expected)
            self.app._copy_iso_result()
            self.assertIn('Örnek delik − mil (mm): '+expected, self.app.clipboard_get())
            with patch('iso_fits.window.filedialog.asksaveasfilename', return_value=str(output)):
                self.app._save_iso_report()
            with output.open(encoding='utf-8-sig', newline='') as stream:
                csv_rows = dict(list(csv.reader(stream, delimiter=';'))[1:])
            self.assertEqual(csv_rows, rows)
        self.assertEqual(self.app.iso_widgets['minimum'].cget('text'), '+0,000000 mm')
        self.assertEqual(self.app.iso_widgets['maximum'].cget('text'), '+0,040000 mm')

    def test_nearest_transition_reference_cannot_replace_positive_actual_clearance(self):
        self.manual('-.023', '-.023', '-.026', '-.026')
        self.assertEqual(self.app.iso_widgets['kind'].cget('text'), 'Boşluklu geçme')
        self.assertIn('BOŞLUK VAR', self.text('sample_state'))
        text = self.app.iso_widgets['compatibility_text'].cget('text')
        self.assertTrue(text.startswith('Girilen limitlerin sonucu: Boşluklu geçme.'))
        self.assertIn('Referansın türü: Ara geçme', text)
        self.assertIn('girilen ölçülerin türünden farklı', text)
        self.app.iso_state['target'].set('Sıkı / pres')
        self.assertEqual(self.app.iso_result.kind, 'clearance')
        self.assertIn('uygun değil', self.app.iso_widgets['compatibility_title'].cget('text'))

    def test_transition_positive_twenty_micron_sample_remains_a_positive_clearance(self):
        canvas = self.manual('-0.02', '+0.02', '0', '0')
        self.assertEqual(self.app.iso_widgets['kind'].cget('text'), 'Ara geçme')
        for sample, value, state in zip(SAMPLES, ('-0,020000', '+0,000000', '+0,020000'),
                                        ('SIKILIK VAR', 'SINIRDA TEMAS', 'BOŞLUK VAR')):
            self.app.iso_state['sample'].set(sample)
            self.assertIn(state, self.text('sample_state'))
            self.assertIn('Ara geçme', self.text('fit_kind'))
            self.assertEqual(dict(self.app._iso_report_rows())['Örnek delik − mil (mm)'], value)
        self.assertEqual(len(canvas.find_withtag('clearance')), 2)
        self.assertFalse(canvas.find_withtag('overlap'))


if __name__ == '__main__':
    unittest.main()
