"""Pack and Go boundary, reference graph, filename rules and failure cleanup."""

from dataclasses import replace
import json
from pathlib import Path
import queue
from tempfile import TemporaryDirectory
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from naming import exporter as naming
from tests.support.solidworks import Variant


class Pack:
    def __init__(self, app):
        self.app = app
        self.IncludeDrawings = self.IncludeSuppressed = self.IncludeToolboxComponents = False
        self.IncludeSimulationResults = True
        self.AddPrefix = self.AddSuffix = ''
        self.names = list(app.paths)
        self.targets = list(self.names)
        self.FlattenToSingleFolder = False

    def GetDocumentNames(self):
        assert self.IncludeDrawings and self.IncludeSuppressed and self.IncludeToolboxComponents
        assert not self.IncludeSimulationResults
        return True, tuple(self.names)

    def GetDocumentNamesCount(self):
        return len(self.names)

    def GetDocumentSaveToNames(self):
        return True, tuple(self.targets), tuple(self.app.states)

    def SetSaveToName(self, override, folder):
        assert override is False
        self.folder = folder
        return True

    def SetDocumentSaveToNames(self, names):
        assert self.FlattenToSingleFolder
        values = names.value if isinstance(names, Variant) else names
        self.targets = list(values)
        self.app.last_mapping = dict(zip(self.names, self.targets))
        return not self.app.reject_names


class App:
    def __init__(self, folder):
        self.folder = folder
        definitions = {'Ana.sldasm': ['Alt.sldasm', 'Levha.sldprt'],
                       'Alt.sldasm': ['Cıvata.sldprt'], 'Levha.sldprt': ['Taban.sldprt'],
                       'Cıvata.sldprt': [], 'Taban.sldprt': [],
                       'Ana.slddrw': ['Ana.sldasm'], 'Levha.slddrw': ['Levha.sldprt']}
        self.paths = [str(folder/name) for name in definitions]
        self.states = [0]*len(self.paths)
        for name, refs in definitions.items():
            (folder/name).write_text(json.dumps(dict(refs=[str(folder/ref) for ref in refs],
                mates=['persistent-id-1'], configurations=['Default', 'İnce'], views=['Front', 'Section']),
                ensure_ascii=False), encoding='utf-8')
        self.dirty = False
        self.reject_names = False
        self.corrupt = False
        self.statuses = None
        self.on_save = None
        self.saves = 0
        self.last_mapping = None
        self.pack_class = Pack
        self.extension = SimpleNamespace(GetPackAndGo=lambda: self.pack_class(self), SavePackAndGo=self.save)
        self.ActiveDoc = SimpleNamespace(GetType=lambda: 2, GetPathName=lambda: self.paths[0],
                                         Extension=self.extension, GetSaveFlag=lambda: self.dirty)

    def GetOpenDocumentByName(self, path):
        return self.ActiveDoc if path == self.paths[0] else None

    def GetDocumentDependencies2(self, path, traverse, search, readonly):
        assert (traverse, search, readonly) == (False, False, False)
        values = json.loads(Path(path).read_text(encoding='utf-8'))['refs']
        return tuple(value for ref in values for value in (Path(ref).name, ref))

    def save(self, pg):
        self.saves += 1
        mapping = dict(zip(pg.names, pg.targets))
        for source, target in mapping.items():
            content = json.loads(Path(source).read_text(encoding='utf-8'))
            if not self.corrupt:
                content['refs'] = [mapping[ref] for ref in content['refs']]
            Path(target).write_text(json.dumps(content, ensure_ascii=False), encoding='utf-8')
        if self.on_save:
            self.on_save()
        return self.statuses if self.statuses is not None else (0,)*len(mapping)


def install_com(test):
    com = SimpleNamespace(VT_ARRAY=8192, VT_BSTR=8, VT_BYREF=16384, VT_VARIANT=12,
                           CoInitialize=Mock(), CoUninitialize=Mock())
    test.enterContext(patch.multiple(naming, pythoncom=com,
                                     win32com=SimpleNamespace(client=SimpleNamespace(VARIANT=Variant))))
    return com


class NamingTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.app = App(self.folder)
        self.destination = self.folder/'new-package'

    def plan(self, **rules):
        snapshot = naming.scan(self.app)
        entries = naming.plan_names(snapshot, self.destination, naming.Rules(**rules))
        return snapshot, entries

    def test_package_updates_assembly_drawing_and_derived_part_references_with_exact_mapping(self):
        originals = {path: Path(path).read_bytes() for path in self.app.paths}
        snapshot, entries = self.plan(prefix='PROJE-', suffix='-R1', find='Levha', replacement='Sac')
        report = naming.execute(self.app, snapshot, entries, self.destination)
        self.assertTrue(report['file_references_verified'])
        self.assertEqual(list(self.app.last_mapping), self.app.paths)
        self.assertEqual(Path(report['root']).name, 'PROJE-Ana-R1.sldasm')
        for entry in entries:
            source = json.loads(originals[entry.source])
            saved = json.loads(Path(entry.destination).read_text(encoding='utf-8'))
            self.assertEqual(saved['refs'], [self.app.last_mapping[ref] for ref in source['refs']])
            for field in ('mates', 'configurations', 'views'):
                self.assertEqual(saved[field], source[field])
            self.assertEqual(Path(entry.source).read_bytes(), originals[entry.source])
        self.assertTrue((self.destination/naming.REPORT_NAME).is_file())

    def test_numbered_models_and_manual_names_keep_paired_drawing_name(self):
        snapshot = naming.scan(self.app)
        entries = naming.plan_names(snapshot, self.destination, naming.Rules(prefix='P-', numbered=True, start=10, digits=4),
                                     {str(self.folder/'Levha.sldprt'): 'ÖZEL-LEVHA'})
        names = {Path(entry.source).name: Path(entry.destination).name for entry in entries}
        self.assertEqual(names['Levha.sldprt'], 'ÖZEL-LEVHA.sldprt')
        self.assertEqual(names['Levha.slddrw'], 'ÖZEL-LEVHA.slddrw')
        self.assertEqual(Path(names['Ana.sldasm']).stem, Path(names['Ana.slddrw']).stem)
        self.assertTrue(names['Alt.sldasm'].startswith('P-0010'))

    def test_invalid_names_and_case_insensitive_collisions_block_plan(self):
        snapshot = naming.scan(self.app)
        for stem in ('', '../bad', 'NUL', 'COM1.data', ' trailing ', 'trailing.', 'bad:name'):
            with self.subTest(stem=stem), self.assertRaises(ValueError):
                naming.plan_names(snapshot, self.destination, overrides={self.app.paths[0]: stem})
        with self.assertRaisesRegex(ValueError, 'çakışıyor'):
            naming.plan_names(snapshot, self.destination, overrides={str(self.folder/'Levha.sldprt'): 'same',
                str(self.folder/'Cıvata.sldprt'): 'SAME'})
        with self.assertRaises(ValueError):
            naming.plan_names(snapshot, self.folder)
        self.assertEqual(self.app.saves, 0)

    def test_existing_output_is_not_overwritten(self):
        snapshot, entries = self.plan(prefix='new-')
        self.destination.mkdir()
        file = self.destination/'keep.txt'
        file.write_text('original')
        with self.assertRaises(ValueError):
            naming.execute(self.app, snapshot, entries, self.destination)
        self.assertEqual(file.read_text(), 'original')
        self.assertEqual(self.app.saves, 0)

    def test_selected_empty_folder_is_used_directly_and_references_are_preserved(self):
        self.destination.mkdir()
        snapshot, entries = self.plan(prefix='NEW-')
        report = naming.execute(self.app, snapshot, entries, self.destination)
        self.assertTrue(report['file_references_verified'])
        self.assertEqual(Path(report['root']).parent, self.destination)
        self.assertEqual(Path(report['root']).name, 'NEW-Ana.sldasm')
        self.assertFalse((self.destination/'Yeni-paket').exists())

    def test_failed_save_preserves_the_selected_existing_empty_folder(self):
        self.destination.mkdir()
        snapshot, entries = self.plan(prefix='NEW-')
        self.app.statuses = ()
        with self.assertRaises(RuntimeError):
            naming.execute(self.app, snapshot, entries, self.destination)
        self.assertTrue(self.destination.is_dir())
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_destination_filled_after_preview_is_rejected_without_saving(self):
        self.destination.mkdir()
        snapshot, entries = self.plan(prefix='NEW-')
        marker = self.destination/'keep.txt'
        marker.write_text('keep')
        with self.assertRaisesRegex(ValueError, 'boş olmalı'):
            naming.execute(self.app, snapshot, entries, self.destination)
        self.assertEqual(marker.read_text(), 'keep')
        self.assertEqual(self.app.saves, 0)

    def test_destination_validation_rejects_sources_files_and_missing_parent(self):
        snapshot = naming.scan(self.app)
        for destination in ('', self.folder, self.app.paths[0], self.folder/'missing'/'new'):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                naming.validate_destination(destination, snapshot)
        self.assertEqual(naming.validate_destination(self.destination, snapshot), self.destination)

    def test_name_planning_does_not_access_the_destination_filesystem(self):
        snapshot = naming.scan(self.app)
        with patch.object(Path, 'iterdir', side_effect=AssertionError('filesystem in preview')), \
                patch.object(Path, 'is_dir', side_effect=AssertionError('filesystem in preview')):
            entries = naming.plan_names(snapshot, self.destination, naming.Rules(prefix='NEW-'))
        self.assertEqual(len(entries), len(snapshot.documents))

    def test_partial_save_and_reference_mismatch_remove_created_outputs(self):
        for failure in ('status', 'references', 'empty_status'):
            with self.subTest(failure=failure):
                snapshot, entries = self.plan(prefix='new-')
                self.app.statuses = (0,)*6+(4,) if failure == 'status' else () if failure == 'empty_status' else None
                self.app.corrupt = failure == 'references'
                with self.assertRaises(RuntimeError):
                    naming.execute(self.app, snapshot, entries, self.destination)
                self.assertFalse(self.destination.exists())
                self.assertTrue(all(Path(path).is_file() for path in self.app.paths))

    def test_changed_source_after_preview_requires_new_scan(self):
        snapshot, entries = self.plan(prefix='new-')
        Path(self.app.paths[3]).write_text(Path(self.app.paths[3]).read_text()+' ')
        with self.assertRaisesRegex(RuntimeError, 'önizlemeden sonra değişti'):
            naming.execute(self.app, snapshot, entries, self.destination)
        self.assertEqual(self.app.saves, 0)
        self.assertFalse(self.destination.exists())

    def test_unsaved_virtual_missing_and_external_references_block_before_write(self):
        self.app.dirty = True
        with self.assertRaisesRegex(RuntimeError, 'Kaydedilmemiş'):
            naming.scan(self.app)
        self.app.dirty = False
        self.app.states[1] = 1
        with self.assertRaisesRegex(RuntimeError, 'Sanal'):
            naming.scan(self.app)
        self.app.states[1] = 0
        Path(self.app.paths[0]).write_text(json.dumps({'refs': [str(self.folder/'missing.sldprt')]}))
        with self.assertRaisesRegex(RuntimeError, 'Paket dışında'):
            naming.scan(self.app)
        self.assertEqual(self.app.saves, 0)

    def test_cancel_before_or_during_pack_save_leaves_no_completed_output(self):
        snapshot, entries = self.plan(prefix='new-')
        stop = threading.Event()
        stop.set()
        with self.assertRaises(naming.Cancelled):
            naming.execute(self.app, snapshot, entries, self.destination, stop)
        self.assertEqual(self.app.saves, 0)
        stop.clear()
        self.app.on_save = stop.set
        with self.assertRaises(naming.Cancelled):
            naming.execute(self.app, snapshot, entries, self.destination, stop)
        self.assertFalse(self.destination.exists())

    def test_ignored_name_mapping_and_changed_extensions_never_save(self):
        snapshot, entries = self.plan(prefix='new-')
        class IgnoredPack(Pack):
            def SetDocumentSaveToNames(self, names):
                return True
        self.app.pack_class = IgnoredPack
        with self.assertRaisesRegex(RuntimeError, 'eşleştirmedi'):
            naming.execute(self.app, snapshot, entries, self.destination)
        self.app.pack_class = Pack
        bad = (replace(entries[0], destination=str(self.destination/'invalid.txt')), *entries[1:])
        with self.assertRaisesRegex(ValueError, 'uzantısı'):
            naming.execute(self.app, snapshot, bad, self.destination)
        self.assertEqual(self.app.saves, 0)

    def test_byref_getters_and_bstr_array_are_supported(self):
        install_com(self)
        class ByRefPack(Pack):
            def SetSaveToName(self, override, folder):
                super().SetSaveToName(override, folder)
                return False  # The override is disabled, not a save failure.
            def GetDocumentNames(self, output=None):
                if output is None:
                    return True  # Untyped dispatch may hide the out result.
                output.value = tuple(self.names)
                return True
            def GetDocumentSaveToNames(self, names, states):
                names.value, states.value = tuple(self.targets), tuple(self.app.states)
                return True
            def SetDocumentSaveToNames(self, names):
                assert names.kind == 8192 | 8
                return super().SetDocumentSaveToNames(names)
        self.app.pack_class = ByRefPack
        snapshot, entries = self.plan(prefix='new-')
        naming.execute(self.app, snapshot, entries, self.destination)
        self.assertEqual(self.app.saves, 1)

    def test_worker_com_lifecycle_and_cancel_before_connect(self):
        com = install_com(self)
        events, stop = queue.Queue(), threading.Event()
        with patch('naming.exporter.connect_to_solidworks', return_value=self.app):
            naming.worker(events, stop)
        self.assertEqual(list(events.queue)[-1][1]['state'], 'scanned')
        com.CoInitialize.assert_called_once()
        com.CoUninitialize.assert_called_once()
        stop.set()
        with patch('naming.exporter.connect_to_solidworks') as connect:
            naming.worker(events, stop)
            connect.assert_not_called()
        self.assertEqual(list(events.queue)[-1][1]['state'], 'cancelled')
