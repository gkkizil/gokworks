"""The actual preview adapter and native-export path, with a structural COM double."""
from pathlib import Path
import pytest
from modules.dxf_dwg.preview import solidworks as sw
from modules.dxf_dwg.preview.models import Request,MeshCache
from modules.dxf_dwg.sheetmetal import scan_inventory
from .sheet_fakes import environment,part
from modules.profile_cutting.tests.fakes import Properties


def test_real_preview_path_selects_only_the_second_body_and_its_thickness(tmp_path,monkeypatch):
    app,Base,_=environment(monkeypatch)
    p=part(app,tmp_path/'Multi.SLDPRT',count=2);p.GetBendState=lambda:3;app.ActiveDoc=p
    with Base() as session:rows,_=scan_inventory(session)
    monkeypatch.setattr(sw,'interface',lambda obj,iid:obj)
    class Session(sw.Session):
        def __enter__(self):
            Base.__enter__(self)
            self.constants.update(swSMBendStateNone=0,swSMBendStateSharps=1,swSMBendStateFlattened=2,swSMBendStateFolded=3)
            return self
    row=rows[1];before=Path(p.path).read_bytes()
    result=sw.capture(Request(row['source'],row['configuration'],row['body_ref'],quantity=4,
                             flat_ref=row['flat_ref'],body_name=row['body_name']),MeshCache(),session_factory=Session)
    assert result.flat and result.flat.bounds==(0,0,20,20)
    assert result.mesh.triangles==1 and p.export_calls==[('Default','Default-Body-1',1)]
    assert dict(result.info)['Sac kalınlığı']=='2 mm' and dict(result.info)['Adet']=='4'
    assert p.selection==['user selection'] and app.ActiveDoc is p and not app.saves
    assert Path(p.path).read_bytes()==before


@pytest.mark.parametrize('cut_material,body_material,document_material,part_material,expected',[
    ('S275JR','S355JR','S235JR','S460','S275JR'),
    ('','S355JR','S235JR','S460','S355JR'),
    ('','','S235JR','S460','S235JR'),
    ('','','','S460','S460'),
    ('','','','',''),
])
def test_scan_and_real_preview_agree_on_body_material_scope(tmp_path,monkeypatch,
        cut_material,body_material,document_material,part_material,expected):
    app,Base,_=environment(monkeypatch)
    p=part(app,tmp_path/'Panel.SLDPRT');p.GetBendState=lambda:3;app.ActiveDoc=p
    props=p.features_by_config['Default'][1].CustomPropertyManager.values
    props.pop('MATERIAL')
    if cut_material:props['Malzeme']=cut_material
    # CustomPropertyManager(scope) is a parameterized COM PROPERTYGET, not
    # a Python method; exercise the same invocation contract as SolidWorks.
    extension=p.Extension
    class Extension:
        def GetIDsOfNames(self,lcid,name):return name
        def Invoke(self,name,lcid,flags,result,*args):
            if name=='CustomPropertyManager':
                assert flags==2 and args[0] in ('','Default')
                return Properties({'MATERIAL':document_material} if document_material else {})
            value=getattr(extension,name)
            return value(*args) if flags==1 else value
    p.Extension=Extension()
    p.by_config['Default'][0].GetMaterialPropertyName2=lambda *args:body_material
    p.GetMaterialPropertyName2=lambda *args:part_material
    with Base() as session:rows,_=scan_inventory(session)
    monkeypatch.setattr(sw,'interface',lambda obj,iid:obj)
    class Session(sw.Session):
        def __enter__(self):
            Base.__enter__(self)
            self.constants.update(swSMBendStateNone=0,swSMBendStateSharps=1,swSMBendStateFlattened=2,swSMBendStateFolded=3)
            return self
    row=rows[0]
    result=sw.capture_geometry(Request(row['source'],row['configuration'],row['body_ref'],
                                      flat_ref=row['flat_ref']),MeshCache(),session_factory=Session)
    assert row['exportable'] and row['material']==expected
    assert dict(result.info)['Malzeme']==(expected or 'Okunamadı')
    assert not app.saves and p.selection==['user selection']
