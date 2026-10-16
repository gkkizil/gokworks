"""Real Tk naming workflow, preview validation, themes and page persistence."""

from pathlib import Path
import json
import threading
from unittest.mock import patch

import customtkinter as ctk

from naming import exporter as naming
from support.gui import GuiTestCase
from test_naming import App, install_com


class NamingWindowTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.sw = App(self.root)
        install_com(self)
        self.app._switch_mode('naming')
        self.destination = self.root/'Yeni-montaj'
        self.app.naming_state['destination'].set(str(self.destination))
        self.app.naming_state['source_folder'].set(str(self.root))
        self.app._show_naming_sources((self.root/'Ana.sldasm', self.root/'Alt.sldasm'))
        self.app._select_naming_assembly('Ana.sldasm')
        self.app.naming_state['prefix'].set('PROJE-')

    def scan(self):
        with patch('naming.exporter.connect_to_solidworks', return_value=self.sw):
            self.app.naming_widgets['scan'].invoke()
            self.wait_idle()
        self.settle()

    def table_rows(self, parent=''):
        table = self.app.naming_widgets['table']
        return [row for child in table.get_children(parent)
                for row in (child, *self.table_rows(child))]

    def test_scan_manual_model_and_paired_drawing_edit_then_save_package(self):
        self.scan()
        widgets = self.app.naming_widgets
        self.assertEqual(len(self.table_rows()), 7)
        self.assertEqual(widgets['save'].cget('state'), 'normal')
        index = next(i for i, entry in enumerate(self.app.naming_plan) if Path(entry.source).name == 'Levha.sldprt')
        widgets['table'].selection_set(str(index))
        with patch('naming.window.simpledialog.askstring', return_value='ÖZEL-LEVHA'):
            self.app._edit_naming_row()
        names = {Path(e.source).name: Path(e.destination).name for e in self.app.naming_plan}
        self.assertEqual(names['Levha.slddrw'], 'ÖZEL-LEVHA.slddrw')
        with patch('naming.exporter.connect_to_solidworks', return_value=self.sw):
            widgets['save'].invoke()
            self.wait_idle()
        self.assertEqual(self.sw.saves, 1)
        self.assertIn('bağlantıları doğrulandı', self.app.status_label.cget('text'))
        destination = self.destination
        self.assertTrue((destination/'ÖZEL-LEVHA.slddrw').is_file())
        self.assertTrue((destination/naming.REPORT_NAME).is_file())
        self.assertEqual(widgets['save'].cget('state'), 'disabled')
        self.assertEqual(self.app.nav_buttons['pdf'].cget('state'), 'normal')

    def test_native_error_signature_is_copied_in_full_without_growing_status_label(self):
        error = 'SolidWorks GetPackAndGo başlatılamadı (API çağrısı): -2147352561 · '+ 'parametre bilgisi; '*40
        with patch('naming.exporter.connect_to_solidworks', side_effect=RuntimeError(error)):
            self.app.naming_widgets['scan'].invoke()
            self.wait_idle()
        self.app.geometry('1000x690')
        self.settle()
        button = self.app.naming_widgets['copy_error']
        self.assertTrue(button.winfo_viewable())
        self.assertLess(len(self.app.status_label.cget('text')), 250)
        button.invoke()
        copied = self.app.clipboard_get()
        self.assertIn(error, copied)
        self.assertIn('Ana.sldasm', copied)
        self.assert_inside(button)
        self.scan()
        self.assertFalse(button.winfo_viewable())
        self.assertNotIn('last_error', self.app.naming_widgets)

    def test_invalid_rules_existing_folder_and_failed_rescan_disable_save(self):
        self.scan()
        self.app.naming_state['prefix'].set('bad:')
        self.settle()
        self.assertEqual(self.app.naming_widgets['save'].cget('state'), 'disabled')
        self.app.naming_state['prefix'].set('PROJE-')
        self.destination.mkdir()
        (self.destination/'existing.txt').write_text('keep')
        # Reselecting the destination forces a fresh directory check.
        self.app.naming_state['destination'].set(str(self.destination))
        self.settle()
        self.assertEqual(self.app.naming_widgets['save'].cget('state'), 'disabled')
        with patch('naming.exporter.connect_to_solidworks', side_effect=RuntimeError('SolidWorks yok')):
            self.app.naming_widgets['scan'].invoke()
            self.wait_idle()
        self.assertIsNone(self.app.naming_snapshot)
        self.assertFalse(self.app.naming_widgets['table'].get_children())
        self.assertIn('SolidWorks yok', self.app.status_label.cget('text'))

    def test_colliding_source_basenames_stay_editable_until_names_are_unique(self):
        subfolder = self.root/'Other'
        subfolder.mkdir()
        second = subfolder/'Levha.sldprt'
        second.write_bytes((self.root/'Levha.sldprt').read_bytes())
        self.sw.paths.append(str(second))
        self.sw.states.append(0)
        root = self.root/'Ana.sldasm'
        content = json.loads(root.read_text())
        content['refs'].append(str(second))
        root.write_text(json.dumps(content))
        self.scan()
        widgets = self.app.naming_widgets
        self.assertEqual(len(set(widgets['row_indices'].values())), 8)
        self.assertEqual(len(self.table_rows()), 9)  # Both derived parts reference the same base file.
        self.assertEqual(widgets['save'].cget('state'), 'disabled')
        index = next(i for i, entry in enumerate(self.app.naming_plan) if entry.source == str(second))
        widgets['table'].selection_set(str(index))
        with patch('naming.window.simpledialog.askstring', return_value='İkinci levha'):
            self.app._edit_naming_row()
        self.assertEqual(widgets['save'].cget('state'), 'normal')
        with patch('naming.exporter.connect_to_solidworks', return_value=self.sw):
            widgets['save'].invoke()
            self.wait_idle()
        self.assertEqual(self.sw.saves, 1)

    def test_assembly_tree_shared_edit_preserves_branches_and_pack_order(self):
        root = self.root/'Ana.sldasm'
        content = json.loads(root.read_text())
        content['refs'].append(str(self.root/'Cıvata.sldprt'))
        root.write_text(json.dumps(content))
        self.scan()
        widgets = self.app.naming_widgets
        table = widgets['table']
        ids = {Path(doc.path).name: str(i) for i, doc in enumerate(self.app.naming_snapshot.documents)}
        self.assertEqual(table.parent(ids['Alt.sldasm']), ids['Ana.sldasm'])
        self.assertEqual(table.parent(ids['Cıvata.sldprt']), ids['Alt.sldasm'])
        self.assertEqual(table.parent(ids['Levha.sldprt']), ids['Ana.sldasm'])
        self.assertEqual(table.parent(ids['Levha.slddrw']), ids['Levha.sldprt'])
        self.assertEqual(table.parent(ids['Ana.slddrw']), ids['Ana.sldasm'])
        # Derived-file dependencies must not appear as extra assembly components.
        self.assertEqual(table.parent(ids['Taban.sldprt']), ids['Levha.sldprt'])
        self.assertIn('Referans', table.set(ids['Taban.sldprt'], 'kind'))
        repeated = next(row for row in self.table_rows() if row.startswith(ids['Cıvata.sldprt']+':'))
        self.assertEqual(table.parent(repeated), ids['Ana.sldasm'])
        self.assertIn('Ortak dosya', table.set(repeated, 'kind'))
        table.item(ids['Alt.sldasm'], open=False)
        table.selection_set(repeated)
        with patch('naming.window.simpledialog.askstring', return_value='BHV-R01-630'):
            self.app._edit_naming_row()
        self.assertFalse(table.item(ids['Alt.sldasm'], 'open'))
        self.assertEqual(table.selection(), (repeated,))
        for row in (repeated, ids['Cıvata.sldprt']):
            self.assertEqual(table.set(row, 'new'), 'BHV-R01-630.sldprt')
        self.assertEqual([entry.source for entry in self.app.naming_plan], self.sw.paths)
        with patch('naming.exporter.connect_to_solidworks', return_value=self.sw):
            widgets['save'].invoke()
            self.wait_idle()
        self.assertEqual(list(self.sw.last_mapping), self.sw.paths)
        self.assertEqual(self.sw.saves, 1)

    def test_cached_page_and_rules_survive_theme_and_small_window_scaling(self):
        self.scan()
        workspace, snapshot = self.app.workspace, self.app.naming_snapshot
        self.app._switch_mode('bom')
        self.app._switch_mode('naming')
        self.assertIs(self.app.workspace, workspace)
        self.assertIs(self.app.naming_snapshot, snapshot)
        self.assertEqual(self.app.naming_state['prefix'].get(), 'PROJE-')
        self.addCleanup(lambda: ctk.set_widget_scaling(1))
        for scale in (1, 1.25):
            ctk.set_widget_scaling(scale)
            self.app._set_scaled_min_max()
            self.app.geometry('1000x690')
            for theme in ('Açık', 'Koyu'):
                self.app._change_theme(theme)
                self.settle()
                self.assertFalse(self.app.naming_widgets['copy_error'].winfo_viewable())
                for key in ('scan', 'save', 'stop', 'table', 'destination', 'prefix', 'mode', 'suffix', 'start', 'digits'):
                    self.assert_inside(self.app.naming_widgets[key])
                for key in ('source_browse', 'browse', 'source_folder', 'assembly'):
                    self.assert_inside(self.app.naming_widgets[key])
                for button in self.app.nav_buttons.values():
                    self.assert_inside(button, self.app.sidebar)
                self.assertGreater(self.app.naming_widgets['table'].winfo_height(), 100)
                table_height = self.app.naming_widgets['table'].winfo_height()
                self.app.naming_widgets['form']._parent_canvas.yview_moveto(1)
                self.settle(.03)
                for key in ('find', 'replacement'):
                    self.assert_inside(self.app.naming_widgets[key])
                self.assertEqual(self.app.naming_widgets['table'].winfo_height(), table_height)
                self.app.naming_widgets['form']._parent_canvas.yview_moveto(0)
                self.settle(.03)
                self.assertLessEqual(self.app.nav_buttons['geometric_tolerances'].winfo_rooty()+
                                     self.app.nav_buttons['geometric_tolerances'].winfo_height(),
                                     self.app.theme_selector.winfo_rooty())

    def test_immediate_navigation_keeps_delayed_preview_and_edit_in_sync(self):
        self.scan()
        self.app.naming_state['prefix'].set('YENİ-')
        self.app._switch_mode('pdf')  # Leave before the 150 ms preview debounce.
        self.settle()
        self.app._switch_mode('naming')
        table = self.app.naming_widgets['table']
        index = next(i for i, entry in enumerate(self.app.naming_plan)
                     if Path(entry.source).name == 'Levha.sldprt')
        table.selection_set(str(index))
        self.assertEqual(table.set(str(index), 'new'), 'YENİ-Levha.sldprt')
        self.assertEqual(Path(self.app.naming_plan[index].destination).name, 'YENİ-Levha.sldprt')
        with patch('naming.window.simpledialog.askstring', return_value=None) as dialog:
            self.app._edit_naming_row()
        self.assertEqual(dialog.call_args.kwargs['initialvalue'], 'YENİ-Levha')
        self.assertNotIn('preview_id', self.app.naming_widgets)

    def test_source_folder_with_multiple_assemblies_uses_inline_choice_then_exact_target(self):
        self.scan()
        widgets = self.app.naming_widgets
        source = str(self.root/'Ana.sldasm')
        self.destination.mkdir()  # An existing empty target is accepted directly.
        with patch('naming.window.filedialog.askdirectory', side_effect=[str(self.root), str(self.destination)]), \
                patch('naming.window.filedialog.askopenfilename') as file_picker:
            widgets['source_browse'].invoke()
            self.wait_idle()
            widgets['browse'].invoke()
        file_picker.assert_not_called()
        self.assertEqual(self.app.naming_state['source_mode'].get(), 'Dosyadan')
        self.assertEqual(self.app.naming_state['source_folder'].get(), str(self.root))
        self.assertEqual(self.app.naming_state['source_file'].get(), '')
        self.assertTrue(widgets['assembly_holder'].winfo_viewable())
        self.assertIsNone(self.app.naming_snapshot)
        self.assertFalse(widgets['table'].get_children())
        with patch('naming.window.worker') as worker:
            widgets['scan'].invoke()
        worker.assert_not_called()
        self.assertIn('ana montajı seçin', widgets['status'].cget('text'))
        widgets['assembly']._dropdown_callback('Ana.sldasm')
        self.assertEqual(self.app.naming_state['source_file'].get(), source)
        self.scan()
        self.assertEqual(self.app.naming_snapshot.source_path, source)
        self.assertEqual(widgets['save'].cget('state'), 'normal')
        with patch('naming.exporter.connect_to_solidworks', return_value=self.sw):
            widgets['save'].invoke()
            self.wait_idle()
        self.assertEqual(self.sw.saves, 1)
        self.assertTrue((self.destination/'PROJE-Ana.sldasm').is_file())
        self.assertFalse((self.destination/'Yeni-paket').exists())

    def test_single_assembly_is_selected_without_a_file_picker_and_busy_pick_is_ignored(self):
        folder = self.root/'Tek-montaj'
        folder.mkdir()
        source = folder/'Tek.SLDASM'
        source.write_text('{}')
        with patch('naming.window.filedialog.askdirectory', return_value=str(folder)), \
                patch('naming.window.filedialog.askopenfilename') as picker:
            self.app.naming_widgets['source_browse'].invoke()
            self.wait_idle()
        picker.assert_not_called()
        self.assertEqual(self.app.naming_state['source_file'].get(), str(source))
        self.assertFalse(self.app.naming_widgets['assembly_holder'].winfo_viewable())
        with patch('naming.window.filedialog.askdirectory') as picker:
            self.app._naming_busy(True)
            self.app._pick_naming_source_folder()
            self.app._pick_naming_folder()
            self.app._naming_busy(False)
        picker.assert_not_called()

    def test_cancelled_source_selection_keeps_preview_but_empty_folder_invalidates_it(self):
        self.scan()
        snapshot = self.app.naming_snapshot
        with patch('naming.window.filedialog.askdirectory', return_value=''):
            self.app.naming_widgets['source_browse'].invoke()
        self.assertIs(self.app.naming_snapshot, snapshot)
        folder = self.root/'Bos'
        folder.mkdir()
        with patch('naming.window.filedialog.askdirectory', return_value=str(folder)):
            self.app.naming_widgets['source_browse'].invoke()
            self.wait_idle()
        self.assertEqual(self.app.naming_state['source_file'].get(), '')
        self.assertIsNone(self.app.naming_snapshot)
        self.assertEqual(self.app.naming_widgets['save'].cget('state'), 'disabled')
        self.assertIn('bulunamadı', self.app.naming_widgets['source'].cget('text'))
        with patch('naming.window.worker') as worker:
            self.app.naming_widgets['scan'].invoke()
            self.wait_idle()
        worker.assert_not_called()

    def test_destination_check_runs_outside_tk_and_is_reused_for_rule_edits(self):
        self.scan()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        ui_thread = threading.get_ident()
        threads = []
        def check(destination, snapshot):
            threads.append(threading.get_ident())
            entered.set()
            release.wait(3)
            return Path(destination)
        with patch('naming.window.validate_destination', side_effect=check) as check_folder:
            self.app.naming_state['destination'].set(str(self.root/'Other-output'))
            self.app._update_naming_preview()
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.app.naming_widgets['save'].cget('state'), 'disabled')
            self.app.naming_state['prefix'].set('NEW-')
            self.app._switch_mode('pdf')
            self.assertEqual(self.app.mode, 'pdf')
            release.set()
            self.settle()
            self.app._switch_mode('naming')
            self.assertEqual(self.app.naming_widgets['save'].cget('state'), 'normal')
            check_folder.assert_called_once()
        self.assertNotEqual(threads, [ui_thread])

    def test_old_parent_and_package_settings_migrate_to_one_destination(self):
        self.close_app()
        from pdf.settings import save_settings, load_settings
        save_settings({'naming_parent': str(self.root), 'naming_package': 'Old-package',
                       'naming_source_mode': 'Aktif montaj'}, self.settings)
        self.open_app()
        self.app._switch_mode('naming')
        self.assertEqual(self.app.naming_state['destination'].get(), str(self.root/'Old-package'))
        self.assertNotIn('parent', self.app.naming_state)
        self.assertNotIn('package', self.app.naming_state)
        self.assertEqual(self.app.naming_state['source_mode'].get(), 'Dosyadan')
        self.app._save_preferences()
        self.assertEqual(load_settings(self.settings)['naming_destination'], str(self.root/'Old-package'))

    def test_rules_are_saved_and_close_cancels_pending_worker(self):
        self.app.naming_state['suffix'].set('-R2')
        self.app._switch_mode('pdf')
        self.app._switch_mode('naming')
        from pdf.settings import load_settings
        self.app._save_preferences()
        self.assertEqual(load_settings(self.settings)['naming_suffix'], '-R2')
        def wait(events, stop, **kwargs):
            stop.wait(3)
            events.put(('naming_done', dict(state='cancelled')))
        with patch('naming.window.worker', side_effect=wait):
            self.app.naming_widgets['scan'].invoke()
            with patch('pdf.window.messagebox.askyesno', return_value=True):
                self.app._on_close()
            self.pump_until(lambda: self.app._closed)
        self.assertTrue(self.app.stop_event.is_set())
