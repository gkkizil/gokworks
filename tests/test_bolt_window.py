"""Real Tk controls, load diagrams and page lifecycle for bolt calculations."""

from unittest.mock import patch

import customtkinter as ctk
from support.gui import GuiTestCase
from pdf.settings import load_settings


class BoltWindowTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.app.nav_buttons['bolt'].invoke()
        self.settle()

    def test_live_load_modes_and_invalid_input_clear_previous_verdict(self):
        state, w = self.app.bolt_state, self.app.bolt_widgets
        self.assertEqual(w['verdict'].cget('text'), 'Güvenli')
        state['tension'].set('20')
        self.assertEqual(w['verdict'].cget('text'), 'Güvensiz')
        state['grade'].set('12.9')
        self.assertEqual(w['verdict'].cget('text'), 'Güvenli')
        self.assertEqual(self.app.bolt_result.proof_stress, 970)
        self.assertIn('12.9', [w['canvas'].itemcget(item, 'text')
                              for item in w['canvas'].find_all() if w['canvas'].type(item) == 'text'])
        state['grade'].set('8.8')
        self.assertEqual(w['verdict'].cget('text'), 'Güvensiz')
        state['tension'].set('')
        self.assertIsNone(self.app.bolt_result)
        self.assertEqual(w['copy'].cget('state'), 'disabled')
        self.assertEqual(w['stress'].cget('text'), '—')
        self.assertFalse(w['canvas'].find_withtag('tension_arrow'))
        state['mode'].set('Kesme')
        state['shear'].set('10')
        self.assertEqual(w['verdict'].cget('text'), 'Güvensiz')
        self.assertFalse(w['canvas'].find_withtag('tension_arrow'))
        self.assertEqual(len(w['canvas'].find_withtag('shear_arrow')), 2)
        state['planes'].set('Çift kesme')
        self.assertEqual(w['verdict'].cget('text'), 'Güvenli')
        self.assertEqual(len(w['canvas'].find_withtag('shear_arrow')), 3)
        state['mode'].set('Birleşik yük')
        state['tension'].set('12')
        state['shear'].set('8')
        state['planes'].set('Tek kesme')
        self.assertEqual(w['verdict'].cget('text'), 'Güvensiz')
        self.assertEqual(len(w['canvas'].find_withtag('tension_arrow')), 2)
        state['tension'].set('0')
        state['shear'].set('0')
        self.assertEqual(w['verdict'].cget('text'), 'Yük yok')

    def test_units_page_cache_preferences_and_copy_preserve_physical_load(self):
        state, w = self.app.bolt_state, self.app.bolt_widgets
        before = self.app.bolt_result
        for unit in ('N', 'kg', 'kN'):
            state['unit'].set(unit)
            self.assertAlmostEqual(self.app.bolt_result.tension_n, before.tension_n, places=6)
        self.app._select_bolt_unit('kg yük')
        self.assertEqual(state['unit'].get(), 'kg')
        self.assertIn('kg yük', w['capacity'].cget('text'))
        self.assertIn('9,80665', w['unit_hint'].cget('text'))
        self.assertTrue(any('kg yük' in w['canvas'].itemcget(item, 'text')
                            for item in w['canvas'].find_all() if w['canvas'].type(item) == 'text'))
        state['metric'].set('M12')
        self.app._copy_bolt_result()
        self.assertIn('M12', self.app.clipboard_get())
        self.assertIn('Ön sıkmalı', self.app.clipboard_get())
        self.app._switch_mode('pdf')
        self.app._change_theme('Koyu')
        self.app._switch_mode('bolt')
        self.assertIs(self.app.bolt_widgets, w)
        self.assertEqual(state['metric'].get(), 'M12')
        self.assertEqual(self.app._focus_search(), 'break')
        self.app._save_preferences()
        saved = load_settings(self.settings)
        self.assertEqual(saved['bolt_metric'], 'M12')
        self.assertEqual(saved['bolt_unit'], 'kg')
        self.assertEqual(saved['unrelated_setting'], 'keep')
        self.close_app()
        self.open_app()
        self.app._switch_mode('bolt')
        self.assertEqual(self.app.bolt_result.metric, 'M12')
        self.assertEqual(self.app.bolt_state['unit'].get(), 'kg')

    def test_small_window_dpi_and_unchanged_diagram(self):
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        for theme, scale, size in (('Açık', 1, '1000x690'), ('Koyu', 1.25, '1240x860')):
            self.app._change_theme(theme)
            ctk.set_widget_scaling(scale)
            self.app._set_scaled_min_max()
            self.app.geometry(size)
            self.app.bolt_widgets['details']._parent_canvas.yview_moveto(0)
            self.settle()
            for key in ('result_card', 'canvas'):
                self.assert_inside(self.app.bolt_widgets[key])
            for button in self.app.nav_buttons.values():
                self.assert_inside(button)
            self.assert_inside(self.app.theme_selector.master)
            for panel, control in (('form', 'safety_factor_input'), ('details', 'copy')):
                self.app.bolt_widgets[panel]._parent_canvas.yview_moveto(1)
                self.app.update()
                self.assert_inside(self.app.bolt_widgets[control])
            with patch('bolt.window.draw') as render:
                self.app._draw_bolt_diagram()
                self.app._resize_bolt_workspace()
                render.assert_not_called()
