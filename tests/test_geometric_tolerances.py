import csv
import unittest
from decimal import Decimal
from math import atan2, cos, degrees, hypot, radians
from unittest.mock import patch

import customtkinter as ctk
from support.gui import GuiTestCase

from geometric_tolerances.catalog import (
    ACTIVE,
    CATALOG,
    CHARACTERISTICS,
    GUIDE,
    MEASUREMENT_INPUTS,
)
from geometric_tolerances.rules import DATUM_CHOICES, fmt, fmt_mm, specify
from gui.theme import INPUT
from pdf.settings import load_settings, save_settings


class GeometricRulesTests(unittest.TestCase):
    def test_asme_mm_frame_keeps_leading_zero_and_exact_decimal_point(self):
        for raw, expected in [('0,000001', '0.000001'), ('0.050000', '0.05'),
                              ('1.000000', '1'), ('999.999999', '999.999999'), ('1000', '1000')]:
            with self.subTest(value=raw):
                spec = specify('position', '50', raw, 'A | B | C')
                self.assertEqual(fmt_mm(spec.tolerance), expected)
                self.assertEqual(spec.frame, f'Konum | ⌀{expected} | A | B | C')

    def test_position_independent_pythagorean_examples_use_diametral_error(self):
        # Exact 3-4-5 triangle; the GUI input is the evaluated diameter error.
        for dx, dy, t, expected in [('0.015', '0.020', '0.05', True),
                                    ('0.018', '0.024', '0.05', False),
                                    ('-0.018', '0.024', '0.06', True)]:
            with self.subTest(dx=dx, dy=dy, t=t):
                radial = (Decimal(dx)**2+Decimal(dy)**2).sqrt()
                spec = specify('position', '50', t, measured=str(2*radial))
                self.assertEqual(spec.accepted, expected)
                self.assertEqual(4*(Decimal(dx)**2+Decimal(dy)**2) <= Decimal(t)**2, expected)

    def test_centered_profile_uses_absolute_normal_deviation_not_peak_to_peak(self):
        for key in ('line_profile', 'surface_profile'):
            for deviations, equivalent, accepted in [
                (('0.01', '0.04'), '0.08', False),
                (('-0.025', '0.025'), '0.05', True),
                (('-0.025001', '0.001'), '0.050002', False)]:
                with self.subTest(key=key, deviations=deviations):
                    points = tuple(Decimal(point) for point in deviations)
                    total = 2*max(map(abs, points))
                    self.assertEqual(total, Decimal(equivalent))
                    spec = specify(key, '50', '0.05', measured=str(total))
                    self.assertEqual(spec.accepted, accepted)
                    self.assertEqual(all(abs(point) <= Decimal('0.025') for point in points), accepted)
        self.assertEqual(set(MEASUREMENT_INPUTS), {item.key for item in ACTIVE})

    def test_radial_form_width_and_runout_tir_are_not_doubled(self):
        for key in ('circularity', 'cylindricity', 'circular_runout', 'total_runout'):
            with self.subTest(key=key):
                # Evaluated bounding radii share an axis; radial width is 0.05.
                width = Decimal('25.025')-Decimal('24.975')
                self.assertEqual(width, Decimal('0.05'))
                self.assertTrue(specify(key, '50', '0.05', measured=str(width)).accepted)
                self.assertFalse(specify(key, '50', '0.05', measured='0.050001').accepted)

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
        self.assertEqual(spec.frame, 'Konum | ⌀0.05 | A | B | C')
        self.assertIn('unrelated AME', spec.characteristic.zone)
        with self.assertRaisesRegex(ValueError, 'datum referansı'):
            specify('position', '100', '0.05', 'Yok')
        self.assertIn('5.9.1', GUIDE)
        self.assertIn('5.9.2', GUIDE)
        self.assertIn('RFS/RMB aynı kavram değildir', GUIDE)

    def test_total_width_is_not_plus_minus_or_a_general_grade(self):
        spec = specify('cylindricity', '100', '0,3')
        self.assertEqual(spec.tolerance, Decimal('0.3'))
        self.assertEqual(spec.frame, 'Silindiriklik | 0.3')
        self.assertNotIn('±', spec.frame)
        self.assertEqual(spec.datums, ())
        self.assertEqual(spec.tolerance, specify('cylindricity', '500', '0,3').tolerance)
        self.assertIn('f/m/c/v', GUIDE)
        self.assertIn('geometrik değer türetilmez', GUIDE)

    def test_cylindrical_position_region_is_diameter_not_radius(self):
        spec = specify('position', '50', '0,3', 'A | B | C')
        self.assertEqual(spec.frame, 'Konum | ⌀0.3 | A | B | C')
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


