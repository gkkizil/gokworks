"""Selected Pack and Go source ownership and real COM output signatures."""

from pathlib import Path
from tempfile import TemporaryDirectory
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from naming import exporter as naming
from tests.support.solidworks import Variant
from tests.test_naming import App, Pack


class SourceApp(App):
    def __init__(self, folder, *, loaded=False, window=False):
        super().__init__(folder)
        self.source = self.ActiveDoc
        self.source.GetTitle = lambda: 'Ana.sldasm'
        self.source.Visible = False
        self.source.ConfigurationManager = SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name='İnce'))
        self.other_path = str(folder/'Aktif-parça.sldprt')
        Path(self.other_path).write_text('{"refs": []}', encoding='utf-8')
        self.previous = SimpleNamespace(GetPathName=lambda: self.other_path,
            GetTitle=lambda: 'Aktif-parça.sldprt', GetType=lambda: 1,
            GetSaveFlag=lambda: True, Visible=True, Extension=self.extension)
        self.ActiveDoc = self.previous
        self.loaded = {self.other_path: self.previous}
        self.windows = {self.other_path: self.previous}
        if loaded:
            self.loaded[self.paths[0]] = self.source
        if window:
            self.windows[self.paths[0]] = self.source
        self.opens, self.closes, self.activations = [], [], []
        self.warning = self.open_error = 0
        self.activation_warning = 0
        self.restore_error = False
        self.on_open = None

    def GetOpenDocument(self, path):
        return self.loaded.get(path)

    def GetOpenDocumentByName(self, path):
        return self.windows.get(path)

    def OpenDoc6(self, path, kind, options, configuration, errors, warnings):
        assert path == self.paths[0] and kind == 2
        assert options == 1 and configuration == ''
        assert errors.kind == 16384 | 3 and warnings.kind == 16384 | 3
        self.opens.append(path)
        errors.value, warnings.value = self.open_error, self.warning
        self.loaded[path] = self.windows[path] = self.source
        self.ActiveDoc = self.source
        if self.on_open:
            self.on_open()
        return self.source

    def CloseDoc(self, title):
        assert title == 'Ana.sldasm'
        self.closes.append(title)
        self.loaded.pop(self.paths[0], None)
        self.windows.pop(self.paths[0], None)
        if self.ActiveDoc is self.source:
            self.ActiveDoc = None

    def ActivateDoc3(self, path, preferences, rebuild, errors):
        assert preferences is False and rebuild == 1
        self.activations.append(path)
        if self.restore_error:
            errors.value = 8
            return None
        errors.value = self.activation_warning
        self.ActiveDoc = self.loaded[path]
        return self.ActiveDoc


class NamingSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.com = SimpleNamespace(VT_ARRAY=8192, VT_BSTR=8, VT_BYREF=16384,
            VT_VARIANT=12, VT_I4=3, VT_DISPATCH=9, DISPATCH_METHOD=1,
            CoInitialize=Mock(), CoUninitialize=Mock())
        self.client = SimpleNamespace(VARIANT=Variant, Dispatch=Mock(side_effect=lambda obj: obj),
            dynamic=SimpleNamespace(DumbDispatch=Mock(side_effect=lambda obj: obj)))
        self.enterContext(patch.multiple(naming, pythoncom=self.com,
            win32com=SimpleNamespace(client=self.client)))

    def test_loaded_hidden_source_restores_visibility_configuration_and_active_document(self):
        app = SourceApp(self.folder, loaded=True)
        app.activation_warning = 2  # Needs-rebuild warning is successful no-rebuild activation.
        snapshot = naming.scan(app, source_path=app.paths[0])
        self.assertEqual(snapshot.root, app.paths[0])
        self.assertEqual(snapshot.source_path, app.paths[0])
        self.assertIs(app.ActiveDoc, app.previous)
        self.assertFalse(app.source.Visible)
        self.assertEqual(app.source.ConfigurationManager.ActiveConfiguration.Name, 'İnce')
        self.assertEqual((app.opens, app.closes), ([], []))
        self.assertEqual(app.activations, [app.paths[0], app.other_path])
        self.assertTrue(app.previous.GetSaveFlag())
        app = SourceApp(self.folder, loaded=True)
        app.source.Visible = True
        naming.scan(app, source_path=app.paths[0])
        self.assertEqual((app.opens, app.closes), ([], []))
        self.assertEqual(app.activations, [app.paths[0], app.other_path])

    def test_selected_unopened_source_is_reopened_for_save_even_after_active_doc_changes(self):
        app = SourceApp(self.folder)
        originals = {path: Path(path).read_bytes() for path in app.paths}
        snapshot = naming.scan(app, source_path=app.paths[0])
        self.assertIs(app.ActiveDoc, app.previous)
        self.assertEqual(app.closes, ['Ana.sldasm'])
        destination = self.folder/'renamed'
        entries = naming.plan_names(snapshot, destination, naming.Rules(prefix='P-'))
        report = naming.execute(app, snapshot, entries, destination)
        self.assertEqual(Path(report['root']).name, 'P-Ana.sldasm')
        self.assertIs(app.ActiveDoc, app.previous)
        self.assertEqual(app.opens, [app.paths[0], app.paths[0]])
        self.assertEqual(app.closes, ['Ana.sldasm', 'Ana.sldasm'])
        self.assertTrue(all(Path(path).read_bytes() == original for path, original in originals.items()))

    def test_borrowed_dirty_source_is_rejected_without_open_close_or_active_switch(self):
        app = SourceApp(self.folder, loaded=True)
        app.dirty = True
        with self.assertRaisesRegex(RuntimeError, 'kaydedilmemiş'):
            naming.scan(app, source_path=app.paths[0])
        self.assertIs(app.ActiveDoc, app.previous)
        self.assertEqual((app.opens, app.closes, app.activations), ([], [], []))

    def test_already_open_warning_prevents_closing_borrowed_document(self):
        app = SourceApp(self.folder)
        app.warning = 128
        snapshot = naming.scan(app, source_path=app.paths[0])
        self.assertEqual(snapshot.root, app.paths[0])
        self.assertEqual(app.closes, [])
        self.assertIs(app.loaded[app.paths[0]], app.source)
        self.assertIs(app.ActiveDoc, app.previous)

    def test_cancel_or_scan_failure_closes_owned_source_and_restores_active_document(self):
        for operation in ('cancel', 'failure', 'open_error'):
            with self.subTest(operation=operation):
                app = SourceApp(self.folder)
                stop = threading.Event()
                if operation == 'cancel':
                    app.on_open = stop.set
                    error = naming.Cancelled
                elif operation == 'failure':
                    app.states[0] = 1
                    error = RuntimeError
                else:
                    app.open_error = 4
                    error = RuntimeError
                with self.assertRaises(error):
                    naming.scan(app, stop, source_path=app.paths[0])
                self.assertEqual(app.closes, ['Ana.sldasm'])
                self.assertIs(app.ActiveDoc, app.previous)

    def test_cleanup_errors_are_reported_and_new_dirty_source_is_left_open(self):
        app = SourceApp(self.folder)
        app.restore_error = True
        with self.assertRaisesRegex(RuntimeError, 'Önceki aktif belge'):
            naming.scan(app, source_path=app.paths[0])
        self.assertEqual(app.closes, ['Ana.sldasm'])
        app = SourceApp(self.folder)
        app.on_open = lambda: setattr(app, 'dirty', True)
        with self.assertRaisesRegex(RuntimeError, 'açık bırakıldı'):
            naming.scan(app, source_path=app.paths[0])
        self.assertEqual(app.closes, [])
        self.assertIs(app.loaded[app.paths[0]], app.source)
        self.assertIs(app.ActiveDoc, app.previous)

    def test_active_assembly_mode_rejects_active_part_and_preserves_root_change_guard(self):
        app = SourceApp(self.folder, loaded=True)
        with self.assertRaisesRegex(RuntimeError, 'bir montajı etkinleştirin'):
            naming.scan(app, require_assembly=True)
        app.ActiveDoc = app.source
        snapshot = naming.scan(app, require_assembly=True)
        self.assertIsNone(snapshot.source_path)
        self.assertTrue(snapshot.require_assembly)
        app.ActiveDoc = app.previous
        with self.assertRaisesRegex(RuntimeError, 'bir montajı etkinleştirin'):
            naming.execute(app, snapshot, naming.plan_names(snapshot, self.folder/'out'), self.folder/'out')
        self.assertFalse((self.folder/'out').exists())

    def test_makepy_missing_outputs_retry_through_late_bound_child_and_name_api_failure(self):
        class MissingOutput(Exception):
            hresult = -2147352561

        class TypedPack:
            _oleobj_ = object()
            @property
            def GetDocumentNames(self):
                raise MissingOutput('Parametre seçime bağlı değil')

        class DynamicPack:
            _FlagAsMethod = Mock()

            def GetDocumentNames(self, names):
                self_names = ('C:/Ana.sldasm', 'C:/Levha.sldprt')
                names.value = self_names
                return True
            def GetDocumentSaveToNames(self, names, states):
                names.value, states.value = ('C:/Ana.sldasm',), (0,)
                return True

        typed, dynamic = TypedPack(), DynamicPack()
        self.client.dynamic.DumbDispatch.side_effect = lambda obj: dynamic if obj is typed else obj
        self.assertEqual(naming._arrays(typed, 'GetDocumentNames', 1),
                         (('C:/Ana.sldasm', 'C:/Levha.sldprt'),))
        typed.GetDocumentSaveToNames = lambda: (_ for _ in ()).throw(MissingOutput())
        self.assertEqual(naming._arrays(typed, 'GetDocumentSaveToNames', 2),
                         (('C:/Ana.sldasm',), (0,)))
        dynamic.GetDocumentNames = Mock(side_effect=MissingOutput('Parametre seçime bağlı değil'))
        with self.assertRaisesRegex(RuntimeError, 'GetDocumentNames çıkış parametreleri'):
            naming._arrays(typed, 'GetDocumentNames', 1)

    def test_pack_and_go_child_is_invoked_as_method_without_property_probe(self):
        class MissingParameter(Exception):
            hresult = -2147352561

        class Extension:
            def __init__(self, app):
                self.app = app
                self.methods = set()
                self.calls = 0
                self.failure = None
                self._oleobj_ = SimpleNamespace(GetIDsOfNames=self.ids, InvokeTypes=self.invoke)

            def ids(self, lcid, name):
                self.app_test.assertEqual((lcid, name), (0, 'GetPackAndGo'))
                return 41

            def invoke(self, *args):
                self.app_test.assertEqual(args, (41, 0, 1, (9, 0), ()))
                return self.get_pack()

            def _FlagAsMethod(self, *names):
                self.methods.update(names)

            @property
            def GetPackAndGo(self):
                raise MissingParameter('Parametre seçime bağlı değil')

            def get_pack(self):
                self.calls += 1
                if self.failure:
                    raise self.failure
                return Pack(self.app)

            def SavePackAndGo(self, pg):
                return self.app.save(pg)

        app = App(self.folder)
        typed, dynamic = Extension(app), Extension(app)
        typed.app_test = dynamic.app_test = self
        app.ActiveDoc.Extension = typed
        self.client.dynamic.DumbDispatch.side_effect = lambda obj: dynamic if obj is typed else obj
        snapshot = naming.scan(app)
        self.assertEqual(snapshot.root, app.paths[0])
        self.assertEqual((typed.calls, dynamic.calls), (0, 1))
        self.client.dynamic.DumbDispatch.assert_called_once_with(typed)
        self.client.Dispatch.assert_called_once()

        destination = self.folder/'renamed-native'
        report = naming.execute(app, snapshot,
            naming.plan_names(snapshot, destination, naming.Rules(prefix='P-')), destination)
        self.assertEqual(Path(report['root']).name, 'P-Ana.sldasm')
        self.assertEqual(dynamic.calls, 2)
        self.assertIn('SavePackAndGo', dynamic.methods)

        # A real method failure must surface once, without fallback/retry.
        dynamic.failure = MissingParameter('method failure')
        with self.assertRaisesRegex(RuntimeError, 'GetPackAndGo başlatılamadı.*method failure') as caught:
            naming.scan(app)
        self.assertIs(caught.exception.__cause__, dynamic.failure)
        self.assertEqual(dynamic.calls, 3)

    def test_visible_selected_source_is_activated_before_pack_and_go(self):
        app = SourceApp(self.folder, loaded=True, window=True)
        app.source.Visible = True

        def get_pack():
            if app.ActiveDoc is not app.source:
                raise RuntimeError("(-2147352561, 'Parametre seçime bağlı değil.', None, None)")
            return Pack(app)

        app.extension.GetPackAndGo = get_pack
        snapshot = naming.scan(app, source_path=app.paths[0])
        self.assertEqual(snapshot.root, app.paths[0])
        self.assertEqual(app.activations, [app.paths[0], app.other_path])
        self.assertIs(app.ActiveDoc, app.previous)
        self.assertTrue(app.source.Visible)
        self.assertEqual((app.opens, app.closes), ([], []))


if __name__ == '__main__':
    unittest.main()
