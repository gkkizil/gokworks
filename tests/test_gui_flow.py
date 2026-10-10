"""Selected-format exports, view state and cooperative GUI scheduling."""

import unittest
from pathlib import Path
from unittest.mock import patch

import customtkinter as ctk
from support.gui import GuiTestCase
from support.solidworks import (
    FakeApp,
    FakeAssembly,
    FakeComponent,
    FakePart,
    solidworks_session,
)

from dxf_dwg import exporter as ex
from gui.theme import ACCENT_BG
from k_factor.window import AUTOMATIC_TAB, MANUAL_TAB, RESULTS_TAB
from pdf.settings import load_settings, save_settings


class GUIFlowTests(GuiTestCase):
    def test_legacy_combined_format_migrates_and_stays_single_on_restart(self):
        self.app._on_close()
        save_settings({'dxf_dwg_format': 'DXF + DWG'}, self.settings)
        self.open_app()
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
        model = FakePart(part)
        model.fail.add('.dxf')
        assembly = FakeAssembly(self.root/'main.sldasm', [FakeComponent(part)])
        self.app._switch_mode('dxf_dwg')
        self.app.source_folder.set(str(self.root))
        self.app.output_folder.set(str(self.root/'output'))
        self.app.output_format.set('DWG')
        with solidworks_session(ex, FakeApp(model, previous=assembly), 'dxf'):
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

    def test_worker_batch_retains_every_result_and_log_with_one_visible_update(self):
        paths = [str(self.root/f'part-{i}.slddrw') for i in range(8)]
        self.app._fill_files(paths)
        self.app.after_cancel(self.app._poll_id)
        expected = []
        self.app.events.put(('phase', 'Aktarım hazırlanıyor'))
        self.app.events.put(('log', 'Başlangıç'))
        for index, path in enumerate(paths, 1):
            result = dict(source=path, output=path+'.pdf', status='success', detail=f'Sonuç {index}')
            expected.append(result)
            for event in (('current', path), ('result', result),
                          ('counts', dict(total=8, succeeded=index)), ('progress', (index, 8))):
                self.app.events.put(event)
        self.app.events.put(('log', 'Bitiş'))
        with patch('pdf.window.time.perf_counter', return_value=0), \
                patch.object(self.app.log_box, 'insert', wraps=self.app.log_box.insert) as logs, \
                patch.object(self.app.progress, 'set', wraps=self.app.progress.set) as progress, \
                patch.object(self.app.table, 'see', wraps=self.app.table.see) as scroll:
            self.app._process_events()
        self.assertEqual(self.app.results, expected)
        self.assertEqual((logs.call_count, progress.call_count, scroll.call_count), (1, 1, 1))
        self.assertEqual(self.app.progress.get(), 1)
        self.assertEqual(self.app.stat_values['succeeded'].cget('text'), '8')
        for index, path in enumerate(paths, 1):
            self.assertEqual(self.app.table.item(self.app.row_ids[path], 'values')[1:],
                             ('Başarılı', f'Sonuç {index}'))
        text = self.app.log_box.get('1.0', 'end')
        messages = ['Başlangıç', *[f'Sonuç {i}' for i in range(1, 9)], 'Bitiş']
        self.assertEqual([text.index(message) for message in messages],
                         sorted(text.index(message) for message in messages))
        self.assertIsNone(self.app._worker_updates)

    def test_worker_batch_keeps_total_event_order_and_final_summary_in_each_module(self):
        for mode in ('pdf', 'dxf_dwg', 'k_factor'):
            self.app._switch_mode(mode)
            for events, total in [([('counts', dict(total=9)), ('total', 21)], '21'),
                                  ([('total', 21), ('counts', dict(total=9))], '9')]:
                with self.subTest(mode=mode, total=total):
                    self.app.after_cancel(self.app._poll_id)
                    for event in events:
                        self.app.events.put(event)
                    self.app._process_events()
                    self.assertEqual(self.app.stat_values['total'].cget('text'), total)
            self.app._set_busy(True)
            self.app.events.put(('counts', dict(total=99, failed=99)))
            self.app.events.put(('phase', 'Eski durum'))
            self.app.events.put(('done', dict(state='completed', total=3, processed=3,
                                              succeeded=3, skipped=0, failed=0)))
            self.app.after_cancel(self.app._poll_id)
            self.app._process_events()
            self.assertFalse(self.app.busy)
            self.assertEqual(self.app.stat_values['succeeded'].cget('text'), '3')
            self.assertEqual(self.app.stat_values['failed'].cget('text'), '0')
            self.assertIn('Tamamlandı', self.app.status_label.cget('text'))

    def test_worker_log_burst_yields_between_batches_without_losing_messages(self):
        self.app.after_cancel(self.app._poll_id)
        for index in range(120):
            self.app.events.put(('log', f'Mesaj {index:03}'))
        with patch('pdf.window.time.perf_counter', return_value=0):
            self.app._process_events()
            self.assertEqual(self.app.events.qsize(), 20)
            self.app.after_cancel(self.app._poll_id)
            self.app._process_events()
        text = self.app.log_box.get('1.0', 'end')
        self.assertEqual(text.count('Mesaj '), 120)
        self.assertLess(text.index('Mesaj 099'), text.index('Mesaj 100'))
        self.assertTrue(self.app.events.empty())

    def test_log_scrolling_stays_with_reader_and_follows_again_at_bottom(self):
        self.app.result_tabs.set('Günlük')
        self.settle(.15)
        self.app._write_log(''.join(f'Eski satır {index}\n' for index in range(200)))
        self.app.update_idletasks()
        self.assertGreater(self.app.log_box.yview()[1], .99)
        self.app.log_box.yview_moveto(0)
        self.app.update_idletasks()
        with patch.object(self.app.log_box, 'see', wraps=self.app.log_box.see) as scroll:
            self.app._append_log('Yeni satır')
            self.app.update_idletasks()
        scroll.assert_not_called()
        self.assertLess(self.app.log_box.yview()[0], .01)
        self.app.log_box.yview_moveto(1)
        self.app._append_log('Takip yeniden açık')
        self.app.update_idletasks()
        self.assertGreater(self.app.log_box.yview()[1], .99)


if __name__ == '__main__':
    unittest.main()
