"""BOM occurrence counts, hierarchy, Excel content and failure atomicity."""

from dataclasses import replace
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from unittest.mock import patch

from openpyxl import load_workbook
from bom import exporter as bom
from support.solidworks import FakeAssembly, FakeApp, FakeComponent, install_com


class Component(FakeComponent):
    def __init__(self, path, *args, name=None, excluded=False, **kwargs):
        super().__init__(path, *args, **kwargs)
        self.Name2 = name or Path(path).stem+'-1'
        self.ExcludeFromBOM = excluded


class BomTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        plate = Component(r'C:\İmalat\Parça 2.SLDPRT', name='Parça 2-1')
        bolt = Component(r'C:\İmalat\Parça 10.SLDPRT', name='Parça 10-1')
        branch = Component(r'C:\İmalat\ÖRNEK-M001.SLDASM', children=[bolt, plate])
        hidden = Component(r'C:\İmalat\Parça 2.SLDPRT', name='Parça 2-2')
        hidden.IsHidden = True
        self.assembly = FakeAssembly(r'C:\İmalat\Ana.SLDASM', [branch, branch, hidden])
        self.app = FakeApp(self.assembly)

    def test_repeated_subassemblies_keep_occurrences_hierarchy_and_natural_name_order(self):
        result = bom.collect(self.app)
        self.assertEqual([p.name for p in result.parts], ['Parça 2', 'Parça 10'])
        self.assertEqual([p.quantity for p in result.parts], [3, 2])
        self.assertEqual(result.total_parts, 5)
        self.assertEqual(len(result.tree), 7)
        assemblies = [n for n in result.tree if n.kind == 'Montaj']
        self.assertEqual(len(assemblies), 2)
        for assembly in assemblies:
            children = [n for n in result.tree if n.parent == assembly.number]
            self.assertEqual([n.name for n in children], ['Parça 2', 'Parça 10'])
            self.assertTrue(all(n.level == 2 for n in children))
        self.assertEqual(result.parts[0].path, r'C:\İmalat\Parça 2.SLDPRT')
        self.assertEqual(self.app.closed, [])
        self.assertEqual(self.app.open_count, 0)
        self.assertEqual(self.assembly.ConfigurationManager.ActiveConfiguration.Name, 'Assembly-Default')

    def test_same_names_different_files_and_configurations_do_not_merge(self):
        self.assembly.root.children = [Component('/a/same.sldprt', 'Default'),
            Component('/a/same.sldprt', 'İnce'), Component('/b/same.sldprt', 'Default'),
            Component('/A/SAME.SLDPRT', 'Default')]
        result = bom.collect(self.app)
        self.assertEqual(len(result.parts), 3)
        self.assertEqual(sorted(p.quantity for p in result.parts), [1, 1, 2])

    def test_nested_assemblies_preserve_parent_and_level(self):
        nested = Component('/deep.sldasm', children=[Component('/part.sldprt')])
        self.assembly.root.children = [Component('/outer.sldasm', children=[nested])]
        result = bom.collect(self.app)
        self.assertEqual([(n.number, n.parent, n.level) for n in result.tree],
                         [('1', '', 1), ('1.1', '1', 2), ('1.1.1', '1.1', 3)])

    def test_suppressed_and_excluded_branches_are_omitted_hidden_are_counted(self):
        self.assembly.root.children += [Component('/supp.sldasm', state=0,
                children=[Component('/unreadable', state=1)]),
            Component('/excluded.sldasm', excluded=True, children=[Component('/only.sldprt')])]
        result = bom.collect(self.app)
        self.assertEqual((result.total_parts, result.suppressed, result.excluded), (5, 1, 1))
        included = bom.collect(self.app, include_excluded=True)
        self.assertEqual((included.total_parts, included.suppressed, included.excluded), (6, 1, 0))

    def test_modern_bom_exclusion_uses_active_configuration_and_rejects_unreadable_value(self):
        child = Component('/excluded.sldprt')
        child.GetExcludeFromBOM2 = lambda option, configs: (True,) if (option, configs) == (1, None) else None
        self.assembly.root.children = [child]
        self.assertEqual(bom.collect(self.app).excluded, 1)
        self.assertEqual(bom.collect(self.app, include_excluded=True).total_parts, 1)
        child.GetExcludeFromBOM2 = lambda *_: None
        with self.assertRaisesRegex(RuntimeError, 'BOM dışı durumu'):
            bom.collect(self.app)

    def test_required_api_errors_prevent_partial_result(self):
        cases = [Component('/a.sldprt', state=1), Component(''), Component('/a.sldprt', ''),
                 Component('/a.unknown'), Component('/sub.sldasm')]
        cases[-1].model = None
        for child in cases:
            with self.subTest(path=child.path):
                self.assembly.root.children = [child]
                with self.assertRaises(RuntimeError):
                    bom.collect(self.app)

    def test_cycles_speedpak_and_unresolved_assembly_fail(self):
        self.assembly.root.children = [Component(self.assembly.path, 'Assembly-Default')]
        with self.assertRaisesRegex(RuntimeError, 'döngü'):
            bom.collect(self.app)
        self.assembly.resolve_status = 1
        with self.assertRaisesRegex(RuntimeError, 'çözümlenemedi'):
            bom.collect(self.app)
        self.assembly.resolve_status = 0
        self.assembly.ConfigurationManager.ActiveConfiguration.IsSpeedPak = True
        with self.assertRaisesRegex(RuntimeError, 'SpeedPak'):
            bom.collect(self.app)

    def test_non_assembly_and_cancelled_scan_do_not_return_partial_bom(self):
        with self.assertRaisesRegex(RuntimeError, 'ana montaj'):
            bom.collect(FakeApp(None))
        stop = threading.Event()
        stop.set()
        with self.assertRaises(bom.Cancelled):
            bom.collect(self.app, stop)
        self.assembly.root.children = [Component(f'/p{i}.sldprt') for i in range(101)]
        stop.clear()
        with self.assertRaises(bom.Cancelled):
            bom.collect(self.app, stop_event=stop, progress=lambda _: stop.set())

    def test_excel_has_sorted_numeric_totals_and_grouped_tree_under_assembly(self):
        result = bom.collect(self.app)
        destination = self.folder/'bom.xlsx'
        bom.export_excel(result, destination)
        book = load_workbook(destination)
        self.addCleanup(book.close)
        self.assertEqual(book.sheetnames, ['Parça listesi', 'Ürün ağacı'])
        parts, tree = book.worksheets
        self.assertEqual([parts.cell(i, 2).value for i in (5, 6)], ['Parça 2', 'Parça 10'])
        self.assertEqual([parts.cell(i, 3).value for i in (5, 6)], [3, 2])
        self.assertEqual(parts.cell(5, 3).data_type, 'n')
        self.assertEqual(parts.freeze_panes, 'A5')
        for index, node in enumerate(result.tree, 5):
            self.assertEqual(tree.cell(index, 1).value, node.number)
            self.assertEqual(tree.cell(index, 4).value, node.name)
            self.assertEqual(tree.cell(index, 4).alignment.indent, node.level-1)
            self.assertEqual(tree.row_dimensions[index].outlineLevel, node.level-1)
            if node.kind == 'Montaj':
                self.assertTrue(tree.cell(index, 4).font.bold)
                self.assertEqual(tree.cell(index+1, 2).value, node.number)
        self.assertFalse(tree.sheet_properties.outlinePr.summaryBelow)

    def test_excel_formula_like_names_stay_literal(self):
        result = bom.collect(self.app)
        result = replace(result, parts=(bom.Part('=SUM(1,2)', '=bad.sldprt', '+unsafe', 1),),
                         assembly='=unsafe.sldasm')
        destination = self.folder/'literal.xlsx'
        bom.export_excel(result, destination)
        book = load_workbook(destination, data_only=False)
        self.addCleanup(book.close)
        self.assertEqual(book.worksheets[0]['B5'].value, '=SUM(1,2)')
        self.assertEqual(book.worksheets[0]['B5'].data_type, 's')
        self.assertEqual(book.worksheets[0]['A2'].data_type, 's')

    def test_excel_failure_and_cancellation_preserve_existing_file_and_remove_staging(self):
        result = bom.collect(self.app)
        destination = self.folder/'existing.xlsx'
        destination.write_bytes(b'original')
        with patch('openpyxl.workbook.workbook.Workbook.save', side_effect=OSError('locked')):
            with self.assertRaises(OSError):
                bom.export_excel(result, destination)
        self.assertEqual(destination.read_bytes(), b'original')
        self.assertEqual(list(self.folder.glob('.gokworks*')), [])
        stop = threading.Event()
        real_replace = bom.os.replace
        with patch('bom.exporter.os.replace', side_effect=real_replace) as replace_file, \
                patch('openpyxl.workbook.workbook.Workbook.save', side_effect=lambda _: stop.set()):
            with self.assertRaises(bom.Cancelled):
                bom.export_excel(result, destination, stop)
            replace_file.assert_not_called()
        self.assertEqual(destination.read_bytes(), b'original')
        self.assertEqual(list(self.folder.glob('.gokworks*')), [])

    def test_worker_initializes_com_and_emits_only_complete_result(self):
        com, _ = install_com(self, bom, 'kr')
        events, stop = queue.Queue(), threading.Event()
        with patch('bom.exporter.connect_to_solidworks', return_value=self.app):
            bom.scan_worker(events, stop)
        event, outcome = events.get_nowait()
        self.assertEqual(event, 'bom_done')
        self.assertEqual(outcome['state'], 'completed')
        self.assertEqual(outcome['result'].total_parts, 5)
        com.CoInitialize.assert_called_once()
        com.CoUninitialize.assert_called_once()
        with patch('bom.exporter.collect', side_effect=RuntimeError('read failed')):
            with patch('bom.exporter.connect_to_solidworks', return_value=self.app):
                bom.scan_worker(events, stop)
        self.assertEqual(events.get_nowait()[1]['state'], 'error')


if __name__ == '__main__':
    unittest.main()
