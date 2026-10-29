"""SolidWorks COM doubles shared by export and sheet-metal tests.

These objects validate API arguments and failure paths; they do not replace
validation on a Windows machine running SolidWorks.
"""

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

DXF = b'0\nSECTION\n2\nENTITIES\n0\nLINE\n10\n0\n20\n0\n11\n10\n21\n20\n0\nENDSEC\n0\nEOF\n'
DWG = b'AC1032' + b'\x00' * 40

PDF = b'%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n'

class Variant:
    def __init__(self, kind, value):
        self.kind, self.value = kind, value


class FakeFeature:
    def __init__(self, name='Sheet-Metal1', kind='SheetMetal', thickness=.002,
                 suppressed=False, child=None, next_feature=None):
        self.Name, self.kind = name, kind
        self.thickness, self.suppressed = thickness, suppressed
        self.child, self.next = child, next_feature

    def GetTypeName2(self):
        return self.kind

    def GetNextFeature(self):
        return self.next

    GetNextSubFeature = GetNextFeature

    def GetFirstSubFeature(self):
        return self.child

    def IsSuppressed2(self, scope, configurations):
        assert scope == 1 and configurations.kind == 0
        return (self.suppressed,)

    def GetDefinition(self):
        return SimpleNamespace(Thickness=self.thickness)


class FakeComponent:
    def __init__(self, path, configuration='Default', children=(), state=2):
        self.path, self.ReferencedConfiguration = str(path), configuration
        self.children, self.state = children, state
        self.model, self.IsSpeedPak = object(), False

    def GetSuppression(self):
        return self.state

    def GetPathName(self):
        return self.path

    def GetChildren(self):
        return self.children

    def GetModelDoc2(self):
        return self.model


class FakeDocument:
    # Like pywin32 CDispatch: calling a wrapper invokes a COM default member.
    _oleobj_ = object()
    document_type = 1

    def __call__(self):
        raise AssertionError('COM document default member must not be invoked')

    def GetType(self):
        return self.document_type

    def GetTitle(self):
        return Path(self.path).name

    def GetPathName(self):
        return self.path

    def GetSaveFlag(self):
        return getattr(self, 'dirty', False)

    def IsOpenedReadOnly(self):
        return getattr(self, 'readonly', False)


class FakePart(FakeDocument):
    def __init__(self, path, sheet=True, bodies=1):
        self.path = str(path)
        self.ConfigurationManager = SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name='Default'))
        self.bodies = [SimpleNamespace(IsSheetMetal=lambda: sheet) for _ in range(bodies)]
        self.calls = []
        self.fail = set()
        self.invalid = set()
        self.on_export = None
        self.Visible = True
        self.feature = FakeFeature()

    def GetBodies2(self, kind, visible_only):
        assert (kind, visible_only) == (0, False)
        return self.bodies

    def FirstFeature(self):
        return self.feature

    def ExportToDWG2(self, path, model_path, action, single, alignment, flip_x, flip_y, options, views):
        self.calls.append((path, model_path, action, single, alignment, flip_x, flip_y, options, views))
        kind = Path(path).suffix
        if self.on_export:
            self.on_export(Path(path))
        if kind in self.fail:
            return False
        Path(path).write_bytes(b'invalid output content' if kind in self.invalid else DXF if kind == '.dxf' else DWG)
        return True


class FakeAssembly(FakePart):
    document_type = 2

    def __init__(self, path, children=()):
        super().__init__(path)
        self.root = FakeComponent(path, children=children)
        self.resolve_status = 0
        self.ConfigurationManager = SimpleNamespace(ActiveConfiguration=SimpleNamespace(
            Name='Assembly-Default', GetRootComponent3=self.get_root))

    def get_root(self, resolve):
        assert resolve is True
        return self.root

    def ResolveAllLightWeightComponents(self, warn):
        assert warn is True
        return self.resolve_status


