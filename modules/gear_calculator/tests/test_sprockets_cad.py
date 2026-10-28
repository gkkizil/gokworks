from dataclasses import replace
from math import pi
from threading import Event,Timer
import subprocess,sys
import pytest
import ezdxf
from ezdxf.path import make_path
from shapely.geometry import Polygon
from modules.gear_calculator.sprockets import SprocketPairSpecification
from modules.gear_calculator.sprockets.calculation import calculate
from modules.gear_calculator.sprockets.geometry import polygon
from modules.gear_calculator.sprockets.export import export_cad
from modules.gear_calculator.sprockets.cad import build
from modules.gear_calculator import cad,service


@pytest.mark.parametrize('target,count',[('pinion',1),('wheel',1),('pair',2)])
def test_exact_arc_dxf_closed_contours_bores_and_auxiliary_layers(tmp_path,target,count):
    s=SprocketPairSpecification();path=tmp_path/(target+'.dxf');info=export_cad(s,path,target=target)
    doc=ezdxf.readfile(path);m=doc.modelspace();contours=list(m.query('LWPOLYLINE[layer=="SPROCKET_PROFILE"]'))
    assert info['units']=='mm' and not info['chain_included'] and doc.units==4 and not doc.audit().has_errors
    assert len(contours)==count and all(p.closed for p in contours)
    assert all(any(v[4]<0 for v in p.get_points()) and any(v[4]>0 for v in p.get_points()) for p in contours)
    assert all(Polygon([(v.x,v.y) for v in make_path(p).flattening(.0005)]).is_valid for p in contours)
    assert len(m.query('CIRCLE[layer=="BORE"]'))==count
    assert len(m.query('CIRCLE[layer=="PITCH_CIRCLE"]'))==count
    assert len(m.query('POINT[layer=="ROLLER_CENTERS"]'))==(20 if target=='pinion' else 40 if target=='wheel' else 60)
    centers=list(m.query('POINT[layer=="CONSTRUCTION"]'))
    assert tuple(centers[0].dxf.location)==pytest.approx((0,0,0))
    if target=='pair':assert centers[1].dxf.location.x==pytest.approx(calculate(s).corrected_center_mm)


def test_dxf_helpers_are_separate_and_can_be_omitted(tmp_path):
    path=tmp_path/'plain.dxf';export_cad(SprocketPairSpecification(),path,construction=False)
    m=ezdxf.readfile(path).modelspace()
    assert not m.query('CIRCLE[layer=="PITCH_CIRCLE"]') and not m.query('POINT[layer=="ROLLER_CENTERS"]')
    assert len(m.query('LWPOLYLINE[layer=="SPROCKET_PROFILE"]'))==2 and len(m.query('CIRCLE[layer=="BORE"]'))==2


@pytest.mark.parametrize('target,count',[('pinion',1),('wheel',1),('pair',2)])
def test_real_step_roundtrip_body_count_volume_and_corrected_center(tmp_path,target,count):
    s=SprocketPairSpecification();path=tmp_path/(target+'.step');info=export_cad(s,path,target=target)
    stats=cad.shape_stats(cad.read_step(path))
    wheels=[s.driver] if target=='pinion' else [s.driven] if target=='wheel' else [s.driver,s.driven]
    assert stats['solids']==count and not info['chain_included']
    assert stats['volume_mm3']==pytest.approx(sum(polygon(w,.00005).area*w.width_mm for w in wheels),rel=2e-5)
    assert stats['bounds_mm'][2]==pytest.approx(0,abs=1e-6) and stats['bounds_mm'][5]==pytest.approx(7,abs=1e-6)
    if target=='pair':assert stats['bounds_mm'][3]>calculate(s).corrected_center_mm+80
    else:assert stats['bounds_mm'][0]+stats['bounds_mm'][3]==pytest.approx(0,abs=1e-6)
    text=path.read_text()
    assert 'MANIFOLD_SOLID_BREP' in text and 'CIRCLE' in text and 'FACETED_BREP' not in text
    assert 'SI_UNIT(.MILLI.,.METRE.)' in text


