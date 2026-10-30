"""Structural SW doubles; written geometry is synthetic, not a CAD kernel."""
from collections import Counter
from pathlib import Path
from types import SimpleNamespace as NS
import ezdxf
from modules.cad_converter import api
from modules.cad_converter.tests.fakes import App, C
from modules.profile_cutting.tests.fakes import Properties
from modules.dxf_dwg import exporter
from modules.dxf_dwg.sheetmetal import Session


class Feature:
    def __init__(self,name,kind,body=None,thickness=2,properties=None):
        self.Name,self.kind,self.body,self.thickness = name,kind,body,thickness
        self.ref=('feature:'+name).encode();self.next=None;self.child=None
        self.CustomPropertyManager=Properties(properties or {})
    def GetTypeName2(self):return self.kind
    def GetNextFeature(self):return self.next
    GetNextSubFeature=GetNextFeature
    def GetFirstSubFeature(self):return self.child
    def IsSuppressed2(self,*args):return (False,)
    def GetDefinition(self):return NS(Thickness=self.thickness/1000,FixedFace2=NS(GetBody=lambda:self.body))
    def GetSpecificFeature2(self):return NS(GetBodies=lambda:(self.body,))
    def Select2(self,append,mark):
        assert not append and mark==-1
        self.body.model.selection=[self];return True


class Selection:
    def __init__(self,model):self.model=model;self.saved=[]
    def SuspendSelectionList(self):self.saved.append(list(self.model.selection));return len(self.saved)
    def ResumeSelectionList2(self,append):
        assert not append
        self.model.selection=self.saved.pop()


class Body:
    def __init__(self,name,model,sheet=True,width=10,thickness=2):
        self.Name,self.model,self.sheet,self.width,self.thickness=name,model,sheet,width,thickness
        self.ref=('body:'+name).encode();self.features=[]
    def IsSheetMetal(self):return self.sheet
    def GetFeatures(self):return self.features
    def GetMaterialPropertyName2(self,conf,db):return 'S235JR'
    def GetFaces(self):return (NS(GetTessTriangles=lambda *args:(0,0,0,self.width/1000,0,0,0,.02,0)),)


def part(app,path,configs=None,*,sheet=True,count=1,opened=True):
    path=Path(path).resolve()
    configs=configs or {'Default':[(f'Body-{i}',i+1,10*(i+1)) for i in range(count)]}
    model=app.add(path,tuple(configs),opened=opened)
    model.selection=['user selection'];model.SelectionManager=Selection(model)
    model.GetUpdateStamp=lambda:10;model.GetSaveFlag=lambda:True
    model.GetUnits=lambda:(0,);model.Visible=True
    model.by_config={};model.features_by_config={};model.export_calls=[]
    for configuration,descriptions in configs.items():
        bodies=[];features=[]
        for name,thickness,width in descriptions:
            body=Body(configuration+'-'+name,model,sheet,width,thickness);bodies.append(body)
            if sheet:
                base=Feature('Sheet-'+body.Name,'SheetMetal',body,thickness);body.features=[base]
                folder=Feature('Cut-'+body.Name,'CutListFolder',body,properties={'MATERIAL':'S235JR','PART NUMBER':path.stem})
                features.extend((base,folder,Feature('Flat-'+body.Name,'FlatPattern',body)))
        for a,b in zip(features,features[1:]):a.next=b
        model.by_config[configuration]=bodies;model.features_by_config[configuration]=features
    def bodies(kind,visible):
        assert kind==0 and visible is False
        return tuple(model.by_config[model.active])
    model.GetBodies2=bodies;model.FirstFeature=lambda:next(iter(model.features_by_config[model.active]),None)
    model.FeatureByName=lambda name:next((f for f in model.features_by_config[model.active] if f.Name==name),None)
    model.Extension.GetPersistReference3=lambda obj:obj.ref
    model.ClearSelection2=lambda all:model.selection.clear()
    def export(path,source,action,single,alignment,flipx,flipy,options,views):
        assert app.ActiveDoc is model and len(model.selection)==1
        flat=model.selection[0]
        assert isinstance(flat,Feature) and flat.kind=='FlatPattern'
        assert flat.body in model.by_config[model.active]
        assert source==model.path and action==1 and single is True
        assert not flipx and not flipy and options in (1,5)
        model.export_calls.append((model.active,flat.body.Name,options))
        if getattr(model,'fail_export',False):return False
        path=Path(path)
        if path.suffix.lower()=='.dwg':path.write_bytes(b'AC1032'+b'\0'*40)
        else:
            doc=ezdxf.new();doc.units=4
            doc.modelspace().add_lwpolyline([(0,0),(flat.body.width,0),(flat.body.width,20),(0,20)],close=True)
            if options & 4:
                doc.layers.new('BEND');doc.modelspace().add_line((1,0),(1,20),dxfattribs={'layer':'BEND'})
            doc.saveas(path)
        if getattr(model,'after_export',None):model.after_export()
        return True
    model.ExportToDWG2=export;return model


def component(model=None,*,name='Part-1',configuration='Default',state=2,children=(),path='',virtual=False):
    return NS(Name2=name,ReferencedConfiguration=configuration,IsVirtual=virtual,IsSpeedPak=False,
              GetSuppression2=lambda:state,GetPathName=lambda:path or (model.path if model else ''),
              GetModelDoc2=lambda:model,GetChildren=lambda:tuple(children))


def assembly(app,path,children=(),configurations=('Default',)):
    path=Path(path).resolve()
    model=app.add(path,configurations,opened=True)
    class Assembly(type(model)):
        @property
        def ConfigurationManager(self):
            return NS(ActiveConfiguration=NS(Name=self.active,IsSpeedPak=False,
                       GetRootComponent3=lambda resolve:component(self,name='Root',children=children)))
    model.__class__=Assembly;return model


def environment(monkeypatch):
    app=App();calls=Counter()
    monkeypatch.setattr(api,'interface',lambda obj,iid:obj)
    monkeypatch.setattr(api,'out_int',lambda:NS(value=0))
    monkeypatch.setattr(exporter,'_out_integer',lambda:NS(value=0))
    monkeypatch.setattr(exporter,'pythoncom',NS(VT_EMPTY=0))
    monkeypatch.setattr(exporter,'win32com',NS(client=NS(VARIANT=lambda kind,value:NS(value=value))))
    class FakeSession(Session):
        def __enter__(self):
            self.app=app;self.constants=dict(C,swSolidBody=0,swThisConfiguration=1,swObjectSame=1,swCustomInfoGetResult_ResolvedValue=2)
            self.owned={};self.load_warnings={};self.previous=app.ActiveDoc.path if app.ActiveDoc else ''
            self.pythoncom=NS(CoUninitialize=lambda:None);return self
        def describe(self,model,source,configuration,stop=None):
            calls[(source,configuration)]+=1
            return super().describe(model,source,configuration,stop)
    return app,FakeSession,calls
