"""Real Tk naming workflow, preview validation, themes and page persistence."""

from pathlib import Path
import json
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
        self.app.naming_state['parent'].set(str(self.root))
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
        destination = self.root/'Yeni-paket'
        self.assertTrue((destination/'ÖZEL-LEVHA.slddrw').is_file())
        self.assertTrue((destination/naming.REPORT_NAME).is_file())
        self.assertEqual(widgets['save'].cget('state'), 'disabled')
        self.assertEqual(self.app.nav_buttons['pdf'].cget('state'), 'normal')

    def test_invalid_rules_existing_folder_and_failed_rescan_disable_save(self):
        self.scan()
        self.app.naming_state['prefix'].set('bad:')
        self.settle()
        self.assertEqual(self.app.naming_widgets['save'].cget('state'), 'disabled')
        self.app.naming_state['prefix'].set('PROJE-')
        (self.root/'Yeni-paket').mkdir()
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
                for key in ('scan', 'save', 'stop', 'table', 'parent', 'prefix', 'mode', 'package', 'suffix', 'start', 'digits'):
                    self.assert_inside(self.app.naming_widgets[key])
                for key in ('active_source', 'source_browse', 'source_pick', 'source_folder', 'source_file'):
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

    def test_folder_and_file_picker_invalidate_old_preview_and_save_selected_source(self):
        self.scan()
        widgets = self.app.naming_widgets
        source = str(self.root/'Ana.sldasm')
        with patch('naming.window.filedialog.askdirectory', return_value=str(self.root)), \
                patch('naming.window.filedialog.askopenfilename', return_value=source) as picker:
            widgets['source_browse'].invoke()
        self.assertEqual(picker.call_args.kwargs['initialdir'], str(self.root))
        self.assertEqual(self.app.naming_state['source_mode'].get(), 'Dosyadan')
        self.assertEqual(self.app.naming_state['source_folder'].get(), str(self.root))
        self.assertEqual(self.app.naming_state['source_file'].get(), source)
        self.assertIsNone(self.app.naming_snapshot)
        self.assertFalse(widgets['table'].get_children())
        self.assertEqual(widgets['save'].cget('state'), 'disabled')
        self.scan()
        self.assertEqual(self.app.naming_snapshot.source_path, source)
        self.assertEqual(widgets['save'].cget('state'), 'normal')
        with patch('naming.exporter.connect_to_solidworks', return_value=self.sw):
            widgets['save'].invoke()
            self.wait_idle()
        self.assertEqual(self.sw.saves, 1)

    def test_cancelled_source_selection_and_empty_folder_cannot_use_stale_plan(self):
        self.scan()
        snapshot = self.app.naming_snapshot
        with patch('naming.window.filedialog.askdirectory', return_value=''):
            self.app.naming_widgets['source_browse'].invoke()
        self.assertIs(self.app.naming_snapshot, snapshot)
        with patch('naming.window.filedialog.askdirectory', return_value=str(self.root)), \
                patch('naming.window.filedialog.askopenfilename', return_value=''):
            self.app.naming_widgets['source_browse'].invoke()
        with patch('naming.window.worker') as worker:
            self.app.naming_widgets['scan'].invoke()
        worker.assert_not_called()
        self.assertFalse(self.app.busy)
        self.assertIsNone(self.app.naming_snapshot)
        self.assertEqual(self.app.naming_widgets['save'].cget('state'), 'disabled')
        self.assertIn('dosyayı seçin', self.app.naming_widgets['status'].cget('text'))

    def test_active_assembly_button_reads_source_and_rejects_active_part(self):
        self.app.naming_state['source_file'].set(str(self.root/'Levha.sldprt'))
        with patch('naming.exporter.connect_to_solidworks', return_value=self.sw):
            self.app.naming_widgets['active_source'].invoke()
            self.wait_idle()
        self.assertEqual(self.app.naming_state['source_mode'].get(), 'Aktif montaj')
        self.assertIsNone(self.app.naming_snapshot.source_path)
        self.assertTrue(self.app.naming_snapshot.require_assembly)
        self.assertEqual(self.app.naming_state['source_file'].get(), self.sw.paths[0])
        self.sw.ActiveDoc.GetType = lambda: 1
        with patch('naming.exporter.connect_to_solidworks', return_value=self.sw):
            self.app.naming_widgets['active_source'].invoke()
            self.wait_idle()
        self.assertIsNone(self.app.naming_snapshot)
        self.assertIn('montaj', self.app.naming_widgets['status'].cget('text').lower())
        self.assertEqual(self.app.naming_widgets['save'].cget('state'), 'disabled')

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
