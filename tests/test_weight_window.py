"""Native material weight controls, conversions and cached workspace behavior."""

from contextlib import ExitStack
from unittest.mock import patch

import customtkinter as ctk

from pdf.settings import load_settings, save_settings
from support.gui import GuiTestCase
from weight.rules import FIELDS, KINDS, MATERIALS, MATERIAL_GROUPS


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
        self.assertNotIn('density', state)
        self.assertIn('2.700 kg/m³', w['density_label'].cget('text'))
        self.assertAlmostEqual(self.app.weight_result.mass_kg, 1.35)
        state['count'].set('3')
        self.assertAlmostEqual(self.app.weight_result.total_mass_kg, 4.05)
        state['material'].set('Paslanmaz')
        self.assertAlmostEqual(self.app.weight_result.total_mass_kg, 12)
        self.app._copy_weight_result()
        report = self.app.clipboard_get()
        self.assertIn('Ağırlık hesabı · Sac levha', report)
        self.assertIn('8.000,000 kg/m³', report)
        self.assertIn('Adet: 3', report)
        self.assertIn('12,000 kg', report)
        state['kind'].set('HEA')
        self.assertTrue(self.app.weight_result.approximate)
        self.assertIn('Katalog alanı', w['note'].cget('text'))

    def test_value_edits_keep_field_layout_while_kind_method_and_units_stay_current(self):
        state, w = self.app.weight_state, self.app.weight_widgets
        frames = (*w['dim_frames'].values(), w['area_frame'])

        def edit_without_layout(updates):
            with ExitStack() as stack:
                calls = [stack.enter_context(patch.object(frame, method, wraps=getattr(frame, method)))
                         for frame in frames for method in ('grid', 'grid_remove')]
                for key, value in updates.items():
                    state[key].set(value)
                self.app.update_idletasks()
                for call in calls:
                    call.assert_not_called()

        edit_without_layout(dict(b='120', t='6', length='2000', count='2',
                                 material='Alüminyum', unit='cm'))
        self.assertAlmostEqual(self.app.weight_result.total_mass_kg, 7.776)
        self.assertTrue(w['b_label'].cget('text').endswith('(cm)'))
        self.assertTrue(w['length_label'].cget('text').endswith('(cm)'))

        state['kind'].set('Boru')
        for key, frame in w['dim_frames'].items():
            self.assertEqual(frame.winfo_manager() == 'grid', key in FIELDS['Boru'])
        for index, key in enumerate(FIELDS['Boru']):
            self.assertEqual(w['dim_frames'][key].grid_info()['column'], index)
            self.assertTrue(w[key+'_label'].cget('text').endswith('(cm)'))
        self.assertFalse(w['area_frame'].winfo_manager())

        state['method'].set('Katalog alanından')
        self.assertEqual(w['area_frame'].winfo_manager(), 'grid')
        self.assertFalse(any(frame.winfo_manager() for frame in w['dim_frames'].values()))
        edit_without_layout(dict(area_cm2='12,5', count='3', material='Paslanmaz', unit='m'))
        self.assertAlmostEqual(self.app.weight_result.total_mass_kg, 60)
        self.assertTrue(w['length_label'].cget('text').endswith('(m)'))

        state['method'].set('Ölçülerden')
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        ctk.set_widget_scaling(1.25)
        self.app.update_idletasks()
        self.assertFalse(w['area_frame'].winfo_manager())
        for key, frame in w['dim_frames'].items():
            self.assertEqual(frame.winfo_manager() == 'grid', key in FIELDS['Boru'])
        for key in FIELDS['Boru']:
            self.assertTrue(w[key+'_label'].cget('text').endswith('(m)'))

    def test_units_preserve_inactive_dimensions_and_catalogue_mode_clears_invalid_results(self):
        state, w = self.app.weight_state, self.app.weight_widgets
        state['material'].set('Paslanmaz')
        state['count'].set('3')
        original = self.app.weight_result.total_mass_kg
        for unit in ('cm', 'm', 'mm'):
            state['unit'].set(unit)
            self.assertAlmostEqual(self.app.weight_result.total_mass_kg, original, places=8)
            self.assertEqual(self.app.weight_result.density, MATERIALS['Paslanmaz'])
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
        for key, bad in (('area_cm2', '0'), ('material', 'Tanımsız malzeme'), ('count', '1,5')):
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
        state['material'].set('C45')
        self.app._switch_mode('bolt')
        self.app._switch_mode('weight')
        self.assertIs(self.app.weight_widgets, w)
        self.assertEqual(state['kind'].get(), 'Boru')
        self.assertEqual(self.app._focus_search(), 'break')
        self.app._save_preferences()
        saved = load_settings(self.settings)
        self.assertEqual(saved['weight_kind'], 'Boru')
        self.assertEqual(saved['weight_material'], 'C45')
        self.assertNotIn('weight_density', saved)
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
        self.assertEqual(self.app.weight_result.density, MATERIALS['C45'])

    def test_material_groups_readonly_density_menu_selection_and_legacy_preferences(self):
        state, w = self.app.weight_state, self.app.weight_widgets
        self.assertNotIn('density', state)
        self.assertNotIn('density_input', w)
        self.assertIsInstance(w['density_label'], ctk.CTkLabel)
        state['material_group'].set('Sac / Yapı')
        self.assertEqual(state['material'].get(), MATERIAL_GROUPS['Sac / Yapı'][0])
        values = w['material_input'].cget('values')
        self.assertEqual(len(values), len(MATERIAL_GROUPS['Sac / Yapı']))
        self.assertTrue(all('g/cm³' in value for value in values))
        displayed = self.app._weight_material_text('DC01 (DKP)')
        w['material_input']._dropdown_callback(displayed)
        self.assertEqual(state['material'].get(), 'DC01 (DKP)')
        self.assertEqual(self.app.weight_result.density, MATERIALS['DC01 (DKP)'])
        state['material'].set('C45')
        self.assertEqual(state['material_group'].get(), 'Makine / Takım')
        self.assertEqual(w['material_display'].get(), self.app._weight_material_text('C45'))
        state['material'].set('DX51D+Z')
        self.assertIn('Çinko kaplaması dahil değildir.', w['note'].cget('text'))
        state['unit'].set('m')
        self.assertEqual(self.app.weight_result.density, MATERIALS['DX51D+Z'])
        self.app._copy_weight_result()
        report = self.app.clipboard_get()
        self.assertIn('Malzeme: DX51D+Z', report)
        self.assertIn('Çinko kaplaması dahil değildir.', report)
        self.assertIn('Yoğunluk kaynağı:', report)
        self.close_app()
        save_settings({'weight_material': 'DX51D+Z', 'weight_material_group': 'Genel',
                       'weight_density': '1', 'unrelated_setting': 'keep'}, self.settings)
        self.open_app()
        self.app._switch_mode('weight')
        self.assertNotIn('density', self.app.weight_state)
        self.assertEqual(self.app.weight_state['material_group'].get(), 'Sac / Yapı')
        self.assertEqual(self.app.weight_result.density, MATERIALS['DX51D+Z'])
        self.app._save_preferences()
        self.assertNotIn('weight_density', load_settings(self.settings))
