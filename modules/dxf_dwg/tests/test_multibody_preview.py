"""The actual preview adapter and native-export path, with a structural COM double."""
from pathlib import Path
from modules.dxf_dwg.preview import solidworks as sw
from modules.dxf_dwg.preview.models import Request,MeshCache
from modules.dxf_dwg.sheetmetal import scan_inventory
from .sheet_fakes import environment,part


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
