from dataclasses import replace
from math import pi
from pathlib import Path
from threading import Event
import time
import sys
import subprocess
import json

import ezdxf
import pytest
from shapely.geometry import Polygon

from modules.gear_calculator import GearSpecification,GearPairSpecification
from modules.gear_calculator.export import export_cad
from modules.gear_calculator.geometry import polygon
from modules.gear_calculator import cad,service
from modules.gear_calculator.serialization import to_dict


@pytest.mark.parametrize('target,count',[('pinion',1),('wheel',1),('pair',2)])
def test_dxf_closed_contours_bores_millimetres_layers_and_pair_placement(tmp_path,target,count):
    s=GearPairSpecification();path=tmp_path/f'{target}.dxf'
    result=export_cad(s,path,target=target)
    d=ezdxf.readfile(path);m=d.modelspace()
    assert d.units==4 and not d.audit().has_errors
    profiles=list(m.query('LWPOLYLINE[layer=="GEAR_PROFILE"]'))
    assert len(profiles)==count and all(x.closed for x in profiles)
    for p in profiles:assert Polygon([(v[0],v[1]) for v in p.get_points()]).is_valid
    assert len(m.query('CIRCLE[layer=="BORE"]'))==count
    assert len(m.query('CIRCLE[layer=="PITCH_CIRCLE"]'))==count
    assert len(m.query('CIRCLE[layer=="BASE_CIRCLE"]'))==count
    centers=[tuple(x.dxf.location)[:2] for x in m.query('POINT[layer=="CONSTRUCTION"]')]
    assert centers[0]==pytest.approx((0,0))
    if target=='pair':assert centers[1]==pytest.approx((60,0))
    assert result['maximum_overlap_mm2']<=.00008


def test_dxf_helpers_can_be_omitted_without_removing_bore_or_profile(tmp_path):
    path=tmp_path/'gear.dxf';export_cad(GearPairSpecification(),path,construction=False)
    m=ezdxf.readfile(path).modelspace()
    assert not m.query('CIRCLE[layer=="PITCH_CIRCLE"]')
    assert len(m.query('LWPOLYLINE'))==2 and len(m.query('CIRCLE[layer=="BORE"]'))==2


@pytest.mark.parametrize('target,count',[('pinion',1),('wheel',1),('pair',2)])
def test_step_has_true_valid_solids_with_correct_volume_bores_width_and_coordinates(tmp_path,target,count):
    s=GearPairSpecification();path=tmp_path/f'{target}.step'
    result=export_cad(s,path,target=target)
    shape=cad.read_step(path);stats=cad.shape_stats(shape)
    assert stats['solids']==count and stats['volume_mm3']>0
    gears=[s.pinion] if target=='pinion' else [s.wheel] if target=='wheel' else [s.pinion,s.wheel]
    expected=sum((polygon(g,.00002).area-pi*(g.bore_mm/2)**2)*g.face_width_mm for g in gears)
    assert stats['volume_mm3']==pytest.approx(expected,rel=3e-5)
    assert stats['bounds_mm'][2]==pytest.approx(0,abs=1e-6)
    assert stats['bounds_mm'][5]==pytest.approx(15,abs=1e-6)
    assert stats['bounds_mm'][0]==pytest.approx(-22 if target!='wheel' else -42,abs=1e-5)
    if target=='pair':assert stats['bounds_mm'][3]>100
    # STEP must carry analytical B-Rep surfaces/curves, never faceted STL renamed.
    text=path.read_text()
    assert 'MANIFOLD_SOLID_BREP' in text and 'B_SPLINE_CURVE' in text
    assert 'FACETED_BREP' not in text and 'SI_UNIT(.MILLI.,.METRE.)' in text
    assert result['solids']==count


def test_bore_is_a_real_void_and_curve_surface_is_not_mesh_faceting():
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_OUT,TopAbs_IN
    from OCP.gp import gp_Pnt
    s=GearSpecification();shape=cad.build_gear(s)
    assert BRepClass3d_SolidClassifier(shape,gp_Pnt(0,0,7),1e-6).State()==TopAbs_OUT
    assert BRepClass3d_SolidClassifier(shape,gp_Pnt(10,0,7),1e-6).State()==TopAbs_IN
    triangles=cad.triangulate([shape])
    assert len(triangles)>0 and len(triangles)%9==0
    assert min(triangles[2::3])==pytest.approx(0) and max(triangles[2::3])==pytest.approx(15)


def test_failed_export_and_default_no_clobber_preserve_existing_destination(tmp_path):
    path=tmp_path/'existing.step';path.write_text('user data')
    with pytest.raises(FileExistsError):export_cad(GearPairSpecification(),path)
    bad=GearPairSpecification(pinion=GearSpecification(teeth=10,bore_mm=0))
    with pytest.raises(ValueError):export_cad(bad,path,overwrite=True)
    assert path.read_text()=='user data'
    assert not list(tmp_path.glob('.gokworks-gear-*'))
    with pytest.raises(ValueError):cad.build_gear(bad.pinion)


def test_actual_headless_worker_export_mesh_and_cancel_timeout(tmp_path):
    s=GearPairSpecification()
    result=service.execute(s,'dxf',target='wheel',path=tmp_path/'çark.dxf')
    assert Path(result['path']).is_file()
    mesh=service.execute(s,'mesh',target='pinion')['mesh']
    assert mesh.triangles>0 and mesh.bounds[5]-mesh.bounds[2]==pytest.approx(15)
    stop=Event();stop.set()
    with pytest.raises(service.OperationCancelled):service.execute(s,'step',path=tmp_path/'cancel.step',stop=stop)
    with pytest.raises(TimeoutError):service.execute(s,'step',path=tmp_path/'timeout.step',timeout=.000001)
    assert not (tmp_path/'cancel.step').exists() and not (tmp_path/'timeout.step').exists()


def test_worker_entry_point_does_not_load_qt_or_require_solidworks(tmp_path):
    # Check the real CLI route, then its imported module set in a clean process.
    code="""
import sys,json
from pathlib import Path
from modules.gear_calculator.worker import run_worker
from modules.gear_calculator.serialization import to_dict
from modules.gear_calculator import GearPairSpecification
p=Path(sys.argv[1]);p.write_text(json.dumps(dict(specification=to_dict(GearPairSpecification()),mode='check',target='pair',construction=True)))
assert run_worker(p)==0
assert not any(x.startswith(('PySide6','pythoncom','win32com')) for x in sys.modules)
"""
    p=subprocess.run([sys.executable,'-c',code,str(tmp_path/'request.json')],cwd=service.ROOT,capture_output=True,text=True,timeout=20)
    assert p.returncode==0,p.stdout+p.stderr
