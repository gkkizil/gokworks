import unittest
from pathlib import Path
from queue import Queue
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from support.solidworks import PDF, FakeDrawing, FakePdfApp, FakePdfData, install_com

from pdf import exporter as ex


class PdfTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'source'
        self.source.mkdir()
        self.drawing = self.source/'drawing.SLDDRW'
        self.drawing.touch()
        self.output = self.root/'out'
        self.target = self.output/'drawing.pdf'
        self.model = FakeDrawing(self.drawing)
        self.app = FakePdfApp([self.model])
        self.com, self.client = install_com(self, ex, 'pdf', dynamic=True)

    def run_one(self, overwrite=False):
        return ex.export_one_drawing(self.app, str(self.drawing), self.target, overwrite)

    def run_batch(self, stop=None):
        events = Queue()
        with patch.object(ex, 'connect_to_solidworks', return_value=self.app):
            ex.export_drawings(self.source, self.output, True, False, events, stop)
        return list(events.queue)

    def test_scan_and_destination_preserve_subfolders(self):
        nested = self.source/'sub'
        nested.mkdir()
        second = nested/'drawing.slddrw'
        second.touch()
        (self.source/'~$locked.slddrw').touch()
        (self.source/'part.sldprt').touch()
        self.assertEqual(ex.find_drawings(self.source, False), [str(self.drawing)])
        self.assertEqual(len(ex.find_drawings(self.source, True)), 2)
        self.assertEqual(ex.pdf_destination(second, self.source, self.output), self.output/'sub/drawing.pdf')
        with self.assertRaises(ValueError):
            ex.find_drawings(self.root/'missing', True)

    def test_all_sheets_and_pdf_api_contract(self):
        self.assertEqual(self.run_one()[0], 'success')
        self.assertEqual(self.app.data.sheets, ('Sheet1', 'Sayfa 2'))
        self.assertFalse(self.app.data.ViewPdfAfterSaving)
        self.assertFalse(self.app.data.ExportAs3D)
        self.assertEqual(self.target.read_bytes(), PDF)
        self.assertFalse(self.app.closed)
        self.assertFalse(list(self.output.glob('.*')))

    def test_com_object_property_does_not_call_default_member(self):
        self.assertIs(ex.read_com_value(self.app, 'ActiveDoc'), self.model)

    def test_cached_application_uses_late_binding_for_byref(self):
        self.app._oleobj_ = object()
        self.assertEqual(self.run_one()[0], 'success')
        self.client.dynamic.DumbDispatch.assert_called_once_with(self.app)

    def test_cached_extension_uses_late_binding_for_saveas_byref(self):
        self.model.Extension._oleobj_ = object()
        self.assertEqual(self.run_one()[0], 'success')
        self.client.dynamic.DumbDispatch.assert_called_once_with(self.model.Extension)

    def test_drawing_interface_cast_for_sheet_names(self):
        wrapper = SimpleNamespace(GetType=self.model.GetType, GetTitle=self.model.GetTitle,
                                  GetPathName=self.model.GetPathName, Extension=self.model.Extension)
        self.app.GetOpenDocumentByName = lambda path: wrapper
        self.app.ActiveDoc = wrapper
        self.model.app = SimpleNamespace(ActiveDoc=self.model)
        with patch.object(self.client, 'CastTo', create=True, return_value=self.model) as cast:
            self.assertEqual(self.run_one()[0], 'success')
        cast.assert_called_once_with(wrapper, 'IDrawingDoc')

    def test_wrong_document_and_missing_drawing_interface_are_reported(self):
        self.model.GetType = lambda: 1
        self.assertEqual(self.run_one()[0], 'error')
        self.assertFalse(self.model.calls)
        wrapper = SimpleNamespace(GetType=lambda: 3, GetTitle=self.model.GetTitle,
                                  GetPathName=self.model.GetPathName)
        self.app.GetOpenDocumentByName = lambda path: wrapper
        with patch.object(self.client, 'CastTo', create=True, side_effect=RuntimeError('no typelib')):
            status, detail = self.run_one()
        self.assertEqual(status, 'error')
        self.assertIn('IDrawingDoc', detail)

    def test_existing_output_skips_without_opening(self):
        self.output.mkdir()
        self.target.write_bytes(b'original')
        self.app.opened.clear()
        self.assertEqual(self.run_one()[0], 'skipped')
        self.assertFalse(self.app.open_calls)
        self.assertEqual(self.target.read_bytes(), b'original')

    def test_failed_overwrite_keeps_original_and_cleans_temp(self):
        self.output.mkdir()
        self.target.write_bytes(b'original')
        self.model.save_ok = False
        self.assertEqual(self.run_one(overwrite=True)[0], 'error')
        self.assertEqual(self.target.read_bytes(), b'original')
        self.assertFalse(list(self.output.glob('.*')))

    def test_successful_overwrite(self):
        self.output.mkdir()
        self.target.write_bytes(b'original')
        self.assertEqual(self.run_one(overwrite=True)[0], 'success')
        self.assertEqual(self.target.read_bytes(), PDF)

    def test_competing_target_is_preserved(self):
        self.model.on_save = lambda path: self.target.write_bytes(b'concurrent')
        self.assertEqual(self.run_one()[0], 'skipped')
        self.assertEqual(self.target.read_bytes(), b'concurrent')
        self.assertFalse(list(self.output.glob('.*')))

    def test_windows_publish_uses_rename_and_preserves_competing_target(self):
        self.model.on_save = lambda path: self.target.write_bytes(b'concurrent')
        native_os = Mock(wraps=ex.os)
        native_os.name = 'nt'
        native_os.rename = Mock(side_effect=FileExistsError('already exists'))
        with patch.object(ex, 'os', native_os):
            self.assertEqual(self.run_one()[0], 'skipped')
        native_os.rename.assert_called_once()
        native_os.link.assert_not_called()
        self.assertEqual(self.target.read_bytes(), b'concurrent')

    def test_cleanup_failures_are_reported_without_losing_success(self):
        self.app.opened.clear()
        self.app.CloseDoc = Mock(side_effect=RuntimeError('close failed'))
        status, detail = self.run_one()
        self.assertEqual(status, 'success')
        self.assertIn('Çizim kapatılamadı', detail)
        self.assertTrue(self.target.exists())

    def test_inactive_open_drawing_is_activated_then_previous_restored(self):
        previous = FakeDrawing(self.root/'previous.slddrw')
        self.app = FakePdfApp([self.model], previous=previous)
        self.assertEqual(self.run_one()[0], 'success')
        self.assertIs(self.app.ActiveDoc, previous)
        self.assertEqual(self.app.activated, [self.model.path, previous.path])
        self.assertFalse(self.app.closed)

    def test_newly_opened_drawing_is_closed_and_previous_restored(self):
        previous = FakeDrawing(self.root/'previous.slddrw')
        self.app = FakePdfApp([self.model], opened=[], previous=previous)
        self.assertEqual(self.run_one()[0], 'success')
        self.assertEqual(self.app.closed, ['drawing.SLDDRW'])
        self.assertIs(self.app.ActiveDoc, previous)

    def test_open_error_closes_owned_document_without_export(self):
        self.app.opened.clear()
        self.app.open_error = 2
        self.assertEqual(self.run_one()[0], 'error')
        self.assertEqual(self.app.closed, ['drawing.SLDDRW'])
        self.assertFalse(self.model.calls)

    def test_activation_failure_prevents_export_and_restores_previous(self):
        previous = FakeDrawing(self.root/'previous.slddrw')
        self.app = FakePdfApp([self.model], previous=previous)
        self.app.activate_error = 5
        self.assertEqual(self.run_one()[0], 'error')
        self.assertFalse(self.model.calls)
        self.assertEqual(self.app.activated[-1], previous.path)

    def test_wrong_open_document_is_rejected_before_export(self):
        other = FakeDrawing(self.root/'other.slddrw')
        other.app = self.app
        self.app.GetOpenDocumentByName = Mock(return_value=other)
        self.app.ActiveDoc = other
        self.assertEqual(self.run_one()[0], 'error')
        self.assertFalse(other.calls)
        self.assertFalse(self.target.exists())

    def test_activation_checks_returned_document_and_actual_active_document(self):
        for wrong_return in (True, False):
            with self.subTest(wrong_return=wrong_return):
                self.target.unlink(missing_ok=True)
                self.model.calls.clear()
                other = FakeDrawing(self.root/'other.slddrw')
                self.app.ActiveDoc = other
                def activate(name, preferences, rebuild, errors):
                    self.app.ActiveDoc = self.model if wrong_return else other
                    return other if wrong_return else self.model
                self.app.ActivateDoc3 = activate
                self.assertEqual(self.run_one()[0], 'error')
                self.assertFalse(self.model.calls)
                self.assertFalse(self.target.exists())

    def test_valid_long_pdf_name_uses_short_temporary_name(self):
        self.target = self.output/('p'*225+'.pdf')
        self.assertEqual(self.run_one()[0], 'success')
        self.assertEqual(self.target.read_bytes(), PDF)

    def test_pdf_target_directory_is_an_error_even_without_overwrite(self):
        self.target.mkdir(parents=True)
        self.assertEqual(self.run_one()[0], 'error')
        self.assertFalse(self.model.calls)

    def test_com_cleanup_failure_is_reported_and_worker_returns(self):
        self.com.CoUninitialize.side_effect = RuntimeError('cleanup failed')
        messages = self.run_batch()
        self.assertEqual(messages[-1][0], 'done')
        self.assertEqual(messages[-1][1]['state'], 'error')
        self.assertIn('cleanup failed', messages[-1][1]['error'])

    def test_single_sheet_string(self):
        self.model.sheets = 'Tek Sayfa'
        self.assertEqual(self.run_one()[0], 'success')
        self.assertEqual(self.app.data.sheets, ('Tek Sayfa',))

    def test_missing_export_data_sheets_or_failed_sheet_selection(self):
        for case in ('data', 'sheets', 'selection'):
            with self.subTest(case=case):
                self.app.data = None if case == 'data' else FakePdfData()
                self.model.sheets = () if case == 'sheets' else ('Sheet1',)
                if case == 'selection':
                    self.app.data.ok = False
                self.assertEqual(self.run_one()[0], 'error')
                self.assertFalse(self.model.calls)

    def test_missing_invalid_or_truncated_pdf_is_rejected(self):
        for content in (None, b'', b'invalid pdf', b'%PDF-1.7', PDF[:-6]):
            with self.subTest(content=content):
                self.model.content = content
                self.assertEqual(self.run_one()[0], 'error')
                self.assertFalse(self.target.exists())
                self.assertFalse(list(self.output.glob('.*')))

    def test_save_error_is_failure_even_if_api_returns_true(self):
        self.model.save_error = 1
        self.assertEqual(self.run_one()[0], 'error')
        self.assertFalse(self.target.exists())

    def test_open_and_save_warnings_are_reported(self):
        self.app.opened.clear()
        self.app.open_warning, self.model.save_warning = 4, 8
        status, detail = self.run_one()
        self.assertEqual(status, 'success')
        self.assertIn('Açma uyarısı: 4', detail)
        self.assertIn('Kaydetme uyarısı: 8', detail)

    def test_destination_failure_is_reported_per_drawing(self):
        self.output.write_bytes(b'not a folder')
        status, detail = self.run_one()
        self.assertEqual(status, 'error')
        self.assertTrue(detail)
        self.assertFalse(self.model.calls)

    def test_batch_summary_com_and_output(self):
        messages = self.run_batch()
        summary = messages[-1][1]
        self.assertEqual((summary['state'], summary['processed'], summary['succeeded']), ('completed', 1, 1))
        self.assertEqual(self.target.read_bytes(), PDF)
        self.com.CoInitialize.assert_called_once()
        self.com.CoUninitialize.assert_called_once()

    def test_batch_continues_after_bad_drawing(self):
        other = self.source/'second.slddrw'
        other.touch()
        second = FakeDrawing(other)
        self.app = FakePdfApp([self.model, second])
        self.model.save_ok = False
        summary = self.run_batch()[-1][1]
        self.assertEqual((summary['processed'], summary['failed'], summary['succeeded']), (2, 1, 1))

    def test_batch_stop_between_drawings(self):
        other = self.source/'second.slddrw'
        other.touch()
        self.app = FakePdfApp([self.model, FakeDrawing(other)])
        stop = Event()
        self.model.on_save = lambda path: stop.set()
        summary = self.run_batch(stop)[-1][1]
        self.assertEqual((summary['state'], summary['processed'], summary['total']), ('cancelled', 1, 2))

    def test_empty_and_precancelled_do_not_connect(self):
        self.drawing.unlink()
        self.assertEqual(self.run_batch()[-1][1]['state'], 'empty')
        stop = Event()
        stop.set()
        self.assertEqual(self.run_batch(stop)[-1][1]['state'], 'cancelled')
        self.com.CoInitialize.assert_not_called()

    def test_connection_failure_cleans_up_com(self):
        events = Queue()
        with patch.object(ex, 'connect_to_solidworks', side_effect=RuntimeError('connection failed')):
            ex.export_drawings(self.source, self.output, True, False, events)
        self.assertEqual(list(events.queue)[-1][1]['state'], 'error')
        self.com.CoUninitialize.assert_called_once()

    def test_missing_pywin32_returns_error_and_done(self):
        with patch.object(ex, 'pythoncom', None):
            messages = self.run_batch()
        self.assertEqual(messages[-1][0], 'done')
        self.assertEqual(messages[-1][1]['state'], 'error')


if __name__ == '__main__':
    unittest.main()
