"""COM-free doubles follow the actual Get6 and BodyFolder contracts."""

from contextlib import contextmanager
from types import SimpleNamespace as NS
from pathlib import Path

from modules.profile_cutting.solidworks import Session
from modules.cad_converter.api import RestoreError

CONSTANTS = dict(swDocPART=1, swDocASSEMBLY=2, swWeldmentCutlist=3,
                 swSheetmetalCutlist=2, swSolidBodyCutList=1, swMM=0,
                 swCustomInfoGetResult_ResolvedValue=2, swComponentSuppressed=0,
                 swComponentLightweight=1, swComponentFullyResolved=2)


class Properties:
    def __init__(self, values): self.values = values
    def GetNames(self): return list(self.values)
    def Get6(self, name, cached, raw, resolved, was, linked):
        assert cached is False
        value = self.values[name]
        raw.value, resolved.value, was.value, linked.value = '$PRP:' + name, str(value), True, True
        return 2


class Body:
    def __init__(self, name, length=1000, *, sheet=False, curved=False):
        self.Name, self.length, self.sheet, self.curved = name, length, sheet, curved
    def IsSheetMetal(self): return self.sheet
    def GetBodyBox(self): raise AssertionError('AABB must never be used as cutting length')
    def GetFaces(self):
        normals = [(0,0,1),(0,0,-1),(1,0,0),(-1,0,0),(0,1,0),(0,-1,0)]
        points = [(0,0,0),(0,0,self.length/1000),(.02,0,0),(-.02,0,0),(0,.02,0),(0,-.02,0)]
        # Inner walls prevent the width/height axes from masquerading as length.
        normals += [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0)]
        points += [(.018,0,0),(-.018,0,0),(0,.018,0),(0,-.018,0)]
        faces = []
        for normal, point in zip(normals, points):
            surface = NS(IsPlane=lambda: True, IsCylinder=lambda: False)
            faces.append(NS(Normal=normal,GetSurface=lambda surface=surface:surface,
                            GetClosestPointOn=lambda *args,point=point:point))
        if self.curved:
            faces.append(NS(GetSurface=lambda:NS(IsPlane=lambda:False,IsCylinder=lambda:False)))
        return faces


class Folder:
    def __init__(self, name='Cut-List-1', bodies=None, properties=None, *, kind=3):
        self.Name = name
        self.bodies = [Body(name+'-body')] if bodies is None else bodies
        self.CustomPropertyManager = Properties(dict(DESCRIPTION='40×40×2', MATERIAL='S235JR',
            LENGTH='1000', QUANTITY=str(len(self.bodies)), Angle1='90', Angle2='90') | (properties or {}))
        self.kind = kind; self.updated = 0; self.automatic = True
        self.next = None
    def GetTypeName2(self): return 'CutListFolder'
    def GetSpecificFeature2(self): return self
    def GetFirstSubFeature(self): return None
    def GetNextFeature(self): return self.next
    def GetNextSubFeature(self): return None
    def GetBodyCount(self): return len(self.bodies)
    def GetBodies(self): return tuple(self.bodies)
    def GetAutomaticUpdate(self): return self.automatic
    def SetAutomaticUpdate(self, *_): raise AssertionError('User setting must not change')
    def SetAutomaticCutList(self, *_): raise AssertionError('User setting must not change')
    def UpdateCutList(self): self.updated += 1; return True
    def GetCutListType(self): return self.kind


class Model:
    def __init__(self, path, folders=(), configs=None, children=()):
        self.path = str(path); self.children = children
        self.configs = configs or {'Default': list(folders)}
        self.ConfigurationManager = NS(ActiveConfiguration=NS(Name=next(iter(self.configs))))
        self.Extension = NS(NeedsRebuild2=False, GetPersistReference3=lambda obj: obj.Name.encode())
        self.switches = []
    def GetPathName(self): return self.path
    def GetTitle(self): return Path(self.path).name
    def GetType(self): return 2 if self.children else 1
    def GetUnits(self): return [0]
    def GetConfigurationNames(self): return list(self.configs)
    def ShowConfiguration2(self, name):
        if name not in self.configs: return False
        self.switches.append(name); self.ConfigurationManager.ActiveConfiguration.Name=name; return True
    def FirstFeature(self):
        folders = self.configs[self.ConfigurationManager.ActiveConfiguration.Name]
        for i, folder in enumerate(folders): folder.next = folders[i+1] if i+1<len(folders) else None
        return folders[0] if folders else None
    def GetComponents(self, top_only):
        assert top_only is True
        return self.children
    def Save(self): raise AssertionError('Source must not be saved')


def component(name, path, configuration='Default', state=2):
    return NS(Name2=name, GetPathName=lambda:str(path), ReferencedConfiguration=configuration,
              GetSuppression2=lambda:state, IsVirtual=False)


class FakeSession(Session):
    def __init__(self, models, root):
        self.models={m.path:m for m in models}; self.root=root; self.reads=[]; self.closed=False
    def __enter__(self): self.constants=CONSTANTS; return self
    def __exit__(self,*args): self.closed=True
    def document(self,path=None):
        self.reads.append(str(path))
        return self.root if path is None else self.models[str(path)]
    def activate(self,model): pass
    def is_assembly(self,model): return model.GetType()==2


def factory(models,root):
    session=FakeSession(models,root)
    return session,lambda:session
