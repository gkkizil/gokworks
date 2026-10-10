"""Section dimensions, radial differences and selected/overall fit states."""

import os
import time
import unittest

import customtkinter as ctk
import test_export_window as fixtures
from iso_fits.rules import format_mm
from iso_fits.window import SAMPLES


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'GUI requires a display')
class IsoSectionTests(unittest.TestCase):
    setUp = fixtures.WindowTests.setUp
    close_app = fixtures.WindowTests.close_app

    def section(self, hole='H8', shaft='f7'):
        self.app._switch_mode('iso_fits')
        self.app.iso_state['hole'].set(hole)
        self.app.iso_state['shaft'].set(shaft)
        self.settle()
        return self.app.iso_widgets['canvas']

    def settle(self):
        end = time.monotonic()+.12
        while time.monotonic() < end:
            self.app.update()
            time.sleep(.003)

    def text(self, tag):
        canvas = self.app.iso_widgets['canvas']
        return canvas.itemcget(canvas.find_withtag(tag)[0], 'text')

    def test_diameter_arrows_span_parts_and_radial_arrow_is_half_the_difference(self):
        canvas = self.section()
        for sample in SAMPLES:
            self.app.iso_state['sample'].set(sample)
            self.app.update()
            hole, shaft = self.app.iso_result.sample(sample)
            self.assertIn(format_mm(hole), self.text('hole_label'))
            self.assertIn(format_mm(shaft), self.text('shaft_label'))
            self.assertIn(format_mm(hole-shaft), self.text('diametral_result'))
            self.assertIn(format_mm((hole-shaft)/2), self.text('radial_result'))
            d_hole = canvas.coords(canvas.find_withtag('dimension_D')[0])
            d_shaft = canvas.coords(canvas.find_withtag('dimension_d')[0])
            body = canvas.coords(canvas.find_withtag('shaft')[0])
            walls = [canvas.coords(i) for i in canvas.find_withtag('housing')]
            self.assertEqual((d_hole[1], d_hole[3]), (walls[0][3], walls[1][1]))
            self.assertEqual((d_shaft[1], d_shaft[3]), (body[1], body[3]))
            radial = canvas.coords(canvas.find_withtag('radial_dimension')[0])
            self.assertAlmostEqual(radial[3]-radial[1],
                                   ((d_hole[3]-d_hole[1])-(d_shaft[3]-d_shaft[1]))/2)

    def test_transition_endpoints_show_different_samples_with_same_overall_kind(self):
        canvas = self.section('H7', 'k6')
        ratios = []
        for sample, state, region in [(SAMPLES[0], 'SIKILIK VAR', 'overlap'),
                                      (SAMPLES[2], 'BOŞLUK VAR', 'clearance')]:
            self.app.iso_state['sample'].set(sample)
            self.app.update()
            self.assertIn(state, self.text('sample_state'))
            self.assertIn('Ara geçme', self.text('fit_kind'))
            self.assertEqual(len(canvas.find_withtag(region)), 2)
            self.assertFalse(canvas.find_withtag('clearance' if region == 'overlap' else 'overlap'))
            hole, shaft = self.app.iso_result.sample(sample)
            self.assertIn(format_mm(abs(hole-shaft)), self.text('diametral_result'))
            radial = canvas.coords(canvas.find_withtag('radial_dimension')[0])
            ratios.append((radial[3]-radial[1])/float(abs(hole-shaft)))
        self.assertAlmostEqual(*ratios)  # Magnification stays fixed across samples.

    def test_zero_difference_is_contact_without_gap_or_overlap_and_recovers(self):
        canvas = self.section('H7', 'h6')
        self.app.iso_state['sample'].set(SAMPLES[0])
        self.app.update()
        self.assertIn('SINIRDA TEMAS', self.text('sample_state'))
        self.assertIn('g = 0 mm', self.text('radial_result'))
        for tag in ('clearance', 'overlap', 'radial_dimension'):
            self.assertFalse(canvas.find_withtag(tag))
        d_hole = canvas.coords(canvas.find_withtag('dimension_D')[0])
        d_shaft = canvas.coords(canvas.find_withtag('dimension_d')[0])
        self.assertEqual(d_hole[1::2], d_shaft[1::2])
        self.app.iso_state['sample'].set(SAMPLES[2])
        self.assertEqual(len(canvas.find_withtag('clearance')), 2)
        self.assertIn('BOŞLUK VAR', self.text('sample_state'))

    def test_manual_half_micron_radial_value_and_negative_gap_are_exact(self):
        canvas = self.section()
        self.app.iso_state['method'].set('Manuel kontrol')
        for key, value in [('hole_lower', '0,000001'), ('hole_upper', '0,000001'),
                           ('shaft_lower', '0'), ('shaft_upper', '0')]:
            self.app.iso_state[key].set(value)
        self.assertIn('0,000001', self.text('diametral_result'))
        self.assertIn('0,0000005', self.text('radial_result'))
        self.app.iso_state['shaft_upper'].set('0,000002')
        self.app.iso_state['shaft_lower'].set('0,000002')
        self.assertIn('d − D', self.text('diametral_result'))
        self.assertIn('0,0000005', self.text('radial_result'))
        self.assertEqual(len(canvas.find_withtag('overlap')), 2)
        self.app.iso_state['diameter'].set('invalid')
        self.assertEqual(len(canvas.find_all()), 1)
        self.assertFalse(canvas.find_withtag('diametral_result'))

    def test_small_window_both_themes_and_dpi_keep_labels_inside_canvas(self):
        canvas = self.section()
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        self.addCleanup(lambda: ctk.set_window_scaling(1))
        for scale in (1, 1.25, 1.5):
            ctk.set_widget_scaling(scale)
            ctk.set_window_scaling(scale)
            self.app.geometry('1000x690')
            for theme in ('Açık', 'Koyu'):
                self.app._change_theme(theme)
                self.settle()
                for tag in ('hole_label', 'shaft_label', 'sample_state', 'diametral_result', 'radial_result', 'fit_kind'):
                    x0, y0, x1, y1 = canvas.bbox(canvas.find_withtag(tag)[0])
                    self.assertGreaterEqual(x0, 0, (tag, theme, scale))
                    self.assertGreaterEqual(y0, 0, (tag, theme, scale))
                    self.assertLessEqual(x1, canvas.winfo_width(), (tag, theme, scale))
                    self.assertLessEqual(y1, canvas.winfo_height(), (tag, theme, scale))
                self.assertTrue(self.app.iso_widgets['sample'].winfo_viewable())

    def test_view_change_restores_height_and_hides_section_legend(self):
        canvas = self.section()
        self.assertEqual(int(canvas.cget('height')), 310)
        self.app.iso_state['view'].set('Tolerans bölgeleri')
        self.settle()
        self.assertEqual(int(canvas.cget('height')), 220)
        self.assertFalse(self.app.iso_widgets['section_help'].winfo_manager())
        self.assertFalse(canvas.find_withtag('sample_state'))
        self.app.iso_state['view'].set('Montaj kesiti')
        self.settle()
        self.assertEqual(int(canvas.cget('height')), 310)
        self.assertTrue(self.app.iso_widgets['section_help'].winfo_manager())
        self.assertIn('BOŞLUK VAR', self.text('sample_state'))


if __name__ == '__main__':
    unittest.main()
