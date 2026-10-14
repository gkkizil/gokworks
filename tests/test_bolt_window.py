"""Real Tk controls, load diagrams and page lifecycle for bolt calculations."""

from unittest.mock import patch

import customtkinter as ctk
from support.gui import GuiTestCase
from pdf.settings import load_settings
from bolt.rules import force_text


class BoltWindowTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.app.nav_buttons['bolt'].invoke()
        self.settle()

    def test_live_load_modes_and_invalid_input_clear_previous_verdict(self):
        state, w = self.app.bolt_state, self.app.bolt_widgets
        state['view'].set('Yük gösterimi')
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
        state['view'].set('Yük gösterimi')
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
            for key in ('result_card', 'capacity_value'):
                self.assert_inside(self.app.bolt_widgets[key])
            for button in self.app.nav_buttons.values():
                self.assert_inside(button)
            self.assert_inside(self.app.theme_selector.master)
            viewport = self.app.bolt_widgets['details']._parent_canvas
            diagram = self.app.bolt_widgets['canvas']
            total_height = viewport.bbox('all')[3]
            top = diagram.winfo_rooty()-viewport.winfo_rooty()+viewport.canvasy(0)
            viewport.yview_moveto(max(0, (top-12)/total_height))
            self.app.update()
            self.assert_inside(diagram)
            for panel, control in (('form', 'safety_factor_input'), ('details', 'copy')):
                self.app.bolt_widgets[panel]._parent_canvas.yview_moveto(1)
                self.app.update()
                self.assert_inside(self.app.bolt_widgets[control])
            with patch('bolt.window.draw_dimensions') as render:
                self.app._draw_bolt_diagram()
                self.app._resize_bolt_workspace()
                render.assert_not_called()

    def test_dimensions_and_capacity_follow_metric_units_and_load_mode(self):
        state, w = self.app.bolt_state, self.app.bolt_widgets
        self.assertEqual(state['view'].get(), 'Ölçüler')
        state['metric'].set('M8')
        texts = [w['canvas'].itemcget(item, 'text') for item in w['canvas'].find_all()
                 if w['canvas'].type(item) == 'text']
        self.assertIn('s=13,0 mm', texts)
        self.assertIn('k=5,3', texts)
        self.assertIn('≈ Ø6,75 mm', texts)
        self.assertIn('Yaklaşık d − P', texts)
        self.assertEqual(len(w['canvas'].find_withtag('dimension_head')), 1)
        self.assertEqual(len(w['canvas'].find_withtag('dimension_hex')), 1)
        self.assertIn('kN', w['capacity_value'].cget('text'))
        one = self.app.bolt_result.tension_capacity_n
        state['count'].set('2')
        self.assertAlmostEqual(self.app.bolt_result.tension_capacity_n, 2*one)
        self.assertIn('2 cıvata', w['capacity_context'].cget('text'))
        state['mode'].set('Kesme')
        self.assertIn('KESME', w['capacity_title'].cget('text'))
        state['unit'].set('N')
        self.assertTrue(w['capacity_value'].cget('text').endswith(' N'))
        state['mode'].set('Birleşik yük')
        self.assertIn('KAPASİTE KULLANIMI', w['capacity_title'].cget('text'))
        self.assertTrue(w['capacity_value'].cget('text').startswith('%'))
        state['tension'].set('invalid')
        self.assertEqual(w['capacity_value'].cget('text'), '—')
        self.assertTrue(w['canvas'].find_withtag('dimension_head'))

    def test_minimum_count_and_target_margin_are_advisory_and_cleared_when_invalid(self):
        state, w = self.app.bolt_state, self.app.bolt_widgets
        state['tension'].set('20')
        self.assertEqual(self.app.bolt_result.minimum_count, 2)
        self.assertEqual(state['count'].get(), '1')
        self.assertIn('gerekli en az: 2 cıvata', w['usage'].cget('text'))
        self.assertIn('Yük marjı: -%', w['usage'].cget('text'))
        state['count'].set('2')
        self.assertEqual(self.app.bolt_result.minimum_count, 2)
        self.assertIn('Yük marjı: +%', w['usage'].cget('text'))
        self.app._copy_bolt_result()
        report = self.app.clipboard_get()
        self.assertIn('gerekli en az: 2 cıvata', report)
        self.assertIn('Seçili emniyet hedefine göre yük marjı', report)
        self.assertIn('adet otomatik değiştirilmez', report)
        state['tension'].set('1000000000')
        self.assertGreater(self.app.bolt_result.minimum_count, 1000)
        self.assertEqual(state['count'].get(), '2')
        self.assertIn('1000 adet sınırını aşıyor', w['usage'].cget('text'))
        self.assertNotIn('gerekli en az:', w['usage'].cget('text'))
        state['tension'].set('0')
        self.assertIsNone(self.app.bolt_result.minimum_count)
        self.assertIn('yük girildiğinde hesaplanır', w['usage'].cget('text'))
        state['tension'].set('invalid')
        self.assertEqual(w['usage'].cget('text'), 'Hesaplanamadı')
        self.assertEqual(w['copy'].cget('state'), 'disabled')

    def test_combined_limits_hold_other_load_fixed_and_copy_the_same_units(self):
        state, w = self.app.bolt_state, self.app.bolt_widgets
        for key, value in dict(mode='Birleşik yük', tension='12', shear='8').items():
            state[key].set(value)
        self.assertEqual(self.app.bolt_result.minimum_count, 2)
        self.assertEqual(state['count'].get(), '1')
        for unit in ('kN', 'N', 'kg'):
            state['unit'].set(unit)
            result = self.app.bolt_result
            text = w['capacity'].cget('text')
            self.assertIn(f'çekme sınırı: {force_text(result.tension_limit_with_shear_n, unit)}', text)
            self.assertIn(f'kesme sınırı: {force_text(result.shear_limit_with_tension_n, unit)}', text)
            self.assertIn('iki sınır aynı anda kullanılamaz', text)
            self.assertIn('eklenebilecek yük değildir', text)
            self.app._copy_bolt_result()
            self.assertIn(text, self.app.clipboard_get())
        state['unit'].set('kN')
        state['shear'].set('100')
        self.assertIsNone(self.app.bolt_result.tension_limit_with_shear_n)
        self.assertIn('çekme sınırı: yok; kesme tek başına sınırı aşıyor', w['capacity'].cget('text'))
        state['shear'].set('8')
        state['tension'].set('100')
        self.assertIsNone(self.app.bolt_result.shear_limit_with_tension_n)
        self.assertIn('kesme sınırı: yok; çekme tek başına sınırı aşıyor', w['capacity'].cget('text'))
