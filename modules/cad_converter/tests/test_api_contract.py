"""Published COM shapes, installed constants and session cleanup boundaries."""

from dataclasses import replace
import sys
from types import SimpleNamespace, ModuleType

import pytest

from modules.cad_converter import api
from modules.cad_converter.exporter import convert
from modules.cad_converter.models import Source
from .test_converter import setup, run
from .fakes import C, FakeSession


def test_enum_reader_uses_pytypeattr_members_and_vardesc_constant_values():
    class Info:
        def GetTypeAttr(self): return SimpleNamespace(typekind=0, cVars=2)
        def GetVarDesc(self, index): return (index, (75, 211)[index], None, 0, 2)
        def GetDocumentation(self, index): return (('swStepAP', 'swExportStlUnits')[index],)
    library = SimpleNamespace(GetTypeInfoCount=lambda: 1, GetTypeInfo=lambda index: Info())
    assert api.enum_values(library) == {'swStepAP':75, 'swExportStlUnits':211}


def test_tlb_registry_versions_are_hexadecimal_and_not_guessed_preferences(monkeypatch):
    calls = []
    pythoncom = ModuleType('pythoncom')
    pythoncom.LoadRegTypeLib = lambda *args: calls.append(args) or 'library'
    win32com = ModuleType('win32com'); client = ModuleType('win32com.client'); select = ModuleType('win32com.client.selecttlb')
    select.EnumTlbs = lambda: [SimpleNamespace(desc='SOLIDWORKS 2025 Constant type library', clsid='registered-id', major='21', minor='a', lcid=0)]
    for name, module in [('pythoncom',pythoncom), ('win32com',win32com), ('win32com.client',client), ('win32com.client.selecttlb',select)]: monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(api, 'enum_values', lambda library: {'swStepAP':75})
    assert api.load_constants(None) == {'swStepAP':75}
    assert calls == [('registered-id',33,10,0)]


def test_raw_dispatch_routes_get_and_method_without_makepy_or_retrying_other_interfaces():
    calls = []
    class Dispatch:
        def GetIDsOfNames(self, locale, name): assert locale == 0; return {'Name':1,'SaveAs3':2}[name]
        def Invoke(self, member, locale, flags, result, *args): calls.append((member,flags,args)); return True
    obj = SimpleNamespace(_oleobj_=Dispatch())
    assert api.get(obj,'Name') and api.call(obj,'SaveAs3','file',0,3,None,None,'errors','warnings')
    assert calls == [(1,2,()), (2,1,('file',0,3,None,None,'errors','warnings'))]


def test_com_initialization_connection_failure_and_pointer_release_order(setup, monkeypatch):
    app, model, _, _ = setup
    events = []
    com = ModuleType('pythoncom'); com.CoInitialize = lambda: events.append('init')
    com.CoUninitialize = lambda: events.append('uninit')
    monkeypatch.setitem(sys.modules,'pythoncom',com)
    monkeypatch.setattr('solidworks.connection.connect_to_solidworks', lambda **kw: app)
    monkeypatch.setattr(api,'load_constants',lambda app: C)
    with api.Session() as session:
        assert events == ['init']
    assert events == ['init','uninit'] and session.app is None
    def broken(**kwargs): raise RuntimeError('connection unavailable')
    monkeypatch.setattr('solidworks.connection.connect_to_solidworks', broken)
    with pytest.raises(RuntimeError, match='connection unavailable'):
        with api.Session(): pass
    assert events == ['init','uninit','init','uninit']


def test_stl_snapshot_precedes_quality_setter_that_changes_custom_numeric_preferences(setup, monkeypatch):
    app, _, options, _ = setup
    before = dict(app.preferences)
    setter = app.SetUserPreferenceIntegerValue
    def dependent(key, value):
        if key == C['swSTLQuality']:
            app.preferences[C['swSTLDeviation']] = .007
            app.preferences[C['swSTLAngleTolerance']] = .5
        return setter(key,value)
    monkeypatch.setattr(app,'SetUserPreferenceIntegerValue',dependent)
    events = run(setup, options=replace(options,formats=('stl_binary',),stl_quality='custom',deviation_mm=.05))
    assert events.summary['succeeded'] == 1 and app.preferences == before


def test_ordinary_preset_also_restores_its_implicit_numeric_changes(setup, monkeypatch):
    app, _, options, _ = setup
    before = dict(app.preferences); setter = app.SetUserPreferenceIntegerValue
    def dependent(key, value):
        if key == C['swSTLQuality']:
            app.preferences[C['swSTLDeviation']] = .007
            app.preferences[C['swSTLAngleTolerance']] = .5
        return setter(key,value)
    monkeypatch.setattr(app,'SetUserPreferenceIntegerValue',dependent)
    assert run(setup,options=replace(options,formats=('stl_binary',),stl_quality='coarse')).summary['succeeded'] == 1
    assert app.preferences == before


def test_document_load_warning_is_reported_separately_from_save_warning(setup):
    app, _, _, _ = setup; app.load_warning = 2
    events = run(setup)
    assert events.summary['warned'] == 1 and events.results[0]['open_warnings'] == 2 and events.results[0]['warnings'] == 0


def test_already_open_warning_preserves_user_ownership_even_if_lookup_missed_document(setup):
    app, model, _, _ = setup; app.load_warning = C['swFileLoadWarning_AlreadyOpen']
    run(setup)
    assert model.opened and not app.closed


def test_readonly_silent_and_full_resolution_options_are_used_for_owned_documents(setup, monkeypatch):
    app, model, _, _ = setup; calls = []; method = app.OpenDoc6
    def opened(path, kind, options, configuration, errors, warnings):
        calls.append(options); return method(path, kind, options, configuration, errors, warnings)
    monkeypatch.setattr(app,'OpenDoc6',opened)
    assert run(setup).summary['succeeded'] == 1
    assert calls == [C['swOpenDocOptions_Silent'] | C['swOpenDocOptions_ReadOnly'] | C['swOpenDocOptions_OverrideDefaultLoadLightweight']]


def test_unknown_runtime_constant_never_falls_back_to_an_arbitrary_id(setup):
    app, _, _, _ = setup
    with FakeSession(app) as session:
        with pytest.raises(RuntimeError, match='desteklemiyor'): session.c('swInventedExportFlag')
