import builtins
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from pdf.settings import load_settings, save_settings
from solidworks.connection import connect_to_solidworks


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'GOKWORKS/settings.json'

    def test_preferences_roundtrip_turkish_paths_and_independent_modules(self):
        data = {'pdf_source': 'C:/İmalat/Çizimler', 'pdf_recursive': True,
                'dxf_dwg_source': 'C:/İmalat/Parçalar', 'dxf_dwg_format': 'DXF + DWG',
                'dxf_dwg_overwrite': False, 'custom_setting': 'koru'}
        save_settings(data, self.path)
        self.assertEqual(load_settings(self.path), data)
        self.assertIn('İmalat', self.path.read_text(encoding='utf-8'))
        self.assertFalse(self.path.with_suffix('.tmp').exists())

    def test_missing_corrupt_and_wrong_shape_settings_fall_back(self):
        self.assertEqual(load_settings(self.path), {})
        self.path.parent.mkdir()
        for content in ('{bad json', 'null', '[]', '42', '\ufffdinvalid'):
            self.path.write_text(content, encoding='utf-8')
            with self.subTest(content=content):
                self.assertEqual(load_settings(self.path), {})
        self.path.write_bytes(b'\xff\xfe')
        self.assertEqual(load_settings(self.path), {})

    def test_failed_publish_preserves_previous_settings(self):
        save_settings({'old': 'keep'}, self.path)
        with patch('pdf.settings.os.replace', side_effect=OSError('blocked')):
            with self.assertRaises(OSError):
                save_settings({'new': 'value'}, self.path)
        self.assertEqual(load_settings(self.path), {'old': 'keep'})

    def test_unreadable_settings_fall_back(self):
        with patch.object(Path, 'read_text', side_effect=PermissionError('blocked')):
            self.assertEqual(load_settings(self.path), {})


class ConnectionTests(unittest.TestCase):
    def test_raw_connection_uses_existing_idispatch_without_win32com_type_wrapping(self):
        calls=[]
        class Active:
            def QueryInterface(self,iid):calls.append(('query',iid));return self
            def GetTypeInfo(self):raise AssertionError('Type information must not be requested')
        active=Active()
        pythoncom=ModuleType('pythoncom')
        pythoncom.IID_IDispatch='IDispatch'
        pythoncom.GetActiveObject=lambda clsid: calls.append(('existing',clsid)) or active
        with patch.dict(sys.modules,{'pythoncom':pythoncom}):
            self.assertIs(connect_to_solidworks(raw=True),active)
        self.assertEqual(calls,[('existing','SldWorks.Application'),('query','IDispatch')])

    @unittest.skipUnless(sys.platform == 'win32', 'Gerçek pywin32 API kontrolü Windows gerektirir.')
    def test_raw_connection_uses_real_pywin32_exports_without_a_running_cad_server(self):
        import pythoncom

        active = Mock()
        dispatch = object()
        active.QueryInterface.return_value = dispatch
        # Keep the real module and constants; only the running CAD server is
        # replaced. Invented pythoncom functions must fail this contract test.
        with patch.object(pythoncom, 'GetActiveObject', return_value=active) as get_active:
            self.assertIs(connect_to_solidworks(raw=True), dispatch)
        get_active.assert_called_once_with('SldWorks.Application')
        active.QueryInterface.assert_called_once_with(pythoncom.IID_IDispatch)

    def stub_modules(self, get_active):
        package, client = ModuleType('win32com'), ModuleType('win32com.client')
        package.__path__ = []
        package.client = client
        client.GetActiveObject = get_active
        return patch.dict(sys.modules, {'win32com': package, 'win32com.client': client})

    def test_connects_to_existing_session_without_starting_solidworks(self):
        application = object()
        get_active = Mock(return_value=application)
        with self.stub_modules(get_active):
            self.assertIs(connect_to_solidworks(), application)
        get_active.assert_called_once_with('SldWorks.Application')

    def test_inactive_session_reports_actionable_error(self):
        with self.stub_modules(Mock(side_effect=RuntimeError('COM unavailable'))):
            with self.assertRaisesRegex(RuntimeError, 'SolidWorks açık değil') as caught:
                connect_to_solidworks()
        self.assertIn('COM unavailable', str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)

    def test_missing_pywin32_reports_install_command(self):
        real_import = builtins.__import__
        def unavailable(name, *args, **kwargs):
            if name == 'win32com.client':
                raise ImportError('not installed')
            return real_import(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=unavailable):
            with self.assertRaisesRegex(RuntimeError, 'pip install pywin32'):
                connect_to_solidworks()


class EntryPointTests(unittest.TestCase):
    def test_main_script_calls_application_entrypoint(self):
        entry = Path(__file__).resolve().parents[1]/'main.py'
        with patch('gui_qt.app.main') as start:
            runpy.run_path(str(entry), run_name='__main__')
        start.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
