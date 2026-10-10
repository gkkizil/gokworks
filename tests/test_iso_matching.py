"""Manual ISO identification with independent Ø50 mm reference values.

Hole numbers: lachr/Passungsrechner 0289439b1883db363d92e38f1ab352817b4d5a47,
src/data/tolerances.json (EI, ES in µm). No H7 default or preset is a match.
"""

import unittest
from decimal import Decimal

from support.gui import GuiTestCase

from iso_fits.manual import closest_classes, manual_band
from iso_fits.rules import PRESETS
from iso_fits.window import BASES

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


class ManualMatchingGuiTests(GuiTestCase):
    def manual(self):
        self.app._switch_mode('iso_fits')
        self.app.iso_widgets['method']._buttons_dict['Manuel kontrol'].invoke()
        self.settle()

    def test_every_hole_band_updates_native_labels_and_report_without_h7_fallback(self):
        self.manual()
        self.app.iso_state['hole'].set('H7')  # Saved ISO selector must not leak into manual results.
        for code, (lower, upper) in HOLES_50.items():
            with self.subTest(code=code):
                self.app._set_manual_inputs([('hole_lower', from_um(lower)), ('hole_upper', from_um(upper)),
                                             ('shaft_lower', '-0.016'), ('shaft_upper', '0')])
                text = self.app.iso_widgets['iso_comparison'].cget('text')
                self.assertIn('DELİK · Tam eşleşme: '+code+'\n', text)
                self.assertIn('Tam ISO çift eşleşmesi: '+code+'/h6', self.app.iso_widgets['explanation'].cget('text'))
                report = dict(self.app._iso_report_rows())
                self.assertEqual(report['Delik ISO kontrolü'], 'Tam eşleşme: '+code)
                self.assertEqual(Decimal(report['EI (µm)'].replace(',', '.')), Decimal(str(lower)))
                self.assertEqual(Decimal(report['ES (µm)'].replace(',', '.')), Decimal(str(upper)))
                self.assertEqual(self.app.iso_result.hole.lower_nm, lower*1000)
                self.assertEqual(self.app.iso_result.hole.upper_nm, upper*1000)

    def test_default_manual_example_does_not_suggest_common_h7_preset(self):
        self.manual()
        self.app.iso_widgets['manual_example'].invoke()
        self.assertIn('Delik H6 (tam eşleşme yok; referans)', self.app.iso_widgets['explanation'].cget('text'))
        self.assertIn('H6/h6', self.app.iso_widgets['compatibility_text'].cget('text'))
        self.app.iso_widgets['copy'].invoke()
        report = self.app.clipboard_get()
        self.assertNotIn('H7/h6', report)
        self.assertIn('Tam ISO eşleşmesi yok', report)
        self.assertIn('+0,040000', report)

    def test_equal_distance_and_distant_references_are_visible(self):
        self.manual()
        self.app.iso_widgets['compatibility_example'].invoke()
        self.assertEqual(self.app.iso_result.kind, 'transition')
        text = self.app.iso_widgets['iso_comparison'].cget('text')
        self.assertIn('Eşit uzaklıktaki sınıflar: N7, P7', text)
        self.assertIn('tek bir sınıf seçilemez', text)
        self.assertIn('yalnız referans', self.app.iso_widgets['compatibility_text'].cget('text'))
        self.assertIn('genişliğini aşıyor', self.app.iso_widgets['compatibility_text'].cget('text'))

    def test_entry_edit_invalid_recovery_and_navigation_preserve_new_match(self):
        self.manual()
        field = self.app.iso_widgets['hole_upper']
        field.delete(0, 'end'); field.insert(0, '0,039')
        self.settle()
        self.assertIn('Tam eşleşme: H8', self.app.iso_widgets['iso_comparison'].cget('text'))
        field.delete(0, 'end'); field.insert(0, 'wrong')
        self.assertIsNone(self.app.iso_result)
        self.assertEqual(self.app.iso_widgets['iso_comparison'].cget('text'), '—')
        field.delete(0, 'end'); field.insert(0, '0,062')
        for mode in ('k_factor', 'pdf', 'iso_fits'):
            self.app._switch_mode(mode); self.settle()
        self.assertIn('Tam eşleşme: H9', self.app.iso_widgets['iso_comparison'].cget('text'))
        self.assertEqual(self.app.iso_result.hole.upper_nm, 62000)

    def test_basis_filters_and_clicks_show_non_h7_transition_examples(self):
        self.app._switch_mode('iso_fits')
        self.settle()
        transitions = ['H7 / js6', 'JS7 / h6', 'H7 / k6', 'K7 / h6']
        rows = [int(self.app.iso_widgets['preset_buttons'][code].grid_info()['row']) for code in transitions]
        self.assertEqual(rows, list(range(rows[0], rows[0]+4)))
        for index, basis in enumerate(BASES):
            self.app.iso_widgets['basis']._dropdown_menu.invoke(index)
            visible = {code for code, button in self.app.iso_widgets['preset_buttons'].items() if button.winfo_manager()}
            expected = {preset.code for preset in PRESETS if basis in ('Tümü', preset.basis)}
            self.assertEqual(visible, expected)
            if basis == 'Mil esaslı':
                for code, clearance in [('JS7 / h6', (-12500, 28500)), ('K7 / h6', (-18000, 23000)),
                                        ('N7 / h6', (-33000, 8000)), ('P7 / h6', (-42000, -1000))]:
                    self.app.iso_widgets['preset_buttons'][code].invoke()
                    self.assertEqual((self.app.iso_result.minimum_clearance_nm, self.app.iso_result.maximum_clearance_nm), clearance)
                    self.assertEqual(self.app.iso_result.kind, 'interference' if code.startswith('P7') else 'transition')
                self.assertFalse(any(code.startswith('H') for code in visible))
        self.app.iso_state['basis'].set('Delik esaslı')
        for code in ('H6 / k6', 'H8 / k6'):
            self.app.iso_widgets['preset_buttons'][code].invoke()
            self.assertEqual(self.app.iso_result.kind, 'transition')

    def test_basis_search_diameter_regrouping_and_persistence(self):
        self.app._switch_mode('iso_fits')
        self.app.iso_state['basis'].set('Mil esaslı')
        self.app.iso_search.set('P7/h6')
        visible = [code for code, button in self.app.iso_widgets['preset_buttons'].items() if button.winfo_manager()]
        self.assertEqual(visible, ['P7 / h6'])
        self.app.iso_widgets['preset_buttons']['P7 / h6'].invoke()
        self.assertEqual(self.app.iso_result.kind, 'interference')
        self.app.iso_state['diameter'].set('3')
        self.assertEqual(self.app.iso_result.kind, 'interference')
        self.assertEqual(self.app.iso_result.maximum_clearance_nm, 0)  # Boundary contact, not transition.
        self.app.iso_search.set('')
        self.app.iso_state['basis'].set('Delik esaslı')
        self.app.iso_widgets['preset_buttons']['H7 / p6'].invoke()
        self.assertEqual(self.app.iso_result.kind, 'transition')
        self.app.iso_state['diameter'].set('50')
        self.assertEqual(self.app.iso_result.kind, 'interference')
        self.app.iso_state['basis'].set('Mil esaslı')
        self.app.iso_widgets['preset_buttons']['P7 / h6'].invoke()
        self.app._on_close()
        self.open_app()
        self.app._switch_mode('iso_fits'); self.settle()
        self.assertEqual(self.app.iso_state['basis'].get(), 'Mil esaslı')
        self.assertEqual(self.app.iso_result.hole.code, 'P7')

    def test_shorter_filtered_list_stays_visible_after_manual_form(self):
        self.app._switch_mode('iso_fits'); self.settle()
        presets = self.app.iso_widgets['presets']
        presets._parent_canvas.yview_moveto(1)
        self.app.iso_widgets['method']._buttons_dict['Manuel kontrol'].invoke(); self.settle()
        self.app.iso_widgets['method']._buttons_dict['ISO seçimi'].invoke()
        self.app.iso_widgets['basis']._dropdown_menu.invoke(2); self.settle()
        canvas = presets._parent_canvas
        button = self.app.iso_widgets['preset_buttons']['G7 / h6']
        self.assertTrue(button.winfo_viewable())
        self.assertGreaterEqual(button.winfo_rooty(), canvas.winfo_rooty())
        self.assertLessEqual(button.winfo_rooty()+button.winfo_height(), canvas.winfo_rooty()+canvas.winfo_height())
        self.assertEqual(canvas.yview()[0], 0)
        self.assertLess(presets.winfo_height(), 600)


if __name__ == '__main__':
    unittest.main()