def test_optional_hub_is_one_fused_solid_and_bore_goes_through_plate_and_hub():
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN,TopAbs_OUT
    w=replace(SprocketPairSpecification().driver,hub_diameter_mm=30,hub_length_mm=20)
    shape=build(w);stats=cad.shape_stats(shape)
    assert stats['solids']==1 and stats['bounds_mm'][5]==pytest.approx(20,abs=1e-6)
    expected=polygon(w,.00005).area*w.width_mm+pi*((w.hub_diameter_mm/2)**2-(w.bore_mm/2)**2)*(20-w.width_mm)
    assert stats['volume_mm3']==pytest.approx(expected,rel=2e-5)
    for z in (1,6,10,19):assert BRepClass3d_SolidClassifier(shape,gp_Pnt(0,0,z),1e-7).State()==TopAbs_OUT
    assert BRepClass3d_SolidClassifier(shape,gp_Pnt(10,0,15),1e-7).State()==TopAbs_IN
    assert BRepClass3d_SolidClassifier(shape,gp_Pnt(25,0,15),1e-7).State()==TopAbs_OUT


def test_existing_file_is_preserved_without_confirmation_or_on_invalid_specification(tmp_path):
    s=SprocketPairSpecification();path=tmp_path/'pair.step';path.write_bytes(b'original user data')
    with pytest.raises(FileExistsError):service.execute(s,'step',path=path)
    invalid=replace(s,driver=replace(s.driver,profile_reference='unverified'))
    with pytest.raises(ValueError):service.execute(invalid,'step',path=path,overwrite=True)
    assert path.read_bytes()==b'original user data'


def test_worker_atomic_publication_and_resource_limits(tmp_path):
    s=SprocketPairSpecification();path=tmp_path/'pair.step';path.write_bytes(b'original user data')
    stop=Event();stop.set()
    with pytest.raises(service.OperationCancelled):service.execute(s,'step',path=path,overwrite=True,stop=stop)
    with pytest.raises(TimeoutError):service.execute(s,'step',path=path,overwrite=True,timeout=.000001)
    stop.clear();timer=Timer(.03,stop.set);timer.start()
    try:
        with pytest.raises(service.OperationCancelled):service.execute(s,'step',path=path,overwrite=True,stop=stop)
    finally:timer.join()
    assert path.read_bytes()==b'original user data'
    check=service.execute(s,'check');assert check['minimum_roller_clearance_mm']>=0
    mesh=service.execute(s,'mesh')['mesh'];assert mesh.triangles>0 and mesh.bounds[5]-mesh.bounds[2]==pytest.approx(7)
    info=service.execute(s,'step',path=path,overwrite=True);assert info['solids']==2
    assert path.read_bytes().startswith(b'ISO-10303-21;') and not list(tmp_path.glob('.gokworks-*'))


@pytest.mark.parametrize('series',['08B-1','10B-1','12B-1','16B-1'])
def test_each_catalogue_chain_makes_a_real_closed_solid(tmp_path,series):
    from modules.gear_calculator.sprockets import CHAINS,SprocketSpecification
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SHELL
    wheel=SprocketSpecification(chain=CHAINS[series],teeth=20)
    model=build(wheel);shells=TopExp_Explorer(model,TopAbs_SHELL)
    while shells.More():assert shells.Current().Closed();shells.Next()
    s=SprocketPairSpecification(driver=wheel,driven=replace(wheel,teeth=40))
    info=export_cad(s,tmp_path/(series+'.step'),target='pinion')
    assert info['solids']==1 and info['volume_mm3']>0


def test_chain_worker_imports_no_qt_or_com(tmp_path):
    code='''
import sys,json
from pathlib import Path
from modules.gear_calculator.sprockets import SprocketPairSpecification
from modules.gear_calculator.serialization import to_dict
from modules.gear_calculator.worker import run_worker
p=Path(sys.argv[1]);p.write_text(json.dumps(dict(specification=to_dict(SprocketPairSpecification()),mode='check',target='pair',construction=True)))
assert run_worker(p)==0
assert not any(x in sys.modules for x in ('PySide6','pythoncom','win32com'))
'''
    subprocess.run([sys.executable,'-c',code,str(tmp_path/'request.json')],check=True,timeout=20,cwd=service.ROOT)
