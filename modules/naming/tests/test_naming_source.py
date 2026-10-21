"""Selected Pack and Go source ownership and real COM output signatures."""

from pathlib import Path
from tempfile import TemporaryDirectory
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from modules.naming import exporter as naming
from tests.support.solidworks import Variant
from modules.naming.tests.test_naming import App, Pack


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
            TKIND_INTERFACE=3, TYPEFLAG_FDUAL=64, IID_IDispatch='IDispatch',
            MakeIID=lambda value: value,
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
        self.client.Dispatch.assert_not_called()

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

    def test_pack_and_go_uses_live_output_signature_without_makepy_wrapping(self):
        app = App(self.folder)
        info = SimpleNamespace(GetDocumentation=lambda member: ('IModelDocExtension',),
                               GetTypeAttr=lambda: (0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 64))
        # Automation may expose an explicit output hidden by the .NET API.
        arguments = ((16384 | 9, 2),)
        desc = (207, (), arguments, 4, 1, 4, 0, 40, (25, 0), 0)
        entry = SimpleNamespace(dispid=207, names=('GetPackAndGo',), desc=desc)
        self.client.build = SimpleNamespace(DispatchItem=Mock(return_value=SimpleNamespace(
            mapFuncs={'GetPackAndGo': entry}, propMapGet={})))
        raw = SimpleNamespace(GetIDsOfNames=Mock(return_value=207), GetTypeInfo=Mock(return_value=info),
                              InvokeTypes=Mock(return_value=(0, Pack(app))))
        app.extension._oleobj_ = raw
        app.extension._FlagAsMethod = Mock()
        self.client.Dispatch.side_effect = AssertionError('Automatic makepy factory must not run')
        snapshot = naming.scan(app)
        self.assertEqual(snapshot.root, app.paths[0])
        raw.InvokeTypes.assert_called_once_with(207, 0, 1, (25, 0), arguments)
        self.client.Dispatch.assert_not_called()

        entry.desc = (207, (), ((8, 1),), 4, 1, 4, 0, 40, (9, 0), 0)
        raw.InvokeTypes.reset_mock()
        with self.assertRaisesRegex(RuntimeError, 'Beklenmeyen GetPackAndGo imzası'):
            naming.scan(app)
        raw.InvokeTypes.assert_not_called()

    def test_dual_type_info_is_converted_to_automation_before_reading_signature(self):
        attributes = (0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 64)
        automation = SimpleNamespace(GetTypeAttr=lambda: attributes,
                                     GetDocumentation=lambda member: ('IModelDocExtension',))
        native = SimpleNamespace(GetTypeAttr=lambda: (0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 64),
                                 GetRefTypeOfImplType=Mock(return_value=41),
                                 GetRefTypeInfo=Mock(return_value=automation))
        entry = SimpleNamespace(dispid=207, names=('GetPackAndGo',),
                                desc=(207, (), (), 4, 1, 4, 0, 40, (9, 0), 0))
        builder = Mock(return_value=SimpleNamespace(mapFuncs={'GetPackAndGo': entry}, propMapGet={}))
        self.client.build = SimpleNamespace(DispatchItem=builder)
        result = naming._pack_signature(SimpleNamespace(GetTypeInfo=lambda: native), 207)
        self.assertEqual(result[:3], (1, (9, 0), ()))
        native.GetRefTypeOfImplType.assert_called_once_with(-1)
        native.GetRefTypeInfo.assert_called_once_with(41)
        builder.assert_called_once_with(automation, attributes, bForUser=0)

    def test_unknown_pack_result_preserves_explicit_pack_interface_before_wrapping(self):
        dispatch = SimpleNamespace(InvokeTypes=Mock(), _FlagAsMethod=Mock())
        unknown = SimpleNamespace(QueryInterface=Mock(return_value=dispatch))
        self.assertIs(naming._pack_result(unknown, (13, 0), ()), dispatch)
        unknown.QueryInterface.assert_called_once_with(naming.PACK_AND_GO_IID, 'IDispatch')
        self.client.dynamic.DumbDispatch.assert_called_once_with(dispatch)
        dispatch._FlagAsMethod.assert_called_once()

    def test_extension_uses_requested_dual_interface_instead_of_default_dispatch(self):
        app = App(self.folder)
        pointer = SimpleNamespace(GetIDsOfNames=Mock(return_value=207),
                                  InvokeTypes=Mock(return_value=Pack(app)))
        correct = SimpleNamespace(_oleobj_=pointer, _FlagAsMethod=Mock())
        wrong = SimpleNamespace(QueryInterface=Mock(return_value=correct),
                                InvokeTypes=Mock(side_effect=AssertionError('Default dispatch invoked')))
        app.extension._oleobj_ = wrong
        self.assertEqual(naming.scan(app).root, app.paths[0])
        wrong.QueryInterface.assert_called_once_with(naming.MODEL_EXTENSION_IID, 'IDispatch')
        wrong.InvokeTypes.assert_not_called()
        pointer.InvokeTypes.assert_called_once_with(207, 0, 1, (9, 0), ())

    def test_member_binding_avoids_failing_dual_conversion_and_full_table_enumeration(self):
        # A valid member remains usable when a server cannot provide the
        # alternate dual view or an unrelated function descriptor.
        desc = (207, (), (), 4, 1, 4, 0, 40, (9, 0), 0)
        entry = SimpleNamespace(dispid=207, names=('GetPackAndGo',), desc=desc)
        table = SimpleNamespace(mapFuncs={}, propMapGet={})
        table._AddFunc_ = Mock(side_effect=lambda *args: table.mapFuncs.update(GetPackAndGo=entry))
        builder = Mock(return_value=table)
        self.client.build = SimpleNamespace(DispatchItem=builder)
        info = SimpleNamespace(GetTypeComp=Mock(return_value=SimpleNamespace(
            Bind=Mock(return_value=(1, desc)))),
            GetTypeAttr=Mock(side_effect=RuntimeError('Invalid index')),
            GetDocumentation=lambda member: ('IModelDocExtension',))
        result = naming._pack_signature(SimpleNamespace(GetTypeInfo=lambda: info), 207)
        self.assertEqual(result[:3], (1, (9, 0), ()))
        self.assertIn('çalışan API', result[3])
        info.GetTypeComp().Bind.assert_called_once_with('GetPackAndGo', 1)
        info.GetTypeAttr.assert_not_called()
        builder.assert_called_once_with()
        table._AddFunc_.assert_called_once_with(info, desc, 0)

    def test_native_retval_is_converted_to_automation_return_without_extra_user_input(self):
        for result_type in (9, 13):
            with self.subTest(result_type=result_type):
                # pywin32 _AddFunc_ has resolved native VT_HRESULT to VT_I4.
                desc = (207, (), ((16384 | result_type, 2 | 8),), 1, 1, 4, 0, 40, (3, 0), 0)
                entry = SimpleNamespace(dispid=207, names=('GetPackAndGo',), desc=desc)
                table = SimpleNamespace(mapFuncs={'GetPackAndGo': entry}, propMapGet={}, _AddFunc_=Mock())
                self.client.build = SimpleNamespace(DispatchItem=lambda: table)
                info = SimpleNamespace(GetTypeComp=lambda: SimpleNamespace(Bind=lambda *args: (1, desc)),
                                       GetDocumentation=lambda member: ('IModelDocExtension',))
                result = naming._pack_signature(SimpleNamespace(GetTypeInfo=lambda: info), 207)
                self.assertEqual(result[:3], (1, (result_type, 0), ()))

    def test_member_binding_preserves_live_property_get_invocation(self):
        desc = (207, (), (), 4, 2, 4, 0, 40, (9, 0), 0)
        entry = SimpleNamespace(dispid=207, names=('GetPackAndGo',), desc=desc)
        table = SimpleNamespace(mapFuncs={}, propMapGet={'GetPackAndGo': entry}, _AddFunc_=Mock())
        self.client.build = SimpleNamespace(DispatchItem=lambda: table)
        bind = Mock(side_effect=[(0, None), (1, desc)])
        info = SimpleNamespace(GetTypeComp=lambda: SimpleNamespace(Bind=bind),
                               GetDocumentation=lambda member: ('IModelDocExtension',))
        result = naming._pack_signature(SimpleNamespace(GetTypeInfo=lambda: info), 207)
        self.assertEqual(result[:3], (2, (9, 0), ()))
        self.assertEqual(bind.call_args_list[0].args, ('GetPackAndGo', 1))
        self.assertEqual(bind.call_args_list[1].args, ('GetPackAndGo', 2))

    def test_member_binding_survives_invalid_documentation_and_method_binding(self):
        desc = (207, (), (), 4, 2, 4, 0, 40, (9, 0), 0)
        entry = SimpleNamespace(dispid=207, names=('GetPackAndGo',), desc=desc)
        table = SimpleNamespace(mapFuncs={}, propMapGet={'GetPackAndGo': entry}, _AddFunc_=Mock())
        self.client.build = SimpleNamespace(DispatchItem=lambda: table)
        bind = Mock(side_effect=[RuntimeError('Invalid index'), (1, desc)])
        info = SimpleNamespace(GetTypeComp=lambda: SimpleNamespace(Bind=bind),
                              GetDocumentation=Mock(side_effect=RuntimeError('Invalid index')))
        result = naming._pack_signature(SimpleNamespace(GetTypeInfo=lambda: info), 207)
        self.assertEqual(result[:3], (2, (9, 0), ()))
        self.assertIn('ITypeComp.Bind', result[3])
        self.assertIn('çalışan API', result[3])

    def test_wrong_extension_interface_fails_before_pack_call_or_source_write(self):
        app = App(self.folder)
        ole = SimpleNamespace(QueryInterface=Mock(side_effect=RuntimeError('No interface')),
                              InvokeTypes=Mock())
        app.extension._oleobj_ = ole
        with self.assertRaisesRegex(RuntimeError, 'ModelDocExtension okunamadı.*No interface'):
            naming.scan(app)
        ole.InvokeTypes.assert_not_called()

    def test_pack_and_go_wrap_failure_is_distinct_from_native_call_failure(self):
        app = App(self.folder)
        pointer = SimpleNamespace(InvokeTypes=Mock())
        ole = SimpleNamespace(GetIDsOfNames=lambda *args: 207, InvokeTypes=Mock(return_value=pointer))
        app.extension._oleobj_ = ole
        app.extension._FlagAsMethod = Mock()

        def wrap(obj):
            if obj is pointer:
                raise RuntimeError('wrapper failure')
            return obj

        self.client.dynamic.DumbDispatch.side_effect = wrap
        with self.assertRaisesRegex(RuntimeError, 'nesnesi hazırlanamadı.*wrapper failure'):
            naming.scan(app)
        ole.InvokeTypes.assert_called_once()

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
