"""GUI'nin kullanıcı kontrolleri üzerinden tamamlayıcı kabul testleri."""

import csv
import os
from pathlib import Path
from threading import Event
import time
import unittest
from unittest.mock import patch

import customtkinter as ctk
from tkinter import ttk

import test_export_window as window_tests
from pdf.settings import load_settings


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'GUI requires a display')
class GUIAuditTests(unittest.TestCase):
    setUp = window_tests.WindowTests.setUp
    close_app = window_tests.WindowTests.close_app
    wait_idle = window_tests.WindowTests.wait_idle

    def settle(self):
        self.app.update()
        deadline = time.monotonic() + 2
        while self.app._layout_fit_id is not None and time.monotonic() < deadline:
            self.app.update()
            time.sleep(.01)
        self.app.update()

    def test_browse_buttons_choose_and_cancel_in_both_modules(self):
        for mode in ('pdf', 'dxf_dwg'):
            self.app.nav_buttons[mode].invoke()
            extension = '.slddrw' if mode == 'pdf' else '.sldprt'
            selected = self.root/'Türkçe kaynak'/f'Örnek{extension}'
            selected.parent.mkdir(exist_ok=True)
            selected.touch()
            output = self.root/'Çıktılar'
            output.mkdir(exist_ok=True)
            browse = [control for control in self.app.controls if isinstance(control, ctk.CTkButton)
                      and control.cget('text') == 'Gözat']
            with patch('pdf.window.filedialog.askopenfilename', return_value=str(selected)) as picker:
                browse[0].invoke()
            self.assertEqual(self.app.source_folder.get(), str(selected.parent))
            self.assertEqual(picker.call_args.kwargs['filetypes'][0][1], f'*{extension}')
            with patch('pdf.window.filedialog.askdirectory', return_value=str(output)):
                browse[1].invoke()
            self.assertEqual(self.app.output_folder.get(), str(output))
            with patch('pdf.window.filedialog.askopenfilename', return_value=''), patch('pdf.window.filedialog.askdirectory', return_value=''):
                browse[0].invoke()
                browse[1].invoke()
            self.assertEqual(self.app.source_folder.get(), str(selected.parent))
            self.assertEqual(self.app.output_folder.get(), str(output))

    def test_theme_selector_buttons_apply_and_save_choice(self):
        for label, mode in (('Koyu', 'Dark'), ('Açık', 'Light')):
            self.app.theme_selector._buttons_dict[label].invoke()
            self.app.update()
            self.assertEqual(ctk.get_appearance_mode(), mode)
            self.assertEqual(self.app.theme_mode.get(), label)
            self.assertEqual(load_settings(self.settings)['appearance'], mode.lower())
            self.assertTrue(ttk.Style(self.app).lookup('Gok.Treeview', 'background'))

    def test_dxf_option_widgets_and_start_button_reach_worker(self):
        self.app.nav_buttons['dxf_dwg'].invoke()
        (self.root/'part.sldprt').touch()
        self.app.source_folder.set(str(self.root))
        self.app.output_folder.set(str(self.root/'outputs'))
        formats = next(control for control in self.app.controls if isinstance(control, ctk.CTkSegmentedButton))
        self.assertEqual(formats.cget('values'), ['DXF', 'DWG'])
        formats._buttons_dict['DWG'].invoke()
        checkboxes = [control for control in self.app.controls if isinstance(control, ctk.CTkCheckBox)]
        for control in checkboxes:
            control.toggle()
        captured = {}
        def worker(source, output, recursive, overwrite, events, stop, **options):
            captured.update(source=source, output=output, recursive=recursive,
                            overwrite=overwrite, **options)
            events.put(('done', {'state': 'completed', 'total': 0, 'processed': 0,
                                'succeeded': 0, 'skipped': 0, 'failed': 0, 'error': ''}))
        with patch('pdf.window.export_parts', side_effect=worker):
            self.app.start_button.invoke()
            self.wait_idle()
        self.assertEqual(captured['formats'], ('dwg',))
        self.assertTrue(captured['bend_lines'])
        self.assertFalse(captured['recursive'])
        self.assertTrue(captured['overwrite'])
        self.assertEqual(self.app.start_button.cget('state'), 'normal')

    def test_scan_stop_button_and_disabled_navigation(self):
        self.app.nav_buttons['dxf_dwg'].invoke()
        self.app.source_folder.set(str(self.root))
        entered, proceed = Event(), Event()
        path = str(self.root/'part.sldprt')
        def scan(source, recursive, stop):
            entered.set()
            proceed.wait(3)
            return [path]
        with patch('pdf.window.find_parts', side_effect=scan):
            self.app.scan_button.invoke()
            try:
                self.assertTrue(entered.wait(1))
                self.app.nav_buttons['pdf'].invoke()
                self.assertEqual(self.app.mode, 'dxf_dwg')
                self.assertEqual(self.app.start_button.cget('state'), 'disabled')
                self.app.stop_button.invoke()
                self.assertTrue(self.app.stop_event.is_set())
                self.assertEqual(self.app.stop_button.cget('state'), 'disabled')
                self.assertTrue(self.app.busy)
            finally:
                proceed.set()
                self.wait_idle()
        self.assertIn('durduruldu', self.app.status_label.cget('text').lower())
        self.assertEqual(self.app.nav_buttons['pdf'].cget('state'), 'normal')

    def test_declining_close_keeps_worker_and_window_alive(self):
        (self.root/'drawing.slddrw').touch()
        self.app.source_folder.set(str(self.root))
        self.app.output_folder.set(str(self.root/'outputs'))
        entered, proceed = Event(), Event()
        def worker(source, output, recursive, overwrite, events, stop):
            entered.set()
            proceed.wait(3)
            events.put(('done', {'state': 'completed', 'total': 0, 'processed': 0,
                                'succeeded': 0, 'skipped': 0, 'failed': 0, 'error': ''}))
        with patch('pdf.window.export_drawings', side_effect=worker):
            self.app.start_button.invoke()
            try:
                self.assertTrue(entered.wait(1))
                with patch('pdf.window.messagebox.askyesno', return_value=False):
                    self.app._on_close()
                self.assertFalse(self.app._closed)
                self.assertFalse(self.app.close_pending)
                self.assertFalse(self.app.stop_event.is_set())
                self.assertTrue(self.app.busy)
            finally:
                proceed.set()
                self.wait_idle()
        self.assertTrue(self.app.winfo_exists())

    def test_filtered_csv_report_button_still_writes_all_results(self):
        paths = [str(self.root/f'{index}.slddrw') for index in range(3)]
        self.app._fill_files(paths)
        for path, status in zip(paths, ('success', 'skipped', 'error')):
            self.app.results.append({'source': path, 'output': str(Path(path).with_suffix('.pdf')),
                                     'status': status, 'detail': 'Türkçe açıklama'})
            self.app._update_row(path, status, 'Türkçe açıklama')
        self.app._finish({'state': 'completed', 'total': 3, 'processed': 3,
                          'succeeded': 1, 'skipped': 1, 'failed': 1, 'error': ''})
        self.app.filter_menu._dropdown_menu.invoke(5)
        self.assertEqual(self.app.status_filter.get(), 'Hatalı')
        self.assertEqual(self.app.table.get_children(), ('file_2',))
        output = self.root/'rapor.csv'
        with patch('pdf.window.filedialog.asksaveasfilename', return_value=str(output)):
            self.app.report_button.invoke()
        with output.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.reader(stream, delimiter=';'))
        self.assertEqual(len(rows), 4)
        self.assertEqual([row[0] for row in rows[1:]], paths)
        with patch('pdf.window.filedialog.asksaveasfilename', return_value=''):
            self.app.report_button.invoke()
        self.assertTrue(output.is_file())

    def test_ctrl_f_search_entry_and_clear_button_bindings(self):
        paths = [str(self.root/name) for name in ('ÇİZİM.slddrw', 'other.slddrw')]
        self.app._fill_files(paths)
        self.app.result_tabs.set('Günlük')
        self.app.focus_force()
        self.app.update()
        self.app.event_generate('<Control-f>')
        self.app.update()
        self.assertEqual(self.app.result_tabs.get(), 'Dosyalar')
        self.assertIs(self.app.focus_get(), self.app.search_entry._entry)
        self.app.search_entry.insert(0, 'çizim')
        self.assertEqual(self.app.table.get_children(), ('file_0',))
        clear = next(widget for widget in self.app.files_toolbar.winfo_children()
                     if isinstance(widget, ctk.CTkButton) and widget.cget('text') == 'Temizle')
        clear.invoke()
        self.assertEqual(self.app.table.get_children(), ('file_0', 'file_1'))

    def test_mouse_double_click_and_escape_close_details(self):
        self.app._fill_files([str(self.root/'waiting.slddrw')])
        self.settle()
        x, y, width, height = self.app.table.bbox('file_0')
        for timestamp in (100000, 100080):
            self.app.table.event_generate('<ButtonPress-1>', x=x+20, y=y+height//2, time=timestamp)
            self.app.table.event_generate('<ButtonRelease-1>', x=x+20, y=y+height//2, time=timestamp+10)
            self.app.update()
        window = self.app.detail_window
        self.assertTrue(window.winfo_exists())
        content = next(child for child in window.winfo_children() if isinstance(child, ctk.CTkTextbox))
        self.assertIn('Henüz üretilmedi', content.get('1.0', 'end'))
        window.focus_force()
        window.update()
        window.event_generate('<Escape>')
        self.app.update()
        self.assertFalse(window.winfo_exists())
        self.app.table.selection_set('file_0')
        self.app.table.focus_force()
        self.app.table.event_generate('<Return>')
        self.app.update()
        self.assertTrue(self.app.detail_window.winfo_exists())
        self.app._close_detail()

    def test_output_folder_button_delegates_or_reports_error(self):
        output = self.root/'outputs'
        output.mkdir()
        self.app.output_folder.set(str(output))
        with patch('pdf.window.os.startfile', create=True) as opener:
            self.app.open_button.invoke()
            opener.assert_called_once_with(str(output))
        with patch('pdf.window.os.startfile', create=True, side_effect=OSError('Açma hatası')):
            self.app.open_button.invoke()
        self.assertIn('Klasör açılamadı', self.app.status_label.cget('text'))
        self.app.output_folder.set(str(self.root/'missing'))
        self.app.open_button.invoke()
        self.assertIn('henüz oluşturulmadı', self.app.status_label.cget('text'))

    def test_scan_failure_releases_controls_and_reports_reason(self):
        self.app.nav_buttons['dxf_dwg'].invoke()
        self.app.source_folder.set(str(self.root))
        with patch('pdf.window.find_parts', side_effect=OSError('Klasör okunamıyor')):
            self.app.scan_button.invoke()
            self.wait_idle()
        self.assertIn('Klasör okunamıyor', self.app.status_label.cget('text'))
        self.assertEqual(self.app.start_button.cget('state'), 'normal')
        self.assertEqual(self.app.nav_buttons['pdf'].cget('state'), 'normal')

    def test_repeated_navigation_and_theme_buttons_keep_page_state(self):
        for mode in ('pdf', 'dxf_dwg'):
            self.app.nav_buttons[mode].invoke()
            self.app.source_folder.set(str(self.root/mode))
        for index in range(16):
            mode = 'pdf' if index % 2 else 'dxf_dwg'
            self.app.nav_buttons[mode].invoke()
            self.app.theme_selector._buttons_dict['Koyu' if index % 2 else 'Açık'].invoke()
            self.app.update()
            self.assertEqual(self.app.mode, mode)
            self.assertEqual(self.app.source_folder.get(), str(self.root/mode))
        self.assertEqual(len(self.app._pages), 2)

    def test_layout_matrix_keeps_primary_controls_inside_window(self):
        for dimensions in ('1000x690', '1140x840', '1240x860'):
            self.app.geometry(dimensions)
            for theme in ('Açık', 'Koyu'):
                self.app.theme_selector._buttons_dict[theme].invoke()
                for mode in ('pdf', 'dxf_dwg'):
                    with self.subTest(size=dimensions, theme=theme, mode=mode):
                        self.app.nav_buttons[mode].invoke()
                        self.settle()
                        self.assertGreater(self.app.table.winfo_height(), 80)
                        for widget in (self.app.start_button, self.app.stop_button, self.app.search_entry,
                                       self.app.filter_menu, self.app.table, self.app.progress):
                            self.assertTrue(widget.winfo_viewable())
                            self.assertGreaterEqual(widget.winfo_rootx(), self.app.winfo_rootx())
                            self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(),
                                                 self.app.winfo_rootx()+self.app.winfo_width())
                            self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),
                                                 self.app.winfo_rooty()+self.app.winfo_height())


if __name__ == '__main__':
    unittest.main()
