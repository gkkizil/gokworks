import csv
from decimal import Decimal
import os
import time
import unittest
from unittest.mock import patch

import customtkinter as ctk

import test_export_window as fixtures
from geometric_tolerances.catalog import CATALOG, CHARACTERISTICS, GUIDE, ACTIVE
from geometric_tolerances.rules import DATUM_CHOICES, fmt, specify
from gui.theme import INPUT
from pdf.settings import load_settings, save_settings


class GeometricRulesTests(unittest.TestCase):
    def test_asme_2018_has_twelve_active_and_two_deleted_characteristics(self):
        self.assertEqual(len(ACTIVE), 12)
        self.assertEqual({item.key for item in CATALOG if not item.active}, {'concentricity', 'symmetry'})
        for key in ('concentricity', 'symmetry'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'ASME Y14.5-2018'):
                specify(key, '100', '0.05')
        self.assertTrue(all(item.reference for item in CATALOG))
        self.assertIn('Ek D', GUIDE)

    def test_surface_form_must_be_less_than_associated_size_tolerance(self):
        for key in ('straightness', 'flatness', 'circularity', 'cylindricity'):
            with self.subTest(key=key):
                spec = specify(key, '100', '0,05', size_tolerance='0,050001')
                self.assertEqual(spec.size_tolerance, Decimal('0.050001'))
                for size_t in ('0.05', '0.049999', '0', 'NaN'):
                    with self.subTest(size_t=size_t), self.assertRaises(ValueError):
                        specify(key, '100', '0.05', size_tolerance=size_t)
                self.assertIsNone(specify(key, '100', '0.05').size_tolerance)
        # Cached form input does not create a size relationship on profile/runout.
        self.assertIsNone(specify('surface_profile', '100', '0.05', size_tolerance='0.01').size_tolerance)

    def test_default_rfs_rmb_has_no_material_modifiers_and_position_example_requires_datum(self):
        spec = specify('position', '100', '0.05', 'A | B | C')
        self.assertEqual(spec.frame, 'Konum | ⌀0,05 | A | B | C')
        self.assertIn('unrelated AME', spec.characteristic.zone)
        with self.assertRaisesRegex(ValueError, 'datum referansı'):
            specify('position', '100', '0.05', 'Yok')
        self.assertIn('5.9.1', GUIDE)
        self.assertIn('5.9.2', GUIDE)
        self.assertIn('RFS/RMB aynı kavram değildir', GUIDE)

    def test_total_width_is_not_plus_minus_or_a_general_grade(self):
        spec = specify('cylindricity', '100', '0,3')
        self.assertEqual(spec.tolerance, Decimal('0.3'))
        self.assertEqual(spec.frame, 'Silindiriklik | 0,3')
        self.assertNotIn('±', spec.frame)
        self.assertEqual(spec.datums, ())
        self.assertEqual(spec.tolerance, specify('cylindricity', '500', '0,3').tolerance)
        self.assertIn('f/m/c/v', GUIDE)
        self.assertIn('geometrik değer türetilmez', GUIDE)

    def test_cylindrical_position_region_is_diameter_not_radius(self):
        spec = specify('position', '50', '0,3', 'A | B | C')
        self.assertEqual(spec.frame, 'Konum | ⌀0,3 | A | B | C')
        self.assertEqual(spec.tolerance/2, Decimal('0.15'))
        self.assertEqual(spec.datums, ('A', 'B', 'C'))
        self.assertIn('t/2', spec.characteristic.zone)

    def test_form_ignores_cached_datums_optional_and_required_are_distinct(self):
        for item in CATALOG:
            with self.subTest(kind=item.key):
                if not item.active:
                    with self.assertRaisesRegex(ValueError, 'kaldırıldı'):
                        specify(item.key, '100', '0.05')
                    continue
                for datum in DATUM_CHOICES:
                    if datum == 'Yok' and item.datum == 'required':
                        with self.assertRaisesRegex(ValueError, 'datum referansı'):
                            specify(item.key, '100', '0.05', datum)
                    else:
                        spec = specify(item.key, '100', '0.05', datum)
                        expected = () if item.datum == 'none' or datum == 'Yok' else tuple(datum.split(' | '))
                        self.assertEqual(spec.datums, expected)
        for datum in ('A | A', 'B | A', 'A||B', 'Z', None):
            with self.subTest(datum=datum), self.assertRaises(ValueError):
                specify('parallelism', '100', '0.05', datum)

    def test_error_comparison_equal_and_one_nanometre_above_limit(self):
        for measured, expected, margin in [('0', True, '0.05'), ('0.049999', True, '0.000001'),
                                           ('0.050000', True, '0'), ('0.050001', False, '-0.000001')]:
            with self.subTest(measured=measured):
                spec = specify('flatness', '100', '0.05', measured=measured)
                self.assertIs(spec.accepted, expected)
                self.assertEqual(spec.margin, Decimal(margin))
        absent = specify('flatness', '100', '0.05')
        self.assertIsNone(absent.accepted)
        self.assertIsNone(absent.margin)

    def test_invalid_inputs_do_not_create_a_specification(self):
        for key in ('size', 'tolerance', 'measured'):
            for value in ('', '-0.01', 'NaN', 'Infinity', '1e-2', '0.0000001', '0,0.5', True, '10001'):
                if key == 'measured' and value == '':
                    continue
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    args = dict(key='position', size='50', tolerance='0.05', measured='')
                    args[key] = value
                    specify(**args)
        for key in ('size', 'tolerance'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                args = dict(key='flatness', size='100', tolerance='0.05')
                args[key] = '0'
                specify(**args)
        for key in ('bad', None):
            with self.assertRaises(ValueError):
                specify(key, '100', '.05')

    def test_limits_and_decimal_display_have_no_implicit_rounding(self):
        spec = specify('circularity', '0.000001', '+0,000001', measured='0.000001')
        self.assertEqual(fmt(spec.tolerance), '0,000001')
        self.assertEqual(fmt(Decimal('-0.000001')), '-0,000001')
        self.assertEqual(fmt(specify('flatness', '10000', '1000').size), '10000')
        with self.assertRaises(ValueError):
            specify('flatness', '10000.000001', '0.05')
        with self.assertRaises(ValueError):
            specify('flatness', '100', '1000.000001')

    def test_catalog_distinguishes_form_runout_and_theoretical_dimensions(self):
        self.assertEqual(len(CATALOG), 14)
        self.assertEqual(len(CHARACTERISTICS), 14)
        self.assertEqual({i.key for i in CATALOG if i.datum == 'none'},
                         {'straightness', 'flatness', 'circularity', 'cylindricity'})
        self.assertIn('radyal mesafe', CHARACTERISTICS['cylindricity'].zone)
        self.assertIn('basit toplamı değildir', CHARACTERISTICS['cylindricity'].note)
        self.assertIn('Kesitler ayrı', CHARACTERISTICS['circular_runout'].zone)
        self.assertIn('bağımsız sıfırlanmaz', CHARACTERISTICS['total_runout'].zone)
        self.assertIn('teorik 45°', CHARACTERISTICS['angularity'].zone)
        self.assertIn('Rule #1', GUIDE)
        self.assertIn('Rule #2', GUIDE)
        self.assertIn("CAD'e yazılmaz", GUIDE)
        for item in CATALOG:
            with self.subTest(kind=item.key):
                self.assertTrue(all((item.description, item.zone, item.measurement, item.note, item.example)))


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'GUI requires a display')
class GeometricGuiTests(unittest.TestCase):
    setUp = fixtures.WindowTests.setUp
    close_app = fixtures.WindowTests.close_app

    def settle(self, seconds=.23):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            self.app.update()
            time.sleep(.005)

    def open_page(self):
        self.app.nav_buttons['geometric_tolerances'].invoke()
        self.settle()

    def test_deleted_symbols_are_educational_only_and_cannot_export_a_current_frame(self):
        self.open_page()
        for key in ('concentricity', 'symmetry'):
            with self.subTest(key=key):
                self.app.gdt_widgets['choices'][key].invoke()
                self.assertIsNone(self.app.gdt_result)
                self.assertEqual(self.app.gdt_widgets['value'].cget('text'), '2018’de kaldırıldı')
                for field in ('size', 'tolerance', 'datum', 'measured', 'copy', 'export'):
                    self.assertEqual(self.app.gdt_widgets[field].cget('state'), 'disabled')
                self.assertEqual(self.app._gdt_report_rows(), [])
                self.assertFalse(self.app.gdt_widgets['frame'].find_withtag('frame'))
        self.app._select_gdt('cylindricity')
        self.assertIsNotNone(self.app.gdt_result)
        self.assertEqual(self.app.gdt_widgets['tolerance'].cget('state'), 'normal')

    def test_rule_one_surface_size_relation_blocks_export_and_clears_on_feature_change(self):
        self.open_page()
        self.app.gdt_state['size_tolerance'].set('0.05')
        self.assertIsNone(self.app.gdt_result)
        self.assertIn('ASME 8.4', self.app.status_label.cget('text'))
        self.assertEqual(self.app.gdt_widgets['export'].cget('state'), 'disabled')
        self.app.gdt_state['size_tolerance'].set('0.1')
        self.assertIsNotNone(self.app.gdt_result)
        self.assertIn('t < 0,1 mm', self.app.gdt_widgets['assessment'].cget('text'))
        self.assertEqual(dict(self.app._gdt_report_rows())['İlgili boyut toleransı (mm)'], '0,1')
        self.app._select_gdt('flatness')
        self.assertEqual(self.app.gdt_state['size_tolerance'].get(), '')
        self.assertIn('Rule #1', self.app.gdt_widgets['assessment'].cget('text'))

    def assert_inside(self, child, parent):
        self.assertTrue(child.winfo_ismapped())
        self.assertGreaterEqual(child.winfo_rootx(), parent.winfo_rootx()-1)
        self.assertGreaterEqual(child.winfo_rooty(), parent.winfo_rooty()-1)
        self.assertLessEqual(child.winfo_rootx()+child.winfo_width(), parent.winfo_rootx()+parent.winfo_width()+1)
        self.assertLessEqual(child.winfo_rooty()+child.winfo_height(), parent.winfo_rooty()+parent.winfo_height()+1)

    def test_all_fourteen_buttons_draw_zones_symbols_and_frames_in_both_themes(self):
        self.open_page()
        for appearance in ('Açık', 'Koyu'):
            self.app._change_theme(appearance)
            for item in CATALOG:
                with self.subTest(theme=appearance, kind=item.key):
                    self.app.gdt_widgets['choices'][item.key].invoke()
                    self.settle(.04)
                    if not item.active:
                        self.assertIsNone(self.app.gdt_result)
                        for key in ('frame', 'canvas'):
                            self.assertTrue(self.app.gdt_widgets[key].find_withtag('legacy'))
                        self.assertEqual(self.app.gdt_widgets['export'].cget('state'), 'disabled')
                        self.assertEqual(self.app.gdt_widgets['size'].cget('state'), 'disabled')
                        continue
                    self.assertEqual(self.app.gdt_result.characteristic, item)
                    self.assertEqual(self.app.gdt_widgets['title'].cget('text'), item.name)
                    for key, tag in [('canvas', 'zone'), ('frame', 'frame'), ('symbol', 'symbol')]:
                        canvas = self.app.gdt_widgets[key]
                        self.assertTrue(canvas.find_withtag(tag))
                        self.assertEqual(canvas.cget('background'), INPUT[1 if appearance == 'Koyu' else 0])
                    state = self.app.gdt_widgets['datum'].cget('state')
                    self.assertEqual(state, 'disabled' if item.datum == 'none' else 'normal')
                    self.assertEqual(self.app.gdt_widgets['datum'].get(), 'Gerekmez' if item.datum == 'none' else 'A')
                    self.assertEqual(self.app.gdt_widgets['export'].cget('state'), 'normal')
                    self.assert_inside(self.app.gdt_widgets['choices'][item.key],
                                       self.app.gdt_widgets['listing']._parent_canvas)

    def test_no_stale_result_on_invalid_tolerance_or_measured_error(self):
        self.open_page()
        for key in ('tolerance', 'size', 'measured'):
            with self.subTest(key=key):
                old = self.app.gdt_state[key].get()
                self.app.gdt_state[key].set('-0.05')
                self.assertIsNone(self.app.gdt_result)
                self.assertFalse(self.app.gdt_widgets['canvas'].find_withtag('zone'))
                self.assertFalse(self.app.gdt_widgets['frame'].find_withtag('frame'))
                for control in ('copy', 'export'):
                    self.assertEqual(self.app.gdt_widgets[control].cget('state'), 'disabled')
                self.assertEqual(self.app._gdt_report_rows(), [])
                self.app.gdt_state[key].set(old)
                self.assertIsNotNone(self.app.gdt_result)

    def test_real_datum_dropdown_and_required_reference_error(self):
        self.open_page()
        self.app.gdt_widgets['choices']['parallelism'].invoke()
        menu = self.app.gdt_widgets['datum']
        for index, value in enumerate(DATUM_CHOICES):
            with self.subTest(datum=value):
                menu._dropdown_menu.invoke(index)
                self.assertEqual(self.app.gdt_state['datum'].get(), value)
                if value == 'Yok':
                    self.assertIsNone(self.app.gdt_result)
                    self.assertIn('datum referansı', self.app.status_label.cget('text'))
                else:
                    self.assertEqual(self.app.gdt_result.datums, tuple(value.split(' | ')))
        self.app.gdt_widgets['choices']['line_profile'].invoke()
        menu._dropdown_menu.invoke(0)
        self.assertEqual(self.app.gdt_result.datums, ())

    def test_measured_comparison_clears_when_feature_changes(self):
        self.open_page()
        self.app.gdt_state['measured'].set('0,05')
        self.assertIn('tam sınırda', self.app.gdt_widgets['assessment'].cget('text'))
        self.app.gdt_state['measured'].set('0,050001')
        self.assertIn('sınır dışında', self.app.gdt_widgets['assessment'].cget('text'))
        self.assertIn('-0,000001', self.app.gdt_widgets['assessment'].cget('text'))
        self.app.gdt_widgets['choices']['flatness'].invoke()
        self.assertEqual(self.app.gdt_state['measured'].get(), '')
        self.assertIn('Ölçüm girilmedi', self.app.gdt_widgets['assessment'].cget('text'))

    def test_search_filter_empty_state_and_keyboard_focus(self):
        self.open_page()
        for query, expected in [('SİLİNDİR', ['cylindricity']), ('Run-out', ['circular_runout', 'total_runout']),
                                ('olmayan', []), ('', list(CHARACTERISTICS))]:
            with self.subTest(query=query):
                self.app.gdt_search.set(query)
                visible = [key for key, widget in self.app.gdt_widgets['choices'].items() if widget.grid_info()]
                self.assertEqual(visible, expected)
        self.app.focus_force()
        self.app.event_generate('<Control-f>')
        self.app.update()
        self.assertIn('entry', str(self.app.focus_get()))

    def test_csv_copy_cancel_and_save_error_use_current_specification(self):
        self.open_page()
        self.app.gdt_widgets['choices']['position'].invoke()
        self.app.gdt_state['tolerance'].set('0,3')
        self.app.gdt_state['datum'].set('A | B | C')
        self.app.gdt_state['measured'].set('0.05')
        self.app._copy_gdt_report()
        clipboard = self.app.clipboard_get()
        self.assertIn('Konum | ⌀0,3 | A | B | C', clipboard)
        self.assertIn('ASME Y14.5-2018', clipboard)
        self.assertIn('RFS / datum boyut özelliğinde RMB', clipboard)
        path = self.root/'gdt.csv'
        with patch('geometric_tolerances.window.filedialog.asksaveasfilename', return_value=str(path)):
            self.app.gdt_widgets['export'].invoke()
        with path.open(encoding='utf-8-sig', newline='') as stream:
            rows = dict(list(csv.reader(stream, delimiter=';'))[1:])
        self.assertEqual(rows['Toplam tolerans t (mm)'], '0,3')
        self.assertEqual(rows['Bölge değerinin anlamı'], 'Çap')
        self.assertEqual(rows['Datum sırası'], 'A | B | C')
        before = path.read_bytes()
        with patch('geometric_tolerances.window.filedialog.asksaveasfilename', return_value=''):
            self.app._save_gdt_report()
        self.assertEqual(path.read_bytes(), before)
        with patch('geometric_tolerances.window.filedialog.asksaveasfilename', return_value=str(self.root/'missing'/'gdt.csv')):
            self.app._save_gdt_report()
        self.assertIn('CSV kaydedilemedi', self.app.status_label.cget('text'))

    def test_page_cache_preferences_theme_and_guide(self):
        self.app.source_folder.set('/pdf/source')
        self.open_page()
        workspace = self.app.workspace
        self.app.gdt_widgets['choices']['position'].invoke()
        self.app.gdt_state['tolerance'].set('0.03')
        self.app.gdt_state['datum'].set('A | B')
        self.app.gdt_state['measured'].set('0.02')
        for mode in ('pdf', 'dxf_dwg', 'k_factor', 'iso_fits'):
            self.app._switch_mode(mode)
            self.app._change_theme('Koyu')
            self.app._switch_mode('geometric_tolerances')
            self.assertIs(self.app.workspace, workspace)
            self.assertEqual(self.app.gdt_result.tolerance, Decimal('0.03'))
            self.assertEqual(self.app.gdt_result.measured, Decimal('0.02'))
            self.assertEqual(self.app.gdt_widgets['canvas'].cget('background'), INPUT[1])
        self.app._show_gdt_guide()
        self.app.update()
        self.assertIn('5.8.1', self.app.gdt_widgets['guide_text'].get('1.0', 'end'))
        self.assertEqual(self.app.gdt_widgets['guide_text'].cget('state'), 'disabled')
        self.app._close_detail()
        self.app._save_preferences()
        saved = load_settings(self.settings)
        self.assertEqual(saved['gdt_kind'], 'position')
        self.assertEqual(saved['gdt_datum'], 'A | B')
        self.assertNotIn('gdt_measured', saved)
        self.assertEqual(saved['pdf_source'], '/pdf/source')
        self.assertEqual(saved['unrelated_setting'], 'keep')
        self.app._on_close()
        self.app = fixtures.GokworksPdfApp(settings_path=self.settings)
        self.app.report_callback_exception = lambda *args: self.errors.append(args)
        self.open_page()
        self.assertEqual(self.app.gdt_result.tolerance, Decimal('0.03'))
        self.assertIsNone(self.app.gdt_result.measured)

    def test_corrupt_saved_choices_fall_back_but_invalid_numeric_values_are_visible(self):
        self.app._on_close()
        save_settings({'gdt_kind': 'unknown', 'gdt_datum': 'A | A', 'gdt_tolerance': 'NaN'}, self.settings)
        self.app = fixtures.GokworksPdfApp(settings_path=self.settings)
        self.app.report_callback_exception = lambda *args: self.errors.append(args)
        self.open_page()
        self.assertEqual(self.app.gdt_state['kind'].get(), 'cylindricity')
        self.assertEqual(self.app.gdt_state['datum'].get(), 'A')
        self.assertIsNone(self.app.gdt_result)
        self.assertIn('mm cinsinden sayı', self.app.status_label.cget('text'))

    def test_resolution_scale_matrix_scroll_access_and_circle_aspect(self):
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        self.open_page()
        cases = [('1000x690', 1), ('1240x860', 1), ('1366x768', 1),
                 ('1400x900', 1.25), ('1920x1080', 1.5)]
        for size, scale in cases:
            if self.app.workspace._get_widget_scaling() != scale:
                ctk.set_widget_scaling(scale)
                self.settle(1.05)
            self.app.geometry(size+'+0+0')
            for theme in ('Açık', 'Koyu'):
                with self.subTest(size=size, scale=scale, theme=theme):
                    self.app._change_theme(theme)
                    self.app.gdt_widgets['choices']['circularity'].invoke()
                    self.settle()
                    self.assertEqual(f'{self.app.winfo_width()}x{self.app.winfo_height()}', size)
                    for widget in [self.app.theme_selector, *self.app.nav_buttons.values(),
                                   self.app.gdt_widgets['export'], self.app.gdt_widgets['guide']]:
                        self.assert_inside(widget, self.app)
                    canvas = self.app.gdt_widgets['canvas']
                    for item in canvas.find_withtag('zone'):
                        if canvas.type(item) == 'oval':
                            x1, y1, x2, y2 = canvas.coords(item)
                            self.assertAlmostEqual(x2-x1, y2-y1, places=4)
                    details = self.app.gdt_widgets['details']
                    viewport = details._parent_canvas
                    for key in ('size', 'tolerance', 'datum', 'size_tolerance', 'measured', 'copy'):
                        viewport.yview_moveto(0)
                        self.app.update()
                        field = self.app.gdt_widgets[key]
                        distance = field.winfo_rooty()-details.winfo_rooty()
                        viewport.yview_moveto(max(0, distance-(viewport.winfo_height()-field.winfo_height())/2)/details.winfo_height())
                        self.app.update()
                        self.assert_inside(field, viewport)
                    self.app.gdt_widgets['listing']._parent_canvas.yview_moveto(1)
                    self.app.update()
                    self.assert_inside(self.app.gdt_widgets['choices']['total_runout'], self.app.gdt_widgets['listing']._parent_canvas)


if __name__ == '__main__':
    unittest.main()
