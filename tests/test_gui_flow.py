"""Selected-format exports, view state and cooperative GUI scheduling."""

import os
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import customtkinter as ctk

import test_export_window as fixtures
from dxf_dwg import exporter as ex
from gui.theme import ACCENT_BG
from k_factor.window import AUTOMATIC_TAB, MANUAL_TAB, RESULTS_TAB
from pdf.settings import load_settings, save_settings
from pdf.window import GokworksPdfApp


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'GUI requires a display')
class GUIFlowTests(unittest.TestCase):
    setUp = fixtures.WindowTests.setUp
    close_app = fixtures.WindowTests.close_app
    wait_idle = fixtures.WindowTests.wait_idle

    def pump_until(self, predicate, timeout=5):
        deadline = time.monotonic()+timeout
        while not predicate() and time.monotonic() < deadline:
            self.app.update()
            time.sleep(.002)
        self.assertTrue(predicate())

    def test_legacy_combined_format_migrates_and_stays_single_on_restart(self):
        self.app._on_close()
        save_settings({'dxf_dwg_format': 'DXF + DWG'}, self.settings)
        self.app = GokworksPdfApp(settings_path=self.settings)
        self.app.report_callback_exception = lambda *args: self.errors.append(args)
        self.app._switch_mode('dxf_dwg')
        self.app.update()
        selector = next(control for control in self.app.controls
                        if isinstance(control, ctk.CTkSegmentedButton))
        self.assertEqual(selector.cget('values'), ['DXF', 'DWG'])
        self.assertEqual(self.app.output_format.get(), 'DXF')
        self.app._on_close()
        self.assertEqual(load_settings(self.settings)['dxf_dwg_format'], 'DXF')

    def test_selected_dwg_exports_only_dwg_even_when_dxf_would_fail(self):
        part = self.root/'sheet.sldprt'
        part.touch()
        model = fixtures.FakePart(part)
        model.fail.add('.dxf')
        assembly = fixtures.FakeAssembly(self.root/'main.sldasm', [fixtures.FakeComponent(part)])
        com = SimpleNamespace(VT_BYREF=1, VT_I4=2, VT_EMPTY=0,
                              CoInitialize=Mock(), CoUninitialize=Mock())
        self.app._switch_mode('dxf_dwg')
        self.app.source_folder.set(str(self.root))
        self.app.output_folder.set(str(self.root/'output'))
        self.app.output_format.set('DWG')
        with patch.multiple(ex, pythoncom=com,
                            win32com=SimpleNamespace(client=SimpleNamespace(VARIANT=fixtures.Variant))), \
                patch.object(ex, 'connect_to_solidworks',
                             return_value=fixtures.FakeApp(model, previous=assembly)):
            self.app.start_button.invoke()
            self.wait_idle()
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(Path(model.calls[0][0]).suffix, '.dwg')
        result = self.app.results[0]
        self.assertEqual(result['status'], 'success', result['detail'])
        self.assertEqual(result['outputs'][0]['format'], 'DWG')
        self.assertEqual(list((self.root/'output').glob('*.dxf')), [])
        self.assertTrue((self.root/'output'/'sheet - 2 mm - 1 adet.dwg').is_file())

    def test_invalid_format_does_not_start_worker_or_clear_existing_results(self):
        self.app._switch_mode('dxf_dwg')
        self.app.source_folder.set(str(self.root))
        self.app.output_folder.set(str(self.root/'output'))
        self.app.output_format.set('DXF + DWG')
        self.app.results.append(dict(source='existing.sldprt', status='success',
                                     output='existing.dxf', detail='ready'))
        with patch('pdf.window.export_parts') as worker:
            self.app._start_export()
        worker.assert_not_called()
        self.assertFalse(self.app.busy)
        self.assertEqual(len(self.app.results), 1)
        self.assertIn('DXF veya DWG', self.app.status_label.cget('text'))

    def test_rapid_navigation_defers_io_and_close_flushes_every_page(self):
        with patch('pdf.window.save_settings', wraps=save_settings) as writer:
            self.app.source_folder.set('/pdf/source')
            self.app._switch_mode('dxf_dwg')
            self.app.output_folder.set('/dxf/output')
            self.app.output_format.set('DWG')
            self.app._switch_mode('k_factor')
            self.app.k_state['manual_k'].set('0,274')
            self.app._switch_mode('iso_fits')
            self.app.iso_state['diameter'].set('60')
            self.app._switch_mode('geometric_tolerances')
            writer.assert_not_called()
            self.app._on_close()
        saved = load_settings(self.settings)
        self.assertEqual(saved['pdf_source'], '/pdf/source')
        self.assertEqual(saved['dxf_dwg_output'], '/dxf/output')
        self.assertEqual(saved['dxf_dwg_format'], 'DWG')
        self.assertEqual(saved['kr_manual_k'], '0,274')
        self.assertEqual(saved['iso_diameter'], '60')
        self.assertEqual(saved['unrelated_setting'], 'keep')

    def test_preference_retry_keeps_departed_page_snapshot(self):
        self.app.source_folder.set('/pending/pdf')
        self.app._switch_mode('dxf_dwg')
        with patch('pdf.window.save_settings', side_effect=OSError('disk unavailable')):
            self.app._save_preferences()
        self.assertEqual(self.app._pending_preferences['pdf_source'], '/pending/pdf')
        self.app.output_folder.set('/retry/output')
        self.app._save_preferences()
        saved = load_settings(self.settings)
        self.assertEqual(saved['pdf_source'], '/pending/pdf')
        self.assertEqual(saved['dxf_dwg_output'], '/retry/output')
        self.assertFalse(self.app._pending_preferences)
        with patch('pdf.window.save_settings') as writer:
            self.app._save_preferences()
        writer.assert_not_called()

    def test_rapid_menu_clicks_leave_only_final_page_highlighted(self):
        for mode in ('dxf_dwg', 'k_factor', 'iso_fits', 'pdf', 'geometric_tolerances'):
            self.app.nav_buttons[mode].invoke()
            self.app.update()
        self.pump_until(lambda: self.app._nav_anim_id is None)
        self.assertEqual(self.app.mode, 'geometric_tolerances')
        for mode, button in self.app.nav_buttons.items():
            self.assertEqual(button.cget('fg_color'),
                             ACCENT_BG if mode == self.app.mode else 'transparent')

    def test_k_result_view_preserves_manual_recipe_and_fixed_actions(self):
        self.app._switch_mode('k_factor')
        self.app._select_k_assignment(MANUAL_TAB)
        self.app.k_state['manual_k'].set('0,274')
        self.app.k_state['manual_r'].set('2')
        for selection in (RESULTS_TAB, AUTOMATIC_TAB, MANUAL_TAB, RESULTS_TAB):
            self.app._select_k_view(selection)
            self.app.update()
            self.assertTrue(self.app.scan_button.winfo_viewable())
            self.assertTrue(self.app.open_button.winfo_viewable())
        self.assertEqual(self.app.k_state['assignment_mode'].get(), MANUAL_TAB)
        self.assertEqual(self.app.k_state['manual_k'].get(), '0,274')
        self.app._switch_mode('pdf')
        self.app._switch_mode('k_factor')
        self.app.update()
        self.assertEqual(self.app.k_widgets['work_view'].get(), RESULTS_TAB)
        self.assertTrue(self.app.table.winfo_viewable())
        self.app._focus_search()
        self.app.update()
        self.assertIs(self.app.focus_get(), self.app.search_entry._entry)

    def test_k_scan_automatically_opens_full_result_view(self):
        self.app._switch_mode('k_factor')
        def preview(recipe, events, stop, **options):
            events.put(('done', dict(state='empty', total=0, processed=0,
                                    succeeded=0, skipped=0, failed=0, error='')))
        with patch('k_factor.window.update_assembly', side_effect=preview):
            self.app.scan_button.invoke()
            self.wait_idle()
        self.assertEqual(self.app.k_widgets['work_view'].get(), RESULTS_TAB)
        self.assertTrue(self.app.result_tabs.winfo_viewable())

    def test_large_preview_yields_to_stop_before_completing_list(self):
        paths = [str(self.root/f'part-{i}.slddrw') for i in range(4000)]
        self.app._set_busy(True)
        self.app.events.put(('preview', paths))
        # Stop is serviced between list batches, while navigation stays locked.
        observations = []
        def stop_during_list():
            if self.app._pending_files is None:
                self.app.after(1, stop_during_list)
                return
            observations.append((self.app.busy, len(self.app.row_ids)))
            self.app.stop_button.invoke()
        self.app.after(1, stop_during_list)
        self.wait_idle()
        self.assertTrue(observations)
        self.assertTrue(observations[0][0])
        self.assertLess(observations[0][1], len(paths))
        self.assertEqual(len(self.app.table.get_children()), len(paths))
        self.assertIn('durduruldu', self.app.status_label.cget('text'))

    def test_large_worker_list_precedes_results_and_done(self):
        paths = [str(self.root/f'part-{i}.slddrw') for i in range(1500)]
        self.app._set_busy(True)
        self.app.events.put(('files', paths))
        self.app.events.put(('result', dict(source=paths[-1], output='last.pdf',
                                           status='success', detail='ready')))
        self.app.events.put(('done', dict(state='completed', total=len(paths), processed=1,
                                         succeeded=1, skipped=0, failed=0, error='')))
        self.wait_idle()
        self.assertEqual(len(self.app.row_ids), len(paths))
        self.assertEqual(self.app.table.item(self.app.row_ids[paths[-1]], 'values')[1], 'Başarılı')
        self.assertEqual(self.app.stat_values['succeeded'].cget('text'), '1')


if __name__ == '__main__':
    unittest.main()
