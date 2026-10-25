"""Small structural CAD fixtures and an in-memory COM boundary, NOT CAD kernels."""

from contextlib import contextmanager
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from modules.cad_converter.api import Session

C = json.loads(Path(__file__).with_name('constants.json').read_text())


def content(key):
    if key.startswith('step'):
        schema = {'step203': 'CONFIG_CONTROL_DESIGN', 'step214': 'AUTOMOTIVE_DESIGN',
                  'step242': 'AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'}[key]
        return (f"ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('{schema}'));\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\nENDSEC;\nEND-ISO-10303-21;\n").encode()
    if key == 'iges':
        rows = [('Synthetic fixture', 'S', 1), ('1H,,1H;', 'G', 1), ('1', 'D', 1),
                ('0', 'D', 2), ('116,0.,0.,0.;', 'P', 1), ('S      1G      1D      2P      1', 'T', 1)]
        return ('\n'.join(f'{text:<72}{kind}{seq:7}' for text, kind, seq in rows) + '\n').encode()
    if key == 'stl_binary': return b'Synthetic fixture'.ljust(80, b' ') + struct.pack('<I12fH', 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0)
    if key == 'stl_ascii':
        return b'solid fixture\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid fixture\n'
    header = b'**PART1;\nSCH=SCH_330;\n**END_OF_HEADER************************\n'
    return header + (bytes(range(100)) if key == 'xb' else b'1 2 3 4 5 6 7 8 9 1 2 3 4 5 6 7 8 9 1 2 3 4 5 6 7 8 9\n')


class Selection:
    def __init__(self): self.depth = 0
    def SuspendSelectionList(self): self.depth += 1; return 2
    def ResumeSelectionList2(self, append): assert append is False; self.depth -= 1


class Model:
    def __init__(self, path, app, configurations=('Default',), *, opened=False):
        self.path, self.app, self.names = str(path), app, configurations
        self.active = configurations[0]; self.opened = opened
        self.SelectionManager = Selection()
        self.Extension = Extension(self)
        self.components = []; self.dependencies = []; self.selected = True
        self.saved_source = False; self.show_calls = []; self.body_count = 1
    def GetPathName(self): return self.path
    def GetTitle(self): return Path(self.path).name
    def GetType(self): return C['swDocASSEMBLY'] if self.path.lower().endswith('.sldasm') else C['swDocPART']
    @property
    def ConfigurationManager(self): return SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name=self.active))
    def GetConfigurationNames(self): return self.names
    def ShowConfiguration2(self, name):
        self.show_calls.append(name)
        if name not in self.names: return False
        self.active = name; return True
    def ClearSelection2(self, all): assert all; self.selected = False
    def EditRebuild3(self): return True
    def GetComponents(self, top): assert top is False; return tuple(self.components)


class Extension:
    NeedsRebuild2 = False
    def __init__(self, model): self.model = model
    def SaveAs3(self, name, version, options, export, advanced, errors, warnings):
        app = self.model.app
        assert app.ActiveDoc is self.model and not self.model.selected
        assert version == C['swSaveAsCurrentVersion']
        assert options == C['swSaveAsOptions_Silent'] | C['swSaveAsOptions_Copy']
        app.saves.append((self.model.path, self.model.active, name))
        errors.value, warnings.value = app.save_error, app.save_warning
        if app.disconnect: raise RuntimeError('RPC disconnected')
        if app.save_error: return False
        suffix = Path(name).suffix
        key = {'.x_t': 'xt', '.x_b': 'xb', '.igs': 'iges'}.get(suffix)
        if suffix == '.step': key = 'step' + str(app.preferences[C['swStepAP']])
        if suffix == '.stl': key = 'stl_binary' if app.preferences[C['swSTLBinaryFormat']] else 'stl_ascii'
        Path(name).write_bytes(b'corrupt' if app.corrupt else content(key))
        if app.after_save: app.after_save()
        return True
    def PublishSTEP242File(self, name):
        app = self.model.app
        if app.mbd_error: return app.mbd_error
        app.saves.append((self.model.path, self.model.active, name))
        Path(name).write_bytes(content('step242')); return C['swPublishStep242_Success']


class Component:
    def __init__(self, model=None, *, path='', configuration='Default', virtual=False, suppressed=False):
        self.model, self.path, self.ReferencedConfiguration = model, path or (model.path if model else ''), configuration
        self.Name2 = Path(self.path).name or 'Virtual'; self.IsVirtual = virtual; self.suppressed = suppressed
    def GetSuppression2(self): return C['swComponentSuppressed'] if self.suppressed else C['swComponentFullyResolved']
    def GetPathName(self): return self.path
    def GetModelDoc2(self): return self.model


class App:
    def __init__(self):
        self.models = {}; self.ActiveDoc = None; self.saves = []; self.closed = []; self.open_calls = []
        self.preferences = dict.fromkeys(C.values(), 0)
        self.preferences[C['swStepAP']] = 214
        self.preferences[C['swSTLQuality']] = C['swSTLQuality_Fine']
        self.save_error = 0; self.save_warning = 0; self.load_error = 0; self.load_warning = 0
        self.mbd_error = 0; self.disconnect = False; self.corrupt = False; self.after_save = None
    def add(self, path, configurations=('Default',), *, opened=False):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'source CAD fixture')
        model = Model(path, self, configurations, opened=opened); self.models[str(path)] = model
        return model
    def GetOpenDocumentByName(self, path):
        model = self.models.get(str(path)); return model if model and model.opened else None
    def OpenDoc6(self, path, kind, options, configuration, errors, warnings):
        self.open_calls.append(path); errors.value, warnings.value = self.load_error, self.load_warning
        model = self.models.get(str(path))
        if model: model.opened = True; self.ActiveDoc = model
        return model
    def ActivateDoc3(self, name, preferences, option, errors):
        model = next((m for m in self.models.values() if m.path == name or m.GetTitle() == name), None)
        if model is None: errors.value = 1
        else: self.ActiveDoc = model
        return model
    def CloseDoc(self, title):
        self.closed.append(title)
        for model in self.models.values():
            if model.GetTitle() == title: model.opened = False
    def GetDocumentDependencies2(self, path, *args): return self.models[path].dependencies
    def GetUserPreferenceIntegerValue(self, key): return self.preferences[key]
    GetUserPreferenceToggle = GetUserPreferenceIntegerValue
    GetUserPreferenceDoubleValue = GetUserPreferenceIntegerValue
    def SetUserPreferenceIntegerValue(self, key, value): self.preferences[key] = value; return True
    def SetUserPreferenceToggle(self, key, value): self.preferences[key] = value
    SetUserPreferenceDoubleValue = SetUserPreferenceIntegerValue


class FakeSession(Session):
    def __init__(self, app): self.app = app
    def __enter__(self):
        self.constants = C; self.owned = {}; self.load_warnings = {}
        self.previous = self.app.ActiveDoc.path if self.app.ActiveDoc else ''
        self.pythoncom = SimpleNamespace(CoUninitialize=lambda: None)
        return self


class Events:
    def __init__(self): self.rows = []
    def put(self, row): self.rows.append(row)
    @property
    def results(self): return [row for kind, row in self.rows if kind == 'cad_result']
    @property
    def summary(self): return [row for kind, row in self.rows if kind == 'cad_done'][-1]
