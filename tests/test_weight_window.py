"""Native material weight controls, conversions and cached workspace behavior."""

from unittest.mock import patch

import customtkinter as ctk

from pdf.settings import load_settings
from support.gui import GuiTestCase
from weight.rules import FIELDS, KINDS, MATERIALS


class WeightWindowTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.app.nav_buttons['weight'].invoke()
        self.settle()

    def test_all_section_choices_update_fields_density_and_piece_totals(self):
        state, w = self.app.weight_state, self.app.weight_widgets
        self.assertEqual(len(w['choices']), 19)
        self.assertAlmostEqual(self.app.weight_result.total_mass_kg, 3.925)
        for kind in KINDS:
            with self.subTest(kind=kind):
                w['choices'][kind].invoke()
                self.assertEqual(self.app.weight_result.kind, kind)
                self.assertGreater(self.app.weight_result.total_mass_kg, 0)
                for key, frame in w['dim_frames'].items():
                    self.assertEqual(frame.winfo_manager() == 'grid', key in FIELDS[kind])
        state['kind'].set('Sac levha')
        state['material'].set('Alüminyum')
        self.assertEqual(float(state['density'].get()), MATERIALS['Alüminyum'])
        self.assertAlmostEqual(self.app.weight_result.mass_kg, 1.35)
        state['count'].set('3')
        self.assertAlmostEqual(self.app.weight_result.total_mass_kg, 4.05)
        state['density'].set('2800')
        self.assertAlmostEqual(self.app.weight_result.total_mass_kg, 4.2)
        self.app._copy_weight_result()
        report = self.app.clipboard_get()
        self.assertIn('Ağırlık hesabı · Sac levha', report)
        self.assertIn('2.800,000 kg/m³', report)
        self.assertIn('Adet: 3', report)
        self.assertIn('4,200 kg', report)
        state['kind'].set('HEA')
        self.assertTrue(self.app.weight_result.approximate)
        self.assertIn('Katalog alanı', w['note'].cget('text'))

    def test_units_preserve_inactive_dimensions_and_catalogue_mode_clears_invalid_results(self):
        state, w = self.app.weight_state, self.app.weight_widgets
        state['density'].set('8000')
        state['count'].set('3')
        original = self.app.weight_result.total_mass_kg
        for unit in ('cm', 'm', 'mm'):
            state['unit'].set(unit)
            self.assertAlmostEqual(self.app.weight_result.total_mass_kg, original, places=8)
            self.assertEqual(state['density'].get(), '8000')
            self.assertEqual(state['area_cm2'].get(), '10')
            self.assertEqual(state['count'].get(), '3')
        self.assertAlmostEqual(float(state['h'].get().replace(',', '.')), 100)
        self.assertAlmostEqual(float(state['length'].get().replace(',', '.')), 1000)
        state['method'].set('Katalog alanından')
        state['area_cm2'].set('12,5')
        state['b'].set('')
        state['t'].set('')
        self.assertAlmostEqual(self.app.weight_result.total_mass_kg, 30)
        self.assertEqual(w['area_frame'].winfo_manager(), 'grid')
        self.assertFalse(any(frame.winfo_manager() == 'grid' for frame in w['dim_frames'].values()))
        state['method'].set('Ölçülerden')
        self.assertIsNone(self.app.weight_result)
        self.assertEqual(w['copy'].cget('state'), 'disabled')
        self.assertEqual(w['total'].cget('text'), '—')
        self.assertEqual(w['each'].cget('text'), '—')
        state['method'].set('Katalog alanından')
        for key, bad in (('area_cm2', '0'), ('density', 'nan'), ('count', '1,5')):
            previous = state[key].get()
            state[key].set(bad)
            self.assertIsNone(self.app.weight_result)
            self.assertEqual(w['copy'].cget('state'), 'disabled')
            state[key].set(previous)
            self.assertIsNotNone(self.app.weight_result)

    def test_cached_preferences_theme_small_window_and_drawing_cache(self):
        state, w = self.app.weight_state, self.app.weight_widgets
        state['kind'].set('Boru')
        state['d'].set('60')
        state['t'].set('3')
        state['density'].set('7900')
        self.app._switch_mode('bolt')
        self.app._switch_mode('weight')
        self.assertIs(self.app.weight_widgets, w)
        self.assertEqual(state['kind'].get(), 'Boru')
        self.assertEqual(self.app._focus_search(), 'break')
        self.app._save_preferences()
        saved = load_settings(self.settings)
        self.assertEqual(saved['weight_kind'], 'Boru')
        self.assertEqual(saved['weight_density'], '7900')
        self.assertEqual(saved['unrelated_setting'], 'keep')
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        for theme, scale, size in (('Açık', 1, '1000x690'), ('Koyu', 1.25, '1240x860')):
            self.app._change_theme(theme)
            ctk.set_widget_scaling(scale)
            self.app._set_scaled_min_max()
            self.app.geometry(size)
            w['details']._parent_canvas.yview_moveto(0)
            self.settle()
            self.assert_inside(w['total'])
            self.assert_inside(w['copy'])
            for button in self.app.nav_buttons.values():
                self.assert_inside(button)
            self.assert_inside(self.app.theme_selector.master)
            w['form']._parent_canvas.yview_moveto(1)
            self.app.update()
            self.assert_inside(w['length_input'])
            viewport = w['details']._parent_canvas
            diagram = w['canvas']
            top = diagram.winfo_rooty()-viewport.winfo_rooty()+viewport.canvasy(0)
            viewport.yview_moveto(max(0, (top-12)/viewport.bbox('all')[3]))
            self.app.update()
            self.assert_inside(diagram)
            # DPI/scroll changes can leave a native Configure event queued.
            # Only an unchanged, settled canvas should skip its next redraw.
            self.settle()
            with patch('weight.window.draw') as render:
                self.app._draw_weight_diagram()
                self.app._resize_weight_workspace()
                render.assert_not_called()
        ctk.set_widget_scaling(1)
        self.close_app()
        self.open_app()
        self.app._switch_mode('weight')
        self.assertEqual(self.app.weight_state['kind'].get(), 'Boru')
        self.assertEqual(self.app.weight_state['d'].get(), '60')
        self.assertEqual(self.app.weight_result.density, 7900)