class FakeApp:
    def __init__(self, model, existing=True, previous=None):
        self.model, self.existing = model, existing
        self.ActiveDoc = previous if previous is not None else model if existing else None
        self.closed, self.activated = [], []
        self.open_count = 0
        self.previous = previous
        self.open_error = 0
        self.activate_error = 0

    def GetOpenDocumentByName(self, path):
        return self.model if self.existing else None

    def GetDocuments(self):
        models = list(self.models.values()) if hasattr(self, 'models') else [self.model]
        return [*models, *([self.previous] if self.previous is not None else [])]

    def OpenDoc6(self, path, kind, options, configuration, errors, warnings):
        assert (kind, options, configuration) == (1, 1, '')
        self.open_count += 1
        errors.value = self.open_error
        self.ActiveDoc = self.model
        return self.model

    def CloseDoc(self, title):
        self.closed.append(title)

    def ActivateDoc3(self, title, use_preferences, rebuild, errors):
        assert (use_preferences, rebuild) == (False, 1)
        self.activated.append(title)
        errors.value = self.activate_error
        self.ActiveDoc = self.model if title in (self.model.GetTitle(), self.model.GetPathName()) else self.previous
        return self.ActiveDoc


class FakeMultiPartApp(FakeApp):
    def __init__(self, models, assembly):
        super().__init__(models[0], previous=assembly)
        self.models = {model.path: model for model in models}

    def GetOpenDocumentByName(self, path):
        return self.models.get(str(path))

    def ActivateDoc3(self, name, use_preferences, rebuild, errors):
        assert (use_preferences, rebuild) == (False, 1)
        self.activated.append(name)
        errors.value = self.activate_error
        self.ActiveDoc = self.models.get(name, self.previous)
        return self.ActiveDoc


class FakePdfData:
    def __init__(self):
        self.sheets, self.ok = None, True
        self.ViewPdfAfterSaving = True
        self.ExportAs3D = True

    def SetSheets(self, scope, sheets):
        assert scope in (1, 3) and sheets.kind == 12
        self.scope = scope
        self.sheets = sheets.value
        return self.ok


class FakeDrawing(FakeDocument):
    document_type = 3

    def __init__(self, path, sheets=('Sheet1', 'Sayfa 2')):
        self.path, self.sheets = str(path), sheets
        self.Extension = SimpleNamespace(SaveAs=self.save_as)
        self.calls = []
        self.content = PDF
        self.save_error, self.save_warning = 0, 0
        self.save_ok = True
        self.on_save = None
        self.app = None

    def GetSheetNames(self):
        return self.sheets

    def save_as(self, path, version, options, data, errors, warnings):
        assert self.app.ActiveDoc is self, 'SaveAs requires the drawing to be active'
        assert (version, options) == (0, 1)
        self.calls.append((path, data))
        errors.value, warnings.value = self.save_error, self.save_warning
        if self.on_save:
            self.on_save(Path(path))
        if self.content is not None:
            Path(path).write_bytes(self.content)
        return self.save_ok


class FakePdfApp(FakeMultiPartApp):
    def __init__(self, models, opened=None, previous=None):
        super().__init__(models, previous)
        for model in models:
            model.app = self
        self.opened = set(self.models if opened is None else opened)
        self.data = FakePdfData()
        self.open_calls = []
        self.open_error, self.open_warning, self.activate_error = 0, 0, 0

    def GetOpenDocumentByName(self, path):
        return self.models[path] if path in self.opened else None

    def OpenDoc6(self, path, kind, options, configuration, errors, warnings):
        assert (kind, options, configuration) == (3, 1, '')
        self.open_calls.append(path)
        errors.value, warnings.value = self.open_error, self.open_warning
        self.ActiveDoc = self.models[path]
        return self.ActiveDoc

    def GetExportFileData(self, kind):
        assert kind == 1
        return self.data


class Definition:
    def __init__(self, feature):
        self.feature=feature
        self.data=deepcopy(feature.model.states[feature.model.config])
        self.Thickness, self.BendRadius=self.data['thickness'],self.data['radius']
        self.UseMaterialSheetMetalParameters=feature.model.material_link
        self.allowance=SimpleNamespace(Type=self.data['type'], KFactor=self.data['k'],
                                      BendAllowance=self.data['ba'], BendDeduction=self.data['bd'],
                                      BendTableFile='')

    def GetCustomBendAllowance(self): return self.allowance
    def SetCustomBendAllowance(self, value): self.allowance=value
    def AccessSelections(self, model, component):
        assert model is self.feature.model and component is None
        self.feature.access_count+=1
        return not model.access_fail
    def ReleaseSelectionAccess(self): self.feature.release_count+=1
    def GetUseGaugeTable(self, used, filename):
        used.value=self.feature.model.gauge
        return 0


