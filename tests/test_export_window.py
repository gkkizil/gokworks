import csv
import runpy
import unittest
from pathlib import Path
from tkinter import ttk
from tkinter.font import Font
from types import SimpleNamespace
from unittest.mock import Mock, patch

import customtkinter as ctk
from support.gui import GuiTestCase
from support.solidworks import (
    FakeApp,
    FakeAssembly,
    FakeComponent,
    FakeDrawing,
    FakePart,
    FakePdfApp,
    solidworks_session,
)

from dxf_dwg import exporter as ex
from pdf import exporter as pdf_ex
from pdf.settings import load_settings, save_settings


class WindowTests(GuiTestCase):
    def test_navigation_retains_independent_preferences(self):
        sidebar = self.app.sidebar
        pdf_page = self.app.workspace
        self.app.source_folder.set('/pdf/source')
        self.app.output_folder.set('/pdf/out')
        self.app.overwrite_existing.set(True)
        pdf_source = '/pdf/source/example.slddrw'
        self.app._fill_files([pdf_source])
        self.app._update_row(pdf_source, 'success', 'PDF hazır')
        self.app.results.append({'source': pdf_source, 'output': '/pdf/out/example.pdf',
                                 'status': 'success', 'detail': 'PDF hazır'})
        self.app._append_log('PDF sonucu korundu')
        self.app.result_tabs.set('Günlük')
        self.app._switch_mode('dxf_dwg')
        self.app.update()
        self.assertEqual(self.app.mode, 'dxf_dwg')
        self.assertEqual(self.app.source_folder.get(), '')
        self.app.source_folder.set('/parts')
        self.app.output_folder.set('/cad')
        self.app.output_format.set('DWG')
        self.app.bend_lines.set(True)
        self.app._switch_mode('pdf')
        self.app.update()
        self.assertEqual(self.app.source_folder.get(), '/pdf/source')
        self.assertTrue(self.app.overwrite_existing.get())
        self.assertIs(self.app.sidebar, sidebar)
        self.assertIs(self.app.workspace, pdf_page)
        self.assertEqual(self.app.results[0]['detail'], 'PDF hazır')
        self.assertEqual(self.app.table.item('file_0', 'values')[1], 'Başarılı')
        self.assertIn('PDF sonucu korundu', self.app.log_box.get('1.0', 'end'))
        self.assertEqual(self.app.result_tabs.get(), 'Günlük')
        self.app._save_preferences()
        self.assertEqual(load_settings(self.settings)['dxf_dwg_format'], 'DWG')
        self.app._switch_mode('dxf_dwg')
        self.app.update()
        self.assertEqual(self.app.source_folder.get(), '/parts')
        self.assertEqual(self.app.output_format.get(), 'DWG')
        self.assertTrue(self.app.bend_lines.get())
        saved = load_settings(self.settings)
        self.assertEqual(saved['pdf_source'], '/pdf/source')
        self.assertEqual(saved['dxf_dwg_source'], '/parts')
        self.assertEqual(saved['unrelated_setting'], 'keep')

    def test_dxf_scan_and_navigation_locked_during_worker(self):
        source = self.root/'parts'
        source.mkdir()
        (source/'one.sldprt').touch()
        (source/'~$lock.sldprt').touch()
        (source/'drawing.slddrw').touch()
        self.app._switch_mode('dxf_dwg')
        self.app.source_folder.set(str(source))
        self.app._scan()
        self.app._switch_mode('pdf')
        self.assertEqual(self.app.mode, 'dxf_dwg')
        self.wait_idle()
        self.assertEqual(len(self.app.table.get_children()), 1)
        self.assertIn('1 parça', self.app.status_label.cget('text'))
        self.assertEqual(self.app.start_button.cget('text'), 'Açınım aktarımını başlat')

    def test_pdf_scan_regression(self):
        (self.root/'one.slddrw').touch()
        (self.root/'part.sldprt').touch()
        self.app.source_folder.set(str(self.root))
        self.app._scan()
        self.wait_idle()
        self.assertEqual(len(self.app.table.get_children()), 1)
        self.assertIn('1 teknik resim', self.app.status_label.cget('text'))

    def test_full_dxf_worker_and_csv_report(self):
        source = self.root/'parts'
        source.mkdir()
        part = source/'sheet.sldprt'
        part.touch()
        model = FakePart(part)
        assembly = FakeAssembly(self.root/'main.sldasm', [FakeComponent(part) for _ in range(3)])
        self.app._switch_mode('dxf_dwg')
        self.app.source_folder.set(str(source))
        self.app.output_folder.set(str(self.root/'outputs'))
        self.app.output_format.set('DXF')
        self.app.bend_lines.set(True)
        with solidworks_session(ex, FakeApp(model, previous=assembly), 'dxf'):
            self.app._start_export()
            self.wait_idle()
        self.assertEqual(len(self.app.results), 1)
        self.assertEqual(self.app.results[0]['status'], 'success')
        self.assertEqual(self.app.stat_values['succeeded'].cget('text'), '1')
        self.assertEqual(self.app.progress.get(), 1)
        self.assertIn('1 parça', self.app.status_label.cget('text'))
        self.assertEqual(self.app.table.item('file_0', 'values')[1], 'Başarılı')
        self.assertIn('2 mm · 3 adet', self.app.table.item('file_0', 'values')[2])
        self.assertFalse(self.app.empty_state.winfo_viewable())
        self.assertEqual(model.calls[0][7], 5)
        dxf_page = self.app.workspace
        self.app._switch_mode('pdf')
        self.app._switch_mode('dxf_dwg')
        self.app.update()
        self.assertIs(self.app.workspace, dxf_page)
        self.assertEqual(len(self.app.results), 1)
        self.assertEqual(self.app.table.item('file_0', 'values')[1], 'Başarılı')
        report = self.root/'report.csv'
        with patch('pdf.window.filedialog.asksaveasfilename', return_value=str(report)):
            self.app._save_report()
        with report.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.reader(stream, delimiter=';'))
        self.assertEqual(rows[0], ['Kaynak', 'DXF / DWG', 'Durum', 'Açıklama'])
        self.assertIn('sheet - 2 mm - 3 adet.dxf', rows[1][1])
        self.assertNotIn('.dwg', rows[1][1])
        self.assertEqual(self.app.results[0]['quantity'], 3)
        self.assertTrue((self.root/'outputs'/'sheet - 2 mm - 3 adet.dxf').is_file())
        self.assertFalse((self.root/'outputs'/'sheet - 2 mm - 3 adet.dwg').exists())
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(rows[1][2], 'Başarılı')

    def test_empty_list_hint_follows_scan_reset_and_independent_tabs(self):
        self.assertTrue(self.app.empty_state.winfo_viewable())
        pdf_hint = self.app.empty_state
        (self.root/'drawing.slddrw').touch()
        self.app.source_folder.set(str(self.root))
        self.app._scan()
        self.wait_idle()
        self.assertFalse(pdf_hint.winfo_viewable())
        self.app._switch_mode('dxf_dwg')
        self.app.update()
        self.assertTrue(self.app.empty_state.winfo_viewable())
        dxf_hint = self.app.empty_state
        self.app._switch_mode('pdf')
        self.app.update()
        self.assertIs(self.app.empty_state, pdf_hint)
        self.assertFalse(self.app.empty_state.winfo_viewable())
        self.assertEqual(len(self.app.table.get_children()), 1)
        self.app._reset()
        self.app.update()
        self.assertTrue(self.app.empty_state.winfo_viewable())
        self.assertEqual(len(self.app.table.get_children()), 0)
        self.app._switch_mode('dxf_dwg')
        self.app.update()
        self.assertIs(self.app.empty_state, dxf_hint)
        self.assertTrue(self.app.empty_state.winfo_viewable())

    def test_empty_dxf_worker_message(self):
        self.app._switch_mode('dxf_dwg')
        self.app.source_folder.set(str(self.root))
        self.app.output_folder.set(str(self.root/'out'))
        self.app._start_export()
        self.wait_idle()
        self.assertIn('.SLDPRT', self.app.status_label.cget('text'))
        self.assertEqual(self.app.report_button.cget('state'), 'disabled')

    def test_source_dialog_filters_parts(self):
        self.app._switch_mode('dxf_dwg')
        with patch('pdf.window.filedialog.askopenfilename', return_value=str(self.root/'part.sldprt')) as dialog:
            self.app._choose_folder(self.app.source_folder, 'Kaynak')
        self.assertEqual(dialog.call_args.kwargs['filetypes'][0][1], '*.sldprt')
        self.assertEqual(self.app.source_folder.get(), str(self.root))

    def test_full_pdf_worker_and_turkish_csv_report(self):
        source = self.root/'Çizimler'
        source.mkdir()
        drawing = source/'Çizim.slddrw'
        drawing.touch()
        model = FakeDrawing(drawing)
        self.app.source_folder.set(str(source))
        self.app.output_folder.set(str(self.root/'PDF'))
        with solidworks_session(pdf_ex, FakePdfApp([model]), 'pdf'):
            self.app._start_export()
            self.wait_idle()
        self.assertEqual(self.app.results[0]['status'], 'success')
        self.assertTrue((self.root/'PDF/Çizim.pdf').is_file())
        self.assertEqual(self.app.progress.get(), 1)
        self.assertEqual(self.app.stat_values['succeeded'].cget('text'), '1')
        self.assertEqual(self.app.report_button.cget('state'), 'normal')
        report = self.root/'pdf-report.csv'
        with patch('pdf.window.filedialog.asksaveasfilename', return_value=str(report)):
            self.app._save_report()
        with report.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.reader(stream, delimiter=';'))
        self.assertEqual(rows[0], ['Kaynak', 'PDF', 'Durum', 'Açıklama'])
        self.assertIn('Çizim.pdf', rows[1][1])
        self.assertEqual(rows[1][2], 'Başarılı')

    def test_invalid_source_and_output_keep_worker_idle(self):
        self.app.source_folder.set(str(self.root/'missing'))
        self.app._start_export()
        self.assertFalse(self.app.busy)
        self.assertIn('Kaynak klasör bulunamadı', self.app.status_label.cget('text'))
        self.app.source_folder.set(str(self.root))
        (self.root/'output-file').touch()
        self.app.output_folder.set(str(self.root/'output-file'))
        self.app._start_export()
        self.assertFalse(self.app.busy)
        self.assertIn('Geçerli bir çıktı', self.app.status_label.cget('text'))

    def test_connection_failure_releases_controls_and_shows_error(self):
        (self.root/'one.slddrw').touch()
        self.app.source_folder.set(str(self.root))
        self.app.output_folder.set(str(self.root/'out'))
        com = SimpleNamespace(CoInitialize=Mock(), CoUninitialize=Mock())
        with patch.multiple(pdf_ex, pythoncom=com, win32com=object()), patch.object(pdf_ex, 'connect_to_solidworks', side_effect=RuntimeError('SolidWorks oturumu yok')):
            self.app._start_export()
            self.wait_idle()
        self.assertIn('SolidWorks oturumu yok', self.app.status_label.cget('text'))
        self.assertEqual(self.app.result_tabs.get(), 'Günlük')
        self.assertEqual(self.app.start_button.cget('state'), 'normal')
        self.assertEqual(self.app.nav_buttons['dxf_dwg'].cget('state'), 'normal')
        self.assertEqual(self.app.report_button.cget('state'), 'disabled')

    def test_restart_loads_both_modules_and_rejects_invalid_format(self):
        self.app._on_close()
        save_settings({'pdf_source': '/Çizimler', 'pdf_output': '/PDF',
                       'pdf_recursive': False, 'pdf_overwrite': True,
                       'dxf_dwg_source': '/Parçalar', 'dxf_dwg_output': '/CAD',
                       'dxf_dwg_format': 'INVALID', 'dxf_dwg_bend_lines': True}, self.settings)
        self.open_app()
        self.assertEqual(self.app.source_folder.get(), '/Çizimler')
        self.assertFalse(self.app.include_subfolders.get())
        self.assertTrue(self.app.overwrite_existing.get())
        self.app._switch_mode('dxf_dwg')
        self.assertEqual(self.app.source_folder.get(), '/Parçalar')
        self.assertEqual(self.app.output_format.get(), 'DXF')
        self.assertTrue(self.app.bend_lines.get())
        self.assertEqual(self.app.nav_buttons['k_factor'].cget('state'), 'normal')

    def test_stop_then_close_waits_for_active_worker(self):
        from threading import Event
        entered, proceed = Event(), Event()
        self.addCleanup(proceed.set)
        (self.root/'one.slddrw').touch()
        self.app.source_folder.set(str(self.root))
        self.app.output_folder.set(str(self.root/'out'))
        def export(source, output, recursive, overwrite, events, stop):
            entered.set()
            proceed.wait(5)
            events.put(('done', {'state': 'cancelled', 'total': 1, 'processed': 0,
                                'succeeded': 0, 'skipped': 0, 'failed': 0, 'error': ''}))
        with patch('pdf.window.export_drawings', side_effect=export):
            self.app._start_export()
            self.assertTrue(entered.wait(2))
            with patch('pdf.window.messagebox.askyesno', return_value=True):
                self.app._on_close()
            self.assertTrue(self.app.stop_event.is_set())
            self.assertTrue(self.app.close_pending)
            self.assertFalse(self.app._closed)
            proceed.set()
            self.pump_until(lambda: self.app._closed)

    def test_report_write_failure_is_displayed(self):
        self.app.results.append({'source': 'test.slddrw', 'output': 'test.pdf',
                                 'status': 'success', 'detail': 'ready'})
        with patch('pdf.window.filedialog.asksaveasfilename', return_value=str(self.root/'missing/report.csv')):
            self.app._save_report()
        self.assertIn('Rapor kaydedilemedi', self.app.status_label.cget('text'))

    def test_themes_preserve_both_pages_and_reload_preference(self):
        pdf_source = str(self.root/'ÇİZİM.slddrw')
        self.app._fill_files([pdf_source])
        self.app._update_row(pdf_source, 'success', 'Çizim tamamlandı')
        pdf_table = self.app.table
        self.app._switch_mode('dxf_dwg')
        part = str(self.root/'braket.sldprt')
        self.app._fill_files([part])
        self.app._update_row(part, 'error', 'Sac metal değil')
        self.app._append_log('Sonuçlar korundu')
        self.app.output_format.set('DWG')
        self.app.bend_lines.set(True)
        self.app._change_theme('Koyu')
        self.app.update()
        dark_color = ttk.Style(self.app).lookup('Gok.Treeview', 'background')
        self.assertEqual(ctk.get_appearance_mode(), 'Dark')
        self.assertEqual(load_settings(self.settings)['appearance'], 'dark')
        self.assertEqual(self.app.table.item('file_0', 'values')[1], 'Hata')
        self.app._switch_mode('pdf')
        self.assertIs(self.app.table, pdf_table)
        self.assertEqual(self.app.table.item('file_0', 'values')[1], 'Başarılı')
        self.app._change_theme('Açık')
        self.app.update()
        self.assertNotEqual(dark_color, ttk.Style(self.app).lookup('Gok.Treeview', 'background'))
        self.app._switch_mode('dxf_dwg')
        self.assertEqual(self.app.output_format.get(), 'DWG')
        self.assertTrue(self.app.bend_lines.get())
        self.assertIn('Sonuçlar korundu', self.app.log_box.get('1.0', 'end'))
        self.app._change_theme('Koyu')
        self.app._on_close()
        self.open_app()
        self.assertEqual(self.app.theme_mode.get(), 'Koyu')
        self.assertEqual(ctk.get_appearance_mode(), 'Dark')

    def test_search_status_filters_and_live_results_keep_full_counts(self):
        paths = [str(self.root/name) for name in ('ÇİZİM.slddrw', 'braket.slddrw', 'plate.slddrw')]
        self.app._fill_files(paths)
        self.app._update_row(paths[0], 'success', 'PDF hazır')
        self.app._update_row(paths[1], 'error', 'Çizim açılamadı')
        self.app._update_row(paths[2], 'skipped', 'Zaten var')
        self.app.search_query.set('çizim')
        self.assertEqual(self.app.table.get_children(), ('file_0', 'file_1'))
        self.app.status_filter.set('Hatalı')
        self.assertEqual(self.app.table.get_children(), ('file_1',))
        self.assertEqual(self.app.visible_count.cget('text'), '1 / 3 dosya')
        self.assertEqual(self.app.stat_values['total'].cget('text'), '3')
        self.app.search_query.set('olmayan')
        self.app.update()
        self.assertTrue(self.app.empty_state.winfo_viewable())
        self.assertEqual(self.app.empty_title.cget('text'), 'Eşleşen dosya yok')
        self.app.search_query.set('')
        self.app._update_row(paths[1], 'running')
        self.assertEqual(self.app.table.get_children(), ())
        self.app._update_row(paths[2], 'error', 'Yeni hata')
        self.assertEqual(self.app.table.get_children(), ('file_2',))
        self.app._clear_filters()
        self.assertEqual(self.app.table.get_children(), ('file_0', 'file_1', 'file_2'))

    def test_rescan_deletes_detached_rows_and_resets_filters(self):
        self.app._fill_files([str(self.root/'old.slddrw')])
        self.app.search_query.set('yok')
        self.assertEqual(self.app.table.get_children(), ())
        self.app._reset()
        self.app._fill_files([str(self.root/'new.slddrw')])
        self.assertEqual(self.app.table.get_children(), ('file_0',))
        self.assertEqual(self.app.table.item('file_0', 'values')[0], 'new.slddrw')
        self.assertEqual(self.app.search_query.get(), '')
        self.assertEqual(self.app.status_filter.get(), 'Tüm durumlar')

    def test_filters_are_independent_between_modules(self):
        self.app._fill_files([str(self.root/'drawing.slddrw')])
        self.app.search_query.set('pdf query')
        self.app.status_filter.set('Hatalı')
        self.app._switch_mode('dxf_dwg')
        self.assertEqual(self.app.search_query.get(), '')
        self.app._fill_files([str(self.root/'part.sldprt')])
        self.app.search_query.set('part')
        self.app._switch_mode('pdf')
        self.assertEqual(self.app.search_query.get(), 'pdf query')
        self.assertEqual(self.app.status_filter.get(), 'Hatalı')
        self.assertEqual(self.app.table.get_children(), ())
        self.app._switch_mode('dxf_dwg')
        self.assertEqual(self.app.search_query.get(), 'part')
        self.assertEqual(self.app.table.get_children(), ('file_0',))

    def test_details_show_full_paths_and_copy_to_clipboard(self):
        path = str(self.root/'Çizim.slddrw')
        output = str(self.root/'out/Çizim.pdf')
        self.app._fill_files([path])
        self.app.results.append({'source': path, 'output': output, 'status': 'success', 'detail': 'Tüm sayfalar'})
        self.app._update_row(path, 'success', 'Tüm sayfalar')
        self.app.table.selection_set('file_0')
        self.app._show_detail()
        self.app.update()
        window = self.app.detail_window
        content = next(widget for widget in window.winfo_children() if isinstance(widget, ctk.CTkTextbox))
        self.assertIn(path, content.get('1.0', 'end'))
        self.assertIn(output, content.get('1.0', 'end'))
        self.assertIn('Başarılı', content.get('1.0', 'end'))
        actions = next(widget for widget in window.winfo_children() if isinstance(widget, ctk.CTkFrame))
        copy = next(widget for widget in actions.winfo_children() if isinstance(widget, ctk.CTkButton)
                    and widget.cget('text') == 'Ayrıntıları kopyala')
        copy.invoke()
        self.assertIn(output, self.app.clipboard_get())
        self.app._change_theme('Koyu')
        self.app.update()
        self.assertIn(path, content.get('1.0', 'end'))
        close = next(widget for widget in actions.winfo_children() if isinstance(widget, ctk.CTkButton)
                     and widget.cget('text') == 'Kapat')
        close.invoke()
        self.assertFalse(window.winfo_exists())
        self.assertIn(output, self.app.clipboard_get())

    def test_theme_change_while_busy_preserves_worker_controls(self):
        self.app._switch_mode('dxf_dwg')
        self.app._set_busy(True)
        self.app._change_theme('Koyu')
        self.app.update()
        self.assertTrue(self.app.busy)
        self.assertEqual(self.app.start_button.cget('state'), 'disabled')
        self.assertEqual(self.app.stop_button.cget('state'), 'normal')
        self.assertEqual(self.app.nav_buttons['pdf'].cget('state'), 'disabled')
        self.app._set_busy(False)

    def test_scaled_interface_keeps_table_text_and_icons_usable(self):
        original = self.app.settings_body._get_widget_scaling()
        self.addCleanup(lambda: ctk.set_widget_scaling(original))
        self.app.geometry('1240x860')
        before = abs(Font(self.app, font=ttk.Style(self.app).lookup('Gok.Treeview', 'font')).cget('size'))
        ctk.set_widget_scaling(1.25)
        for selection in ('Açık', 'Koyu'):
            self.app._change_theme(selection)
            for mode in ('pdf', 'dxf_dwg'):
                self.app._switch_mode(mode)
                self.wait_layout()
                self.assertGreater(self.app.table.winfo_height(), 80)
                self.assertTrue(self.app.start_button.winfo_viewable())
                self.assertEqual(self.app.theme_mode.get(), selection)
        after = abs(Font(self.app, font=ttk.Style(self.app).lookup('Gok.Treeview', 'font')).cget('size'))
        self.assertGreater(after, before)

    def test_real_entrypoint_runs_tk_loop_and_closes_cleanly(self):
        def existing_window():
            self.app.after(200, self.app._on_close)
            return self.app
        with patch('pdf.window.GokworksPdfApp', side_effect=existing_window):
            runpy.run_path(str(Path(__file__).resolve().parents[1]/'main.py'), run_name='__main__')
        self.assertTrue(self.app._closed)

    def test_minimum_window_size_keeps_controls_and_results_visible(self):
        self.app.geometry('1000x690')
        for mode in ('pdf', 'dxf_dwg'):
            self.app._switch_mode(mode)
            self.wait_layout()
            self.assertIsNone(self.app._layout_fit_id)
            self.assertTrue(self.app.start_button.winfo_viewable())
            self.assertTrue(self.app.table.winfo_viewable())
            self.assertGreater(self.app.table.winfo_height(), 80)
            self.assertLessEqual(self.app.progress.winfo_y() + self.app.progress.winfo_height(),
                                 self.app.workspace.winfo_height())
        self.app.geometry('1140x840')
        for mode in ('pdf', 'dxf_dwg'):
            self.app._switch_mode(mode)
            self.app.update()
            self.wait_layout()
            viewport = self.app.settings_body._parent_canvas
            self.assertLessEqual(self.app.scan_button.winfo_rooty() + self.app.scan_button.winfo_height(),
                                 viewport.winfo_rooty() + viewport.winfo_height())


if __name__ == '__main__':
    unittest.main()