class GeometricGuiTests(GuiTestCase):
    settle_seconds = .23

    def open_page(self):
        self.app.nav_buttons['geometric_tolerances'].invoke()
        self.settle()

    def test_angularity_draws_45_degrees_with_perpendicular_width(self):
        self.open_page()
        self.app._select_gdt('angularity')
        canvas = self.app.gdt_widgets['canvas']
        boundaries = [canvas.coords(item) for item in canvas.find_withtag('angle-boundary')]
        self.assertEqual(len(boundaries), 2)
        x1, y1, x2, y2 = boundaries[0]
        direction = (x2-x1, y2-y1)
        self.assertAlmostEqual(abs(degrees(atan2(direction[1], direction[0]))), 45)
        arrow = canvas.coords(canvas.find_withtag('dimension')[0])
        normal = (arrow[2]-arrow[0], arrow[3]-arrow[1])
        self.assertAlmostEqual(direction[0]*normal[0]+direction[1]*normal[1], 0)
        # Both arrow endpoints actually belong to their boundary lines.
        for point, edge in zip((arrow[:2], arrow[2:]), boundaries):
            self.assertAlmostEqual((point[0]-edge[0])*direction[1]-(point[1]-edge[1])*direction[0], 0)

    def test_position_diameter_arrow_reaches_both_cylinder_boundaries(self):
        self.open_page()
        self.app._select_gdt('position')
        canvas = self.app.gdt_widgets['canvas']
        circle = next(item for item in canvas.find_withtag('zone') if canvas.type(item) == 'oval')
        left, top, right, bottom = canvas.coords(circle)
        ax, ay, bx, by = canvas.coords(canvas.find_withtag('dimension')[0])
        self.assertAlmostEqual(ax, (left+right)/2)
        self.assertAlmostEqual(bx, ax)
        self.assertAlmostEqual(ay, top)
        self.assertAlmostEqual(by, bottom)
        self.assertAlmostEqual(by-ay, right-left)

    def test_profile_boundaries_are_centered_normal_offsets_and_arrow_meets_them(self):
        self.open_page()
        for kind in ('line_profile', 'surface_profile'):
            with self.subTest(kind=kind):
                self.app._select_gdt(kind)
                canvas = self.app.gdt_widgets['canvas']
                lines = [canvas.coords(item) for item in canvas.find_withtag('profile-boundary')]
                true = canvas.coords(canvas.find_withtag('true-profile')[0])
                arrow = canvas.coords(canvas.find_withtag('dimension')[0])
                # Symmetry axis determined from the drawn curve, not a fixture coordinate.
                center_x = (true[0]+true[-2])/2
                # Arc endpoints are at 20 and 160 degrees; central vertex is at 90.
                mid = len(true)//4*2
                radius = (true[0]-center_x)/cos(radians(20))
                center_y = true[mid+1]+radius
                width = hypot(arrow[2]-arrow[0], arrow[3]-arrow[1])
                for index in range(0, len(true), 2):
                    radii = [hypot(points[index]-center_x, points[index+1]-center_y) for points in lines]
                    actual = hypot(true[index]-center_x, true[index+1]-center_y)
                    self.assertAlmostEqual(radii[1]-radii[0], width)
                    self.assertAlmostEqual((radii[0]+radii[1])/2, actual)
                boundary_tops = sorted(points[mid+1] for points in lines)
                self.assertAlmostEqual(arrow[1], boundary_tops[0])
                self.assertAlmostEqual(arrow[3], boundary_tops[1])
                self.assertIn('Normal sınır: ±0,025 mm', self.app.gdt_widgets['value'].cget('text'))

    def test_long_frame_numbers_fit_cells_and_canvas_at_three_scales(self):
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        self.open_page()
        for scale in (1, 1.25, 1.5):
            ctk.set_widget_scaling(scale)
            self.settle(1.05)
            self.app.geometry('1000x690+0+0' if scale == 1 else '1920x1080+0+0')
            for theme in ('Açık', 'Koyu'):
                self.app._change_theme(theme)
                self.app._select_gdt('position')
                self.app.gdt_state['datum'].set('A | B | C')
                for value in ('0,000001', '999,999999', '1000'):
                    with self.subTest(scale=scale, theme=theme, value=value):
                        self.app.gdt_state['tolerance'].set(value)
                        self.settle(.05)
                        canvas = self.app.gdt_widgets['frame']
                        cells = canvas.find_withtag('frame-cell')
                        self.assertEqual(len(cells), 5)
                        cell = canvas.coords(cells[1])
                        box = canvas.bbox(canvas.find_withtag('frame-number')[0])
                        self.assertGreaterEqual(box[0], cell[0]+5*scale)
                        self.assertLessEqual(box[2], cell[2]-5*scale)
                        self.assertGreaterEqual(box[1], cell[1])
                        self.assertLessEqual(box[3], cell[3])
                        whole = canvas.bbox('frame')
                        self.assertGreaterEqual(whole[0], 0)
                        self.assertLessEqual(whole[2], canvas.winfo_width())

    def test_measurement_definition_and_half_width_export_follow_feature(self):
        self.open_page()
        for item in ACTIVE:
            with self.subTest(kind=item.key):
                self.app._select_gdt(item.key)
                help_text = self.app.gdt_widgets['measured_help'].cget('text')
                self.assertEqual(help_text, MEASUREMENT_INPUTS[item.key])
                report = dict(self.app._gdt_report_rows())
                self.assertEqual(report['Ölçüm girişinin anlamı'], help_text)
                expected = '0,025' if item.diametrical or item.group == 'Profil' else ''
                self.assertEqual(report['Merkezlenmiş bölge yarı payı (mm)'], expected)
        self.app._select_gdt('position')
        self.app.gdt_state['measured'].set('0,06')
        self.assertIn('sınır dışında', self.app.gdt_widgets['assessment'].cget('text'))
        self.assertIn('radyal sapmayı doğrudan girmeyin', self.app.gdt_widgets['measured_help'].cget('text'))
        self.app._select_gdt('surface_profile')
        self.app.gdt_state['measured'].set('0,08')
        self.assertIn('sınır dışında', self.app.gdt_widgets['assessment'].cget('text'))
        self.assertIn('maksimum - minimum farkı yeterli değildir', self.app.gdt_widgets['measured_help'].cget('text'))

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
                                       self.app.gdt_widgets['listing']._parent_canvas, left=1, mapped=True)

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
        self.assertIn('Konum | ⌀0.3 | A | B | C', clipboard)
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
        self.open_app()
        self.open_page()
        self.assertEqual(self.app.gdt_result.tolerance, Decimal('0.03'))
        self.assertIsNone(self.app.gdt_result.measured)

    def test_corrupt_saved_choices_fall_back_but_invalid_numeric_values_are_visible(self):
        self.app._on_close()
        save_settings({'gdt_kind': 'unknown', 'gdt_datum': 'A | A', 'gdt_tolerance': 'NaN'}, self.settings)
        self.open_app()
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
                        self.assert_inside(widget, self.app, left=1, mapped=True)
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
                        self.assert_inside(field, viewport, left=1, mapped=True)
                    self.app.gdt_widgets['listing']._parent_canvas.yview_moveto(1)
                    self.app.update()
                    self.assert_inside(self.app.gdt_widgets['choices']['total_runout'], self.app.gdt_widgets['listing']._parent_canvas, left=1, mapped=True)


if __name__ == '__main__':
    unittest.main()