class SheetFeature(FakeFeature):
    def __init__(self, model):
        super().__init__()
        self.model=model
        self.access_count=self.release_count=self.modify_count=0
    def GetDefinition(self): return Definition(self)
    def GetErrorCode(self): return 0
    def ModifyDefinition(self, definition, model, component):
        assert model is self.model and component is None
        self.modify_count+=1
        if model.modify_fail:
            model.modify_fail=False
            return False
        data=dict(thickness=definition.Thickness, radius=definition.BendRadius,
                  type=definition.allowance.Type,k=definition.allowance.KFactor,
                  ba=definition.allowance.BendAllowance,bd=definition.allowance.BendDeduction)
        if model.readback_fail:
            data['radius']+=.001
            model.readback_fail=False
        model.states[model.config]=data
        if model.propagate:
            for key in model.states: model.states[key]=deepcopy(data)
        return True


class SheetPart(FakePart):
    def __init__(self,path='/work/sheet.sldprt', configurations=('Default',)):
        super().__init__(path)
        initial=dict(thickness=.002,radius=.002,type=2,k=.4,ba=.004,bd=.003)
        self.states={c:deepcopy(initial) for c in configurations}
        self.config=configurations[0]
        self.ConfigurationManager.ActiveConfiguration.Name=self.config
        self.feature=SheetFeature(self)
        # Documented null template/folder denotes a legacy sheet-metal part.
        self.Extension=SimpleNamespace(GetTemplateSheetMetal=lambda: None)
        self.FeatureManager=SimpleNamespace(GetSheetMetalFolder=lambda: None)
        self.gauge=self.material_link=self.access_fail=self.modify_fail=False
        self.rebuild_fail=self.readback_fail=self.propagate=self.dirty=self.save_fail=False
        self.save_count=0
    def GetConfigurationNames(self): return tuple(self.states)
    def ShowConfiguration2(self,config):
        if config not in self.states: return False
        self.config=config
        self.ConfigurationManager.ActiveConfiguration.Name=config
        return True
    def EditRebuild3(self):
        failed=self.rebuild_fail
        self.rebuild_fail=False
        return not failed
    def GetSaveFlag(self): return self.dirty
    def Save3(self,options,errors,warnings):
        assert options==1
        self.save_count+=1
        errors.value=1 if self.save_fail else 0
        return not self.save_fail


# Deliberately retain the different flag values used by the original tests.
COM_FLAGS = {
    'dxf': dict(VT_BYREF=1, VT_I4=2, VT_EMPTY=0),
    'pdf': dict(VT_BYREF=1, VT_I4=2, VT_ARRAY=4, VT_BSTR=8, VT_DISPATCH=9),
    'kr': dict(VT_BYREF=16, VT_I4=3, VT_BOOL=11, VT_BSTR=8, VT_EMPTY=0, VT_DISPATCH=9),
}


def com_stubs(profile, *, dynamic=False):
    com = SimpleNamespace(**COM_FLAGS[profile], CoInitialize=Mock(), CoUninitialize=Mock())
    client = SimpleNamespace(VARIANT=Variant)
    if dynamic:
        def dumb_dispatch(obj):
            # Native CDispatch supports method metadata registration.
            if not hasattr(obj, '_FlagAsMethod'):
                obj._FlagAsMethod = Mock()
            return obj
        client.dynamic = SimpleNamespace(DumbDispatch=Mock(side_effect=dumb_dispatch))
    return com, client


def install_com(testcase, module, profile, *, dynamic=False):
    com, client = com_stubs(profile, dynamic=dynamic)
    testcase.enterContext(patch.multiple(module, pythoncom=com,
                                        win32com=SimpleNamespace(client=client)))
    return com, client


@contextmanager
def solidworks_session(module, app, profile):
    com, client = com_stubs(profile)
    with patch.multiple(module, pythoncom=com, win32com=SimpleNamespace(client=client)), \
            patch.object(module, 'connect_to_solidworks', return_value=app):
        yield com
