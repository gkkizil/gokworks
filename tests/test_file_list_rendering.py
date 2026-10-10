"""Large result lists filter in bulk and retain live, independent row data."""

import os
import unittest
from unittest.mock import patch

import test_export_window as fixtures


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'GUI requires a display')
class FileListRenderingTests(unittest.TestCase):
    setUp = fixtures.WindowTests.setUp
    close_app = fixtures.WindowTests.close_app

    def paths(self, count, extension='slddrw'):
        return [str(self.root/f'İmalat-{i:05}.{extension}') for i in range(count)]

    def test_ten_thousand_rows_filter_in_bulk_without_losing_data_or_selection(self):
        paths = self.paths(10000)
        self.app._fill_files(paths)
        table = self.app.table
        table.selection_set('file_5')
        with patch.object(table, 'move', wraps=table.move) as move, \
                patch.object(table, 'detach', wraps=table.detach) as detach, \
                patch.object(table, 'item', wraps=table.item) as item, \
                patch.object(table, 'set_children', wraps=table.set_children) as bulk:
            self.app.search_query.set('imalat-000')
            self.assertEqual(table.get_children(), tuple(f'file_{i}' for i in range(100)))
            self.assertEqual(self.app.visible_count.cget('text'), '100 / 10000 dosya')
            self.app.search_query.set('')
        move.assert_not_called()
        detach.assert_not_called()
        item.assert_not_called()  # No unchanged tags or per-row Tk value reads.
        self.assertEqual(bulk.call_count, 2)
        self.assertEqual(len(table.get_children()), 10000)
        self.assertEqual(table.selection(), ('file_5',))
        self.assertEqual(table.item('file_9999', 'values'), ('İmalat-09999.slddrw', 'Bekliyor', ''))
        self.assertEqual(self.app.stat_values['total'].cget('text'), '10000')

    def test_out_of_order_results_restore_scan_order_and_refresh_searchable_details(self):
        paths = self.paths(120)
        self.app._fill_files(paths)
        self.app.status_filter.set('Hatalı')
        visible = set()
        for index in (119, 70, 2, 99, 0, 51):
            self.app._update_row(paths[index], 'error', 'İŞLEME sorunu')
            visible.add(index)
            self.assertEqual(self.app.table.get_children(),
                             tuple(f'file_{i}' for i in sorted(visible)))
        self.app.search_query.set('işleme')
        self.app._update_row(paths[70], 'error', 'Dosya kilitli')
        visible.remove(70)
        self.app._update_row(paths[3], 'error', 'İşleme sorunu')
        visible.add(3)
        self.assertEqual(self.app.table.get_children(), tuple(f'file_{i}' for i in sorted(visible)))
        self.app.search_query.set('kilitli')
        self.assertEqual(self.app.table.get_children(), ('file_70',))
        self.app._clear_filters()
        self.assertEqual(self.app.table.get_children(), tuple(f'file_{i}' for i in range(120)))
        self.assertEqual(self.app.table.item('file_70', 'values')[2], 'Dosya kilitli')

    def test_new_list_with_no_matches_detaches_inserted_rows_and_reuses_ids(self):
        old = self.paths(10)
        self.app._fill_files(old)
        self.app._update_row(old[0], 'error', 'Eski detay')
        self.app.search_query.set('eski detay')
        self.app._fill_files([str(self.root/'new.slddrw')])
        self.assertEqual(self.app.table.get_children(), ())
        self.app.search_query.set('new')
        self.assertEqual(self.app.table.get_children(), ('file_0',))
        self.app.search_query.set('eski')
        self.assertEqual(self.app.table.get_children(), ())
        self.assertFalse(self.app.table.exists('file_9'))

    def test_row_cache_and_live_updates_remain_independent_between_three_modules(self):
        for mode in ('pdf', 'dxf_dwg', 'k_factor'):
            self.app._switch_mode(mode)
            path = str(self.root/f'{mode}.sldprt')
            self.app._fill_files([path])
            self.app._update_row(path, 'error', f'{mode} bekliyor')
            self.app.search_query.set(mode)
            self.app.status_filter.set('Hatalı')
        for mode in ('pdf', 'dxf_dwg', 'k_factor'):
            self.app._switch_mode(mode)
            path = str(self.root/f'{mode}.sldprt')
            self.assertEqual(self.app.table.get_children(), ('file_0',))
            self.assertEqual(self.app.table.item('file_0', 'values')[2], f'{mode} bekliyor')
            self.app._update_row(path, 'success', f'{mode} tamamlandı')
            self.assertEqual(self.app.table.get_children(), ())
            self.app.status_filter.set('Başarılı')
            self.assertEqual(self.app.table.get_children(), ('file_0',))


if __name__ == '__main__':
    unittest.main()
