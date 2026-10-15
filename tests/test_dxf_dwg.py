import os
import unittest
from pathlib import Path
from queue import Queue
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from support.solidworks import (
    DWG,
    DXF,
    FakeApp,
    FakeAssembly,
    FakeComponent,
    FakeFeature,
    FakeMultiPartApp,
    FakePart,
    install_com,
)

from dxf_dwg import exporter as ex


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.part = self.source / 'part.SLDPRT'
        self.part.touch()
        self.output = self.root / 'out'
        self.targets = [self.output / 'part.dxf', self.output / 'part.dwg']
        self.model = FakePart(self.part)
        self.app = FakeApp(self.model)
        self.assembly = FakeAssembly(self.root/'main.SLDASM', [FakeComponent(self.part)])
        self.com, _ = install_com(self, ex, 'dxf')

    def run_one(self, **kwargs):
        return ex.export_one_part(self.app, str(self.part), self.targets, **kwargs)

    def activate_assembly(self):
        self.app.ActiveDoc = self.app.previous = self.assembly

    def run_batch(self, **kwargs):
        self.activate_assembly()
        events = Queue()
        with patch.object(ex, 'connect_to_solidworks', return_value=self.app):
            ex.export_parts(self.source, self.output, True, False, events, **kwargs)
        return list(events.queue)

    def test_scanning_filters_and_nested_paths(self):
        (self.source / '~$lock.sldprt').touch()
        (self.source / 'drawing.slddrw').touch()
        nested = self.source / 'sub'
        nested.mkdir()
        second = nested / 'part.sldprt'
        second.touch()
        self.assertEqual(ex.find_parts(self.source, False), [str(self.part)])
        self.assertEqual(len(ex.find_parts(self.source, True)), 2)
        self.assertEqual(ex.destinations(second, self.source, self.output, ('dxf', 'dwg')),
                         [self.output/'sub/part.dxf', self.output/'sub/part.dwg'])
        stopped = Event()
        stopped.set()
        self.assertEqual(ex.find_parts(self.source, True, stopped), [])

    def test_missing_source_and_invalid_formats(self):
        with self.assertRaises(ValueError):
            ex.find_parts(self.root/'missing', True)
        for formats in ((), ('pdf',), ('dxf', 'pdf')):
            with self.assertRaises(ValueError):
                ex.normalize_formats(formats)
        self.assertEqual(ex.normalize_formats(('DXF', '.dwg', 'dxf')), ('dxf', 'dwg'))

    def test_both_formats_and_api_contract(self):
        status, detail = self.run_one(bend_lines=True)
        self.assertEqual(status, 'success')
        self.assertIn('Konfigürasyon: Default', detail)
        self.assertEqual(self.targets[0].read_bytes(), DXF)
        self.assertEqual(self.targets[1].read_bytes(), DWG)
        self.assertEqual(len(self.model.calls), 2)
        for args in self.model.calls:
            self.assertEqual(args[1:4], (str(self.part), 1, True))
            self.assertEqual(args[5:8], (False, False, 5))
            self.assertEqual(args[4].kind, 0)
            self.assertTrue(Path(args[0]).name.startswith('.gokworks-'))
        self.assertFalse(self.app.closed)
        self.assertFalse(list(self.output.glob('.*')))

    def test_com_object_property_is_not_invoked(self):
        self.assertIs(ex._value(self.app, 'ActiveDoc'), self.model)

    def test_default_excludes_bend_lines(self):
        self.assertEqual(self.run_one()[0], 'success')
        self.assertEqual(self.model.calls[0][7], 1)

    def test_modeldoc_wrapper_casts_to_part_interface(self):
        wrapper = SimpleNamespace(GetType=self.model.GetType, GetTitle=self.model.GetTitle,
                                  GetPathName=self.model.GetPathName,
                                  ConfigurationManager=self.model.ConfigurationManager, Visible=True)
        self.app = FakeApp(wrapper)
        with patch.object(ex.win32com.client, 'CastTo', create=True, return_value=self.model) as cast:
            self.assertEqual(self.run_one()[0], 'success')
            cast.assert_called_once_with(wrapper, 'IPartDoc')
        self.assertEqual(len(self.model.calls), 2)

    def test_unavailable_part_interface_reported(self):
        wrapper = SimpleNamespace(GetType=lambda: 1, GetTitle=self.model.GetTitle,
                                  GetPathName=self.model.GetPathName)
        self.app = FakeApp(wrapper)
        with patch.object(ex.win32com.client, 'CastTo', create=True, side_effect=RuntimeError('No type library')):
            status, detail = self.run_one()
        self.assertEqual(status, 'error')
        self.assertIn('IPartDoc', detail)

    def test_preexisting_outputs_skip_without_opening_part(self):
        self.output.mkdir()
        for target in self.targets:
            target.write_bytes(b'original')
        self.app.existing = False
        self.assertEqual(self.run_one()[0], 'skipped')
        self.assertEqual(self.app.open_count, 0)
        self.assertEqual(self.targets[0].read_bytes(), b'original')

    def test_destination_directory_is_error_before_opening_or_exporting(self):
        self.targets[0].mkdir(parents=True)
        self.app.existing = False
        self.assertEqual(self.run_one()[0], 'error')
        self.assertEqual(self.app.open_count, 0)
        self.assertFalse(self.model.calls)

    def test_named_destination_directory_is_error(self):
        (self.output/'part - 2 mm - 1 adet.dxf').mkdir(parents=True)
        messages = self.run_batch()
        self.assertEqual(messages[-1][1]['failed'], 1)
        self.assertEqual(messages[-1][1]['skipped'], 0)
        self.assertFalse(self.model.calls)

    def test_long_valid_destination_does_not_make_temporary_name_too_long(self):
        target = self.output/('P' * 235 + '.dxf')
        status, detail = ex.export_one_part(self.app, self.part, [target])
        self.assertEqual(status, 'success', detail)
        self.assertEqual(target.read_bytes(), DXF)
        self.assertLess(len(Path(self.model.calls[0][0]).name), 60)

    def test_only_missing_format_exported(self):
        self.output.mkdir()
        self.targets[0].write_bytes(b'original')
        self.assertEqual(self.run_one()[0], 'success')
        self.assertEqual(self.targets[0].read_bytes(), b'original')
        self.assertEqual(len(self.model.calls), 1)
        self.assertTrue(self.targets[1].exists())

    def test_failed_overwrite_preserves_original_and_cleans_temp(self):
        self.output.mkdir()
        self.targets[0].write_bytes(b'original')
        self.model.invalid.add('.dxf')
        status, detail = self.run_one(overwrite=True)
        self.assertEqual(status, 'partial')
        self.assertIn('DXF:', detail)
        self.assertEqual(self.targets[0].read_bytes(), b'original')
        self.assertEqual(self.targets[1].read_bytes(), DWG)
        self.assertFalse(list(self.output.glob('.*')))

    def test_partial_success_reports_the_saved_format_separately(self):
        self.model.fail.add('.dwg')
        outputs = []
        status, detail = ex.export_one_part(self.app, self.part, self.targets, output_results=outputs)
        self.assertEqual(status, 'partial')
        self.assertIn('DXF: açınım aktarıldı', detail)
        self.assertIn('DWG:', detail)
        self.assertTrue(self.targets[0].exists())
        self.assertFalse(self.targets[1].exists())
        self.assertEqual([(item['format'], item['status']) for item in outputs],
                         [('DXF', 'success'), ('DWG', 'error')])
        self.assertEqual(outputs[0]['path'], str(self.targets[0]))

    @unittest.skipIf(os.name == 'nt', 'Unix hard-link publication path')
    def test_published_output_remains_success_when_temporary_cleanup_fails(self):
        native_unlink = Path.unlink
        def unlink(path, *args, **kwargs):
            if path.name.startswith('.gokworks-'):
                raise PermissionError('temporary cleanup denied')
            return native_unlink(path, *args, **kwargs)
        with patch.object(Path, 'unlink', unlink):
            status, detail = ex.export_one_part(self.app, self.part, [self.targets[0]])
        self.assertEqual(status, 'success', detail)
        self.assertEqual(self.targets[0].read_bytes(), DXF)
        self.assertIn('temporary cleanup denied', detail)

    def test_batch_partial_result_lists_only_available_output_paths(self):
        self.model.fail.add('.dwg')
        messages = self.run_batch(formats=('dxf', 'dwg'))
        result = next(value for kind, value in messages if kind == 'result')
        summary = messages[-1][1]
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(summary['partial'], 1)
        self.assertEqual(summary['failed'], 0)
        self.assertTrue(Path(result['output']).is_file())
        self.assertTrue(result['output'].endswith('.dxf'))
        self.assertEqual([item['status'] for item in result['outputs']], ['success', 'error'])

    def test_successful_overwrite(self):
        self.output.mkdir()
        self.targets[0].write_bytes(b'original')
        self.assertEqual(self.run_one(overwrite=True)[0], 'success')
        self.assertEqual(self.targets[0].read_bytes(), DXF)

    def test_racing_target_is_not_overwritten(self):
        def create_target(path):
            target = path.with_name('part' + path.suffix)
            target.write_bytes(b'concurrent')
        self.model.on_export = create_target
        self.assertEqual(self.run_one()[0], 'skipped')
        self.assertEqual(self.targets[0].read_bytes(), b'concurrent')
        self.assertFalse(list(self.output.glob('.*')))

    def test_output_parent_file_is_an_error_not_a_skip(self):
        self.output.write_bytes(b'not a directory')
        status, detail = self.run_one()
        self.assertEqual(status, 'error')
        self.assertFalse(self.model.calls)
        self.assertIn('DXF:', detail)

    def test_windows_publish_uses_rename_without_overwrite(self):
        temporary, target = self.root/'temp.dxf', self.root/'target.dxf'
        temporary.write_bytes(DXF)
        native_os = Mock(wraps=ex.os)
        native_os.name = 'nt'
        with patch.object(ex, 'os', native_os):
            ex._publish(temporary, target, False)
        native_os.rename.assert_called_once_with(temporary, target)
        native_os.link.assert_not_called()
        self.assertEqual(target.read_bytes(), DXF)

    def test_unavailable_assembly_interface_and_root_are_reported(self):
        wrapper = SimpleNamespace(GetType=lambda: 2)
        self.app.ActiveDoc = wrapper
        with patch.object(ex.win32com.client, 'CastTo', create=True, side_effect=RuntimeError('no typelib')):
            with self.assertRaisesRegex(RuntimeError, 'montaj API'):
                ex.assembly_quantities(self.app)
        self.activate_assembly()
        self.assembly.root = None
        with self.assertRaisesRegex(RuntimeError, 'bileşen ağacı'):
            ex.assembly_quantities(self.app)

    def test_non_sheet_metal_and_multi_body_rejected(self):
        for model in (FakePart(self.part, sheet=False), FakePart(self.part, bodies=2), FakePart(self.part, bodies=0)):
            with self.subTest(model=model):
                status, _ = ex.export_one_part(FakeApp(model), str(self.part), self.targets)
                self.assertEqual(status, 'error')
                self.assertFalse(model.calls)

    def test_already_open_warning_keeps_borrowed_part_and_restores_assembly(self):
        for open_error in (0, 2):
            with self.subTest(open_error=open_error):
                self.app = FakeApp(self.model, existing=False, previous=self.assembly)
                self.app.open_error = open_error
                self.model.Visible = False
                open_doc = self.app.OpenDoc6
                def already_open(path, kind, options, configuration, errors, warnings):
                    model = open_doc(path, kind, options, configuration, errors, warnings)
                    warnings.value = 128 | 4
                    return model
                self.app.OpenDoc6 = already_open
                status, detail = self.run_one(overwrite=True)
                self.assertEqual(status, 'error' if open_error else 'success', detail)
                self.assertFalse(self.app.closed)
                self.assertFalse(self.model.Visible)
                self.assertIs(self.app.ActiveDoc, self.assembly)

    def test_opened_document_closed_and_previous_restored(self):
        previous = FakePart(self.source/'other.sldprt')
        self.app = FakeApp(self.model, existing=False, previous=previous)
        self.assertEqual(self.run_one()[0], 'success')
        self.assertEqual(self.app.closed, ['part.SLDPRT'])
        self.assertEqual(self.app.activated, [previous.GetPathName()])

    def test_existing_inactive_part_activated_then_restored_without_closing(self):
        previous = FakePart(self.source/'other.sldprt')
        self.app = FakeApp(self.model, previous=previous)
        self.assertEqual(self.run_one()[0], 'success')
        self.assertEqual(self.app.activated, [self.model.GetPathName(), previous.GetPathName()])
        self.assertFalse(self.app.closed)

    def test_activation_failure_does_not_export(self):
        self.app = FakeApp(self.model, previous=FakePart(self.source/'other.sldprt'))
        self.app.activate_error = 5
        self.assertEqual(self.run_one()[0], 'error')
        self.assertFalse(self.model.calls)
        self.assertEqual(self.app.activated[-1], self.app.previous.GetPathName())

    def test_activation_returning_wrong_document_without_error_is_rejected(self):
        other = FakePart(self.source/'other.sldprt')
        self.app = FakeApp(self.model, previous=other)
        self.app.ActivateDoc3 = Mock(return_value=other)
        status, detail = self.run_one()
        self.assertEqual(status, 'error', detail)
        self.assertFalse(self.model.calls)

    def test_open_document_with_wrong_path_is_rejected(self):
        wrong_model = FakePart(self.source/'different.sldprt')
        self.app = FakeApp(wrong_model)
        status, detail = self.run_one()
        self.assertEqual(status, 'error', detail)
        self.assertFalse(wrong_model.calls)

    def test_same_named_documents_restored_by_full_path(self):
        previous = FakePart(self.root/'other'/self.part.name)
        self.app = FakeApp(self.model, previous=previous)
        self.assertEqual(self.run_one()[0], 'success')
        self.assertEqual(self.app.activated, [self.model.GetPathName(), previous.GetPathName()])
        self.assertIs(self.app.ActiveDoc, previous)

    def test_unsaved_previous_document_restored_by_title(self):
        previous = FakePart(self.root/'Unsaved1')
        previous.GetPathName = lambda: ''
        self.app = FakeApp(self.model, previous=previous)
        self.assertEqual(self.run_one()[0], 'success')
        self.assertEqual(self.app.activated[-1], 'Unsaved1')
        self.assertIs(self.app.ActiveDoc, previous)

    def test_hidden_existing_part_visible_during_export_then_hidden(self):
        self.model.Visible = False
        seen = []
        self.model.on_export = lambda path: seen.append(self.model.Visible)
        self.assertEqual(self.run_one()[0], 'success')
        self.assertEqual(seen, [True, True])
        self.assertFalse(self.model.Visible)
        self.assertFalse(self.app.closed)

    def test_hidden_part_visibility_restored_on_export_failure(self):
        self.model.Visible = False
        self.model.fail = {'.dxf', '.dwg'}
        self.assertEqual(self.run_one()[0], 'error')
        self.assertFalse(self.model.Visible)

    def test_cached_com_application_converted_for_byref_outputs(self):
        self.app._oleobj_ = object()
        late_bound = Mock(return_value=self.app)
        with patch.object(ex.win32com.client, 'dynamic', create=True,
                          new=SimpleNamespace(DumbDispatch=late_bound)):
            self.assertEqual(self.run_one()[0], 'success')
        late_bound.assert_called_once_with(self.app)

    def test_open_failure_closes_owned_document(self):
        self.app = FakeApp(self.model, existing=False)
        self.app.open_error = 2
        self.assertEqual(self.run_one()[0], 'error')
        self.assertEqual(self.app.closed, ['part.SLDPRT'])
        self.assertFalse(self.model.calls)

    def test_invalid_destination(self):
        self.assertEqual(ex.export_one_part(self.app, self.part, [self.output/'part.pdf'])[0], 'error')

    def test_empty_or_malformed_dxf_and_bad_dwg_rejected(self):
        self.output.mkdir()
        for content in (b'', b'AutoCAD Binary DXF\r\n\x1a\x00', b'0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n', DXF[:-6], b'invalid content' * 4):
            self.targets[0].write_bytes(content)
            with self.assertRaises(RuntimeError):
                ex._validate_output(self.targets[0])
        self.targets[1].write_bytes(b'garbage' * 10)
        with self.assertRaises(RuntimeError):
            ex._validate_output(self.targets[1])

    def test_missing_output_rejected(self):
        with self.assertRaises(RuntimeError):
            ex._validate_output(self.targets[0])

    def test_missing_dxf_section_end_and_invalid_group_codes_are_rejected(self):
        self.output.mkdir()
        for content in (DXF.replace(b'0\nENDSEC\n', b''),
                        DXF.replace(b'0\nSECTION\n', b''),
                        DXF.replace(b'10\n0\n', b'invalid\n0\n')):
            self.targets[0].write_bytes(content)
            with self.subTest(content=content), self.assertRaises(RuntimeError):
                ex._validate_output(self.targets[0])

    def test_invalid_numeric_dxf_coordinates_are_rejected(self):
        self.output.mkdir()
        self.targets[0].write_bytes(DXF.replace(b'10\n0\n', b'10\ninvalid\n'))
        with self.assertRaises(RuntimeError):
            ex._validate_output(self.targets[0])

    def test_real_r12_and_r2018_ascii_and_binary_fixtures_are_accepted(self):
        folder = Path(__file__).parent/'fixtures/dxf'
        paths = sorted(folder.glob('*.dxf'))
        self.assertEqual(len(paths), 4)
        for path in paths:
            with self.subTest(path=path.name):
                ex._validate_output(path)

    def test_truncated_binary_fixture_is_rejected(self):
        fixture = Path(__file__).parent/'fixtures/dxf/plate-r2018-bin.dxf'
        self.output.mkdir()
        self.targets[0].write_bytes(fixture.read_bytes()[:-6])
        with self.assertRaises(RuntimeError):
            ex._validate_output(self.targets[0])

    def test_missing_dxf_reader_errors_before_connecting(self):
        events = Queue()
        with patch.object(ex, 'ezdxf', None), patch.object(ex, 'connect_to_solidworks') as connect:
            ex.export_parts(self.source, self.output, True, False, events)
        connect.assert_not_called()
        summary = list(events.queue)[-1][1]
        self.assertEqual(summary['state'], 'error')
        self.assertIn('ezdxf', summary['error'])

    def test_dwg_only_export_does_not_need_dxf_reader(self):
        with patch.object(ex, 'ezdxf', None):
            messages = self.run_batch(formats=('dwg',))
        self.assertEqual(messages[-1][1]['succeeded'], 1)
        self.assertTrue((self.output/'part - 2 mm - 1 adet.dwg').is_file())

    def test_malformed_dxf_during_overwrite_preserves_previous_output(self):
        self.output.mkdir()
        self.targets[0].write_bytes(b'original')
        def incomplete_export(path):
            Path(path).write_bytes(DXF.replace(b'0\nENDSEC\n', b''))
            return True
        self.model.ExportToDWG2 = Mock(side_effect=lambda path, *args: incomplete_export(path))
        status, detail = ex.export_one_part(self.app, self.part, [self.targets[0]], overwrite=True)
        self.assertEqual(status, 'error', detail)
        self.assertEqual(self.targets[0].read_bytes(), b'original')
        self.assertFalse(list(self.output.glob('.*')))

    def test_batch_summary_and_com_cleanup(self):
        self.activate_assembly()
        events = Queue()
        with patch.object(ex, 'connect_to_solidworks', return_value=self.app):
            ex.export_parts(self.source, self.output, True, False, events, formats=('dxf', 'dwg'))
        messages = list(events.queue)
        summary = messages[-1][1]
        self.assertEqual(messages[-1][0], 'done')
        self.assertEqual((summary['processed'], summary['succeeded'], summary['failed']), (1, 1, 0))
        result = next(value for kind, value in messages if kind == 'result')
        self.assertIn('part - 2 mm - 1 adet.dwg', result['output'])
        self.assertEqual((result['quantity'], result['thickness_mm']), (1, 2))
        self.assertIs(self.app.ActiveDoc, self.assembly)
        self.com.CoInitialize.assert_called_once()
        self.com.CoUninitialize.assert_called_once()

    def test_batch_continues_after_failed_part(self):
        (self.source/'second.sldprt').touch()
        self.assembly.root.children.append(FakeComponent(self.source/'second.sldprt'))
        self.activate_assembly()
        events = Queue()
        with patch.object(ex, 'connect_to_solidworks', return_value=self.app), patch.object(ex, 'export_one_part', side_effect=[('error', 'bad'), ('success', 'ok')]):
            ex.export_parts(self.source, self.output, False, False, events)
        summary = list(events.queue)[-1][1]
        self.assertEqual((summary['state'], summary['processed'], summary['failed'], summary['succeeded']), ('completed', 2, 1, 1))

    def test_cancellation_between_parts(self):
        (self.source/'second.sldprt').touch()
        self.assembly.root.children.append(FakeComponent(self.source/'second.sldprt'))
        self.activate_assembly()
        events, stop = Queue(), Event()
        def finish_first(*args, **kwargs):
            stop.set()
            return 'success', 'ok'
        with patch.object(ex, 'connect_to_solidworks', return_value=self.app), patch.object(ex, 'export_one_part', side_effect=finish_first):
            ex.export_parts(self.source, self.output, True, False, events, stop)
        summary = list(events.queue)[-1][1]
        self.assertEqual((summary['state'], summary['processed'], summary['total']), ('cancelled', 1, 2))
        self.com.CoUninitialize.assert_called_once()

    def test_empty_and_precancelled_batch_do_not_connect(self):
        self.part.unlink()
        events = Queue()
        ex.export_parts(self.source, self.output, True, False, events)
        self.assertEqual(list(events.queue)[-1][1]['state'], 'empty')
        stop = Event()
        stop.set()
        events = Queue()
        ex.export_parts(self.source, self.output, True, False, events, stop)
        self.assertEqual(list(events.queue)[-1][1]['state'], 'cancelled')
        self.com.CoInitialize.assert_not_called()

    def test_connection_failure_still_uninitializes_com(self):
        events = Queue()
        with patch.object(ex, 'connect_to_solidworks', side_effect=RuntimeError('SolidWorks açık değil')):
            ex.export_parts(self.source, self.output, True, False, events)
        self.assertEqual(list(events.queue)[-1][1]['state'], 'error')
        self.com.CoUninitialize.assert_called_once()

    def test_com_cleanup_failure_is_reported_and_done_is_emitted(self):
        self.com.CoUninitialize.side_effect = RuntimeError('COM cleanup failed')
        messages = self.run_batch()
        self.assertEqual(messages[-1][0], 'done')
        self.assertEqual(messages[-1][1]['state'], 'completed')
        self.assertEqual(messages[-1][1]['succeeded'], 1)
        self.assertIn('COM cleanup failed', messages[-1][1]['warnings'][0])

    def test_active_speedpak_configuration_rejects_incomplete_counts(self):
        self.activate_assembly()
        self.assembly.ConfigurationManager.ActiveConfiguration.IsSpeedPak = lambda: True
        with self.assertRaisesRegex(RuntimeError, 'SpeedPak'):
            ex.assembly_quantities(self.app)

    def test_platform_requirement_is_explicit(self):
        events = Queue()
        with patch.object(ex, 'pythoncom', None):
            ex.export_parts(self.source, self.output, True, False, events)
        summary = list(events.queue)[-1][1]
        self.assertEqual(summary['state'], 'error')
        self.assertIn('Windows', summary['error'])

    def test_nested_assembly_occurrences_and_configuration_counts(self):
        children = [FakeComponent(self.part), FakeComponent(self.part)]
        self.assembly.root.children = [
            FakeComponent(self.part),
            FakeComponent(self.root/'sub.sldasm', children=children),
            FakeComponent(self.root/'sub.sldasm', children=children),
            FakeComponent(self.part, configuration='Thin'),
            FakeComponent(self.root/'suppressed.sldasm', children=children, state=0),
            FakeComponent(self.part, state=0)]
        self.activate_assembly()
        quantities, name, config = ex.assembly_quantities(self.app)
        self.assertEqual(quantities[ex._part_key(self.part, 'Default')], 5)
        self.assertEqual(quantities[ex._part_key(self.part, 'Thin')], 1)
        self.assertEqual((name, config), (self.assembly.path, 'Assembly-Default'))

    def test_count_is_physical_not_visibility_or_bom(self):
        component = self.assembly.root.children[0]
        component.Visible = False
        component.ExcludeFromBOM = True
        self.activate_assembly()
        self.assertEqual(ex.assembly_quantities(self.app)[0][ex._part_key(self.part, 'Default')], 1)

    def test_component_paths_normalize_windows_separators_and_case(self):
        self.assertEqual(ex._part_key(r'C:\Parts\Sheet.SLDPRT', 'DEFAULT'),
                         ex._part_key('c:/parts/sheet.sldprt', 'Default'))

    def test_distinct_unicode_component_paths_and_configurations_do_not_merge(self):
        first, second = r'C:\Parts\Straße.sldprt', r'C:\Parts\Strasse.sldprt'
        self.assembly.root.children = [FakeComponent(first), FakeComponent(second),
                                       FakeComponent(first, configuration='Strasse')]
        self.activate_assembly()
        quantities = ex.assembly_quantities(self.app)[0]
        self.assertEqual(len(quantities), 3)
        self.assertEqual(quantities[ex._part_key(first, 'Default')], 1)
        self.assertEqual(quantities[ex._part_key(second, 'Default')], 1)
        self.assertNotEqual(ex._part_key(first, 'Straße'), ex._part_key(first, 'Strasse'))

    def test_count_requires_active_assembly(self):
        for active in (None, self.model):
            self.app.ActiveDoc = active
            with self.subTest(active=active), self.assertRaisesRegex(RuntimeError, 'ana montaj'):
                ex.assembly_quantities(self.app)

    def test_assembly_interface_cast(self):
        wrapper = SimpleNamespace(GetType=self.assembly.GetType,
                                  GetPathName=self.assembly.GetPathName,
                                  ConfigurationManager=self.assembly.ConfigurationManager)
        self.app.ActiveDoc = wrapper
        with patch.object(ex.win32com.client, 'CastTo', create=True, return_value=self.assembly) as cast:
            self.assertEqual(sum(ex.assembly_quantities(self.app)[0].values()), 1)
        cast.assert_called_once_with(wrapper, 'IAssemblyDoc')

    def test_failed_or_unresolved_components_reject_incomplete_count(self):
        self.activate_assembly()
        for status in (1, 3):
            self.assembly.resolve_status = status
            with self.subTest(resolve=status), self.assertRaisesRegex(RuntimeError, 'çözümlenemedi'):
                ex.assembly_quantities(self.app)
        self.assembly.resolve_status = 2
        for state in (1, 4, 5):
            self.assembly.root.children[0].state = state
            with self.subTest(state=state), self.assertRaisesRegex(RuntimeError, 'çözümlenmemiş'):
                ex.assembly_quantities(self.app)

    def test_cycle_and_missing_component_data_are_reported(self):
        self.activate_assembly()
        child = FakeComponent(self.root/'sub.sldasm')
        child.children = [child]
        self.assembly.root.children = [child]
        with self.assertRaisesRegex(RuntimeError, 'döngü'):
            ex.assembly_quantities(self.app)
        for path, config in (('', 'Default'), (self.part, ''), (self.root/'other.step', 'Default')):
            self.assembly.root.children = [FakeComponent(path, config)]
            with self.subTest(path=path, config=config), self.assertRaises(RuntimeError):
                ex.assembly_quantities(self.app)

    def test_unloaded_or_speedpak_subassembly_rejects_incomplete_count(self):
        self.activate_assembly()
        child = FakeComponent(self.root/'sub.sldasm')
        self.assembly.root.children = [child]
        child.model = None
        with self.assertRaisesRegex(RuntimeError, 'yüklenmemiş'):
            ex.assembly_quantities(self.app)
        child.model, child.IsSpeedPak = object(), True
        with self.assertRaisesRegex(RuntimeError, 'SpeedPak'):
            ex.assembly_quantities(self.app)

    def test_cancellation_during_count_ends_batch_without_export(self):
        stop = Event()
        def resolve(warn):
            stop.set()
            return 0
        self.assembly.ResolveAllLightWeightComponents = resolve
        messages = self.run_batch(stop_event=stop)
        self.assertEqual(messages[-1][1]['state'], 'cancelled')
        self.assertFalse(self.model.calls)
        self.com.CoUninitialize.assert_called_once()

    def test_thickness_nested_active_feature_and_meter_conversion(self):
        self.model.feature = FakeFeature('Folder', 'FeatureFolder', child=FakeFeature(
            'Suppressed', thickness=.009, suppressed=True, next_feature=FakeFeature('Active', thickness=.00125)))
        self.assertEqual(ex.sheet_thickness_mm(self.model), 1.25)

    def test_feature_seen_as_child_does_not_truncate_top_level_chain(self):
        repeated = FakeFeature('Suppressed', suppressed=True)
        repeated.GetNextSubFeature = lambda: None
        repeated.next = FakeFeature('Active', thickness=.00125)
        self.model.feature = FakeFeature('Folder', 'FeatureFolder',
                                         child=repeated, next_feature=repeated)
        self.assertEqual(ex.sheet_thickness_mm(self.model), 1.25)

    def test_multi_part_batch_keeps_each_models_thickness_and_quantity(self):
        second_path = self.source/'second.sldprt'
        second_path.touch()
        second = FakePart(second_path)
        second.feature.thickness = .00125
        self.assembly.root.children = ([FakeComponent(self.part) for _ in range(2)]
                                       + [FakeComponent(second_path) for _ in range(5)])
        self.app = FakeMultiPartApp([self.model, second], self.assembly)
        messages = self.run_batch(formats=('dxf', 'dwg'))
        self.assertEqual(messages[-1][1]['succeeded'], 2)
        for model, stem, quantity, thickness in (
                (self.model, 'part - 2 mm - 2 adet', 2, 2),
                (second, 'second - 1.25 mm - 5 adet', 5, 1.25)):
            self.assertEqual(len(model.calls), 2)
            self.assertTrue(all(call[1] == model.path for call in model.calls))
            result = next(value for kind, value in messages
                          if kind == 'result' and value['source'] == model.path)
            self.assertEqual((result['quantity'], result['thickness_mm']), (quantity, thickness))
            for kind in ('dxf', 'dwg'):
                self.assertTrue((self.output/f'{stem}.{kind}').is_file())
        self.assertIs(self.app.ActiveDoc, self.assembly)

    def test_grouped_batch_keeps_mixed_thickness_and_same_named_subfolders(self):
        models = [(self.model, Path('2 mm'), 2, 2)]
        for folder, quantity in (('left', 3), ('right', 3)):
            path = self.source/folder/'part.SLDPRT'
            path.parent.mkdir()
            path.touch()
            model = FakePart(path)
            model.feature.thickness = .0015
            models.append((model, Path('1,5 mm')/folder, quantity, 1.5))
        self.assembly.root.children = [FakeComponent(model.path)
                                       for model, _, quantity, _ in models
                                       for _ in range(quantity)]
        self.app = FakeMultiPartApp([model for model, _, _, _ in models], self.assembly)
        messages = self.run_batch(formats=('dxf', 'dwg'), group_by_thickness=True)
        self.assertEqual(messages[-1][1]['succeeded'], 3)
        self.assertTrue(any(kind == 'log' and 'kalınlığına göre klasörlenir' in value
                            for kind, value in messages))
        for model, folder, quantity, thickness in models:
            result = next(value for kind, value in messages
                          if kind == 'result' and value['source'] == model.path)
            self.assertEqual((result['quantity'], result['thickness_mm']), (quantity, thickness))
            expected = [self.output/folder/f'part - {thickness:g} mm - {quantity} adet.{kind}'
                        for kind in ('dxf', 'dwg')]
            self.assertEqual(result['output'], ' | '.join(map(str, expected)))
            self.assertEqual([item['path'] for item in result['outputs']], list(map(str, expected)))
            self.assertEqual([target.read_bytes() for target in expected], [DXF, DWG])
            self.assertEqual([Path(call[0]).parent for call in model.calls],
                             [self.output/folder] * 2)
        self.assertFalse(list(self.output.rglob('.gokworks-*')))
        self.assertIs(self.app.ActiveDoc, self.assembly)

    def test_missing_invalid_or_ambiguous_thickness_is_rejected(self):
        for feature in (None, FakeFeature(suppressed=True), FakeFeature(thickness=0),
                        FakeFeature(thickness=float('nan')), FakeFeature(thickness=-.001),
                        FakeFeature(next_feature=FakeFeature('Other', thickness=.003))):
            self.model.feature = feature
            with self.subTest(feature=feature), self.assertRaises(RuntimeError):
                ex.sheet_thickness_mm(self.model)

    def test_named_destinations_keep_decimals_and_subdirectories(self):
        part = self.source/'sub'/'BRAKET.v2.SLDPRT'
        paths = ex.named_destinations(part, self.source, self.output, ('dxf', 'dwg'), 1.25, 12)
        self.assertEqual(paths, [self.output/'sub'/f'BRAKET.v2 - 1.25 mm - 12 adet.{kind}'
                                 for kind in ('dxf', 'dwg')])
        for thickness, quantity in ((0, 1), (float('inf'), 1), (2, 0), (2, 1.5), (2, True)):
            with self.subTest(thickness=thickness, quantity=quantity), self.assertRaises(ValueError):
                ex.named_destinations(part, self.source, self.output, ('dxf',), thickness, quantity)

    def test_grouped_destinations_use_canonical_thickness_and_keep_default_paths(self):
        part = self.source/'sub'/'BRAKET.v2.SLDPRT'
        for thickness, label in ((2, '2'), (1.5, '1.5'), (1.23456789, '1.234568'),
                                 (.000001, '0.000001')):
            with self.subTest(thickness=thickness):
                filename = f'BRAKET.v2 - {label} mm - 12 adet.dxf'
                self.assertEqual(ex.named_destinations(
                    part, self.source, self.output, ('dxf',), thickness, 12),
                    [self.output/'sub'/filename])
                self.assertEqual(ex.named_destinations(
                    part, self.source, self.output, ('dxf',), thickness, 12, True),
                    [self.output/f"{label.replace('.', ',')} mm"/'sub'/filename])

    def test_grouped_batch_rejects_missing_invalid_and_multiple_thicknesses(self):
        for feature in (None, FakeFeature(thickness=0), FakeFeature(thickness=float('nan')),
                        FakeFeature(thickness=.0000000001),
                        FakeFeature(next_feature=FakeFeature('Other', thickness=.003))):
            self.model.feature = feature
            with self.subTest(feature=feature):
                messages = self.run_batch(group_by_thickness=True)
                self.assertEqual(messages[-1][1]['failed'], 1)
                result = next(value for kind, value in messages if kind == 'result')
                self.assertEqual(result['output'], '')
                self.assertEqual(result['outputs'], [])
                self.assertFalse(self.model.calls)
                self.assertFalse(list(self.output.iterdir()))

    def test_named_batch_uses_nested_total_for_both_formats(self):
        self.assembly.root.children *= 3
        self.model.feature.thickness = .00125
        messages = self.run_batch(formats=('dxf', 'dwg'))
        self.assertEqual(messages[-1][1]['succeeded'], 1)
        for kind in ('dxf', 'dwg'):
            self.assertTrue((self.output/f'part - 1.25 mm - 3 adet.{kind}').is_file())

    def test_other_assembly_configurations_are_reported_in_results_and_summary(self):
        self.assembly.root.children = ([FakeComponent(self.part)] * 3
                                      + [FakeComponent(self.part, 'İnce')] * 2)
        messages = self.run_batch()
        result = next(value for kind, value in messages if kind == 'result')
        self.assertEqual(result['status'], 'success', result['detail'])
        self.assertEqual(result['quantity'], 3)
        self.assertEqual(result['configuration'], 'Default')
        self.assertEqual(result['unexported_configurations'], [('İnce', 2)])
        self.assertIn('İnce (2 adet)', result['detail'])
        self.assertEqual(messages[-1][1]['unexported_configurations'], 1)
        self.assertTrue(messages[-1][1]['warnings'])
        self.assertTrue((self.output/'part - 2 mm - 3 adet.dxf').is_file())
        self.assertEqual(len(self.model.calls), 1)

    def test_parts_outside_active_assembly_skip_without_opening(self):
        self.assembly.root.children = []
        self.app.existing = False
        messages = self.run_batch()
        self.assertEqual(messages[-1][1]['skipped'], 1)
        self.assertEqual(self.app.open_count, 0)
        self.assertFalse(self.model.calls)

    def test_configuration_mismatch_and_missing_thickness_never_guess(self):
        for configuration, feature in (('Other', FakeFeature()), ('Default', None)):
            self.assembly.root.children[0].ReferencedConfiguration = configuration
            self.model.feature = feature
            messages = self.run_batch()
            self.assertEqual(messages[-1][1]['failed'], 1)
            self.assertFalse(self.model.calls)
            self.assertFalse(list(self.output.glob('*.dxf')))

    def test_named_existing_output_skips_and_preserves_assembly(self):
        self.output.mkdir()
        target = self.output/'part - 2 mm - 1 adet.dxf'
        target.write_bytes(b'original')
        messages = self.run_batch()
        self.assertEqual(messages[-1][1]['skipped'], 1)
        self.assertEqual(target.read_bytes(), b'original')
        self.assertFalse(self.model.calls)
        self.assertFalse(self.app.activated)
        self.assertIs(self.app.ActiveDoc, self.assembly)

    def test_named_partial_output_exports_only_missing_format(self):
        self.output.mkdir()
        dxf = self.output/'part - 2 mm - 1 adet.dxf'
        dxf.write_bytes(b'original')
        messages = self.run_batch(formats=('dxf', 'dwg'))
        self.assertEqual(messages[-1][1]['succeeded'], 1)
        self.assertEqual(dxf.read_bytes(), b'original')
        self.assertEqual(len(self.model.calls), 1)
        self.assertTrue((self.output/'part - 2 mm - 1 adet.dwg').exists())

    def test_grouped_batch_skips_existing_output_and_exports_only_missing_format(self):
        folder = self.output/'2 mm'
        folder.mkdir(parents=True)
        dxf = folder/'part - 2 mm - 1 adet.dxf'
        dwg = folder/'part - 2 mm - 1 adet.dwg'
        dxf.write_bytes(b'original')
        ungrouped = self.output/dwg.name
        ungrouped.write_bytes(b'legacy')
        messages = self.run_batch(formats=('dxf', 'dwg'), group_by_thickness=True)
        result = next(value for kind, value in messages if kind == 'result')
        self.assertEqual(messages[-1][1]['succeeded'], 1)
        self.assertEqual([item['status'] for item in result['outputs']], ['skipped', 'success'])
        self.assertEqual(result['output'], f'{dxf} | {dwg}')
        self.assertEqual(dxf.read_bytes(), b'original')
        self.assertEqual(dwg.read_bytes(), DWG)
        self.assertEqual(ungrouped.read_bytes(), b'legacy')
        self.assertEqual(len(self.model.calls), 1)
        self.model.calls.clear()
        messages = self.run_batch(formats=('dxf', 'dwg'), group_by_thickness=True)
        self.assertEqual(messages[-1][1]['skipped'], 1)
        result = next(value for kind, value in messages if kind == 'result')
        self.assertEqual([item['status'] for item in result['outputs']], ['skipped', 'skipped'])
        self.assertEqual(result['output'], f'{dxf} | {dwg}')
        self.assertFalse(self.model.calls)
        self.assertFalse(list(folder.glob('.gokworks-*')))

    def test_grouped_batch_overwrite_preserves_original_on_invalid_export(self):
        folder = self.output/'2 mm'
        folder.mkdir(parents=True)
        dxf = folder/'part - 2 mm - 1 adet.dxf'
        dwg = folder/'part - 2 mm - 1 adet.dwg'
        for invalid in (False, True):
            with self.subTest(invalid=invalid):
                dxf.write_bytes(b'original')
                dwg.write_bytes(b'original')
                self.model.invalid = {'.dxf'} if invalid else set()
                self.model.calls.clear()
                self.activate_assembly()
                events = Queue()
                with patch.object(ex, 'connect_to_solidworks', return_value=self.app):
                    ex.export_parts(self.source, self.output, True, True, events,
                                    formats=('dxf', 'dwg'), group_by_thickness=True)
                messages = list(events.queue)
                result = next(value for kind, value in messages if kind == 'result')
                self.assertEqual(result['status'], 'partial' if invalid else 'success')
                self.assertEqual([item['path'] for item in result['outputs']], [str(dxf), str(dwg)])
                self.assertEqual(dxf.read_bytes(), b'original' if invalid else DXF)
                self.assertEqual(dwg.read_bytes(), DWG)
                self.assertEqual(len(self.model.calls), 2)
                self.assertTrue(all(Path(call[0]).parent == folder for call in self.model.calls))
                self.assertFalse(list(folder.glob('.gokworks-*')))


if __name__ == '__main__':
    unittest.main()
