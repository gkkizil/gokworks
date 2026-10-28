from dataclasses import replace
from math import pi
import pytest
from modules.gear_calculator.families.models import MechanismSpecification
from modules.gear_calculator.families.geometry import sections,section_polygon
from modules.gear_calculator.families.cad import solid,placed
from modules.gear_calculator.families.export import export_cad
from modules.gear_calculator.cad import shape_stats
from modules.gear_calculator import service


def small(kind):
    return MechanismSpecification(kind=kind,module_mm=1,teeth1=24 if kind in ('internal','planetary') else 16,
        teeth2=72 if kind=='internal' else 24 if kind=='planetary' else 12 if kind=='cycloidal' else 32,
        pressure_angle_deg=20 if kind in ('internal','planetary','cycloidal') else 25,
        width_mm=4,bore1_mm=2,bore2_mm=2,roller_radius_mm=.75,eccentricity_mm=.25)


@pytest.mark.parametrize('kind,solids',[('rack',2),('helical',2),('herringbone',2),('internal',2),('planetary',5),('cycloidal',13)])
@pytest.mark.timeout(120)
def test_each_available_mechanism_is_real_step_and_closed_layered_dxf(tmp_path,kind,solids):
    s=small(kind)
    result=export_cad(s,tmp_path/(kind+'.step'))
    assert result['solids']==solids and result['units']=='mm' and result['volume_mm3']>0
    assert result['bounds_mm'][2]==pytest.approx(0,abs=1e-6)
    assert result['bounds_mm'][5]==pytest.approx(4,abs=1e-6)
    d=export_cad(s,tmp_path/(kind+'.dxf'))
    assert d['format']=='DXF' and d['units']=='mm'
    import ezdxf
    read=ezdxf.readfile(tmp_path/(kind+'.dxf'))
    assert len(read.modelspace().query('LWPOLYLINE[layer=="GEAR_PROFILE"]'))>0
    assert len(read.modelspace().query('POINT[layer=="CONSTRUCTION"]'))>0


@pytest.mark.parametrize('kind',['helical','herringbone'])
@pytest.mark.timeout(120)
def test_helix_volume_preserves_section_area_and_bore_is_through(kind):
    s=small(kind);sec=sections(s)[0]
    model=solid(s,sec,0);stats=shape_stats(model)
    area=section_polygon(sec,.00001).area
    # True twist extrusion has constant section area. The smooth loft is a
    # bounded-section approximation, not a mesh relabelled as STEP.
    assert stats['volume_mm3']==pytest.approx(area*s.width_mm,rel=2e-5)
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_OUT
    for z in (.1,2,3.9):assert BRepClass3d_SolidClassifier(model,gp_Pnt(0,0,z),1e-7).State()==TopAbs_OUT


def test_family_headless_worker_uses_latest_parameters_and_preserves_existing_file(tmp_path):
    s=replace(small('rack'),module_mm=1.5)
    p=tmp_path/'rack.step';p.write_text('existing',encoding='utf-8')
    with pytest.raises(FileExistsError):service.execute(s,'step',path=p)
    assert p.read_text()=='existing'
    info=service.execute(s,'step',path=p,overwrite=True)
    assert info['solids']==2 and info['bounds_mm'][3]>30
    with pytest.raises(RuntimeError):service.execute(small('hypoid'),'step',path=p,overwrite=True)
    assert p.read_bytes().startswith(b'ISO-10303-21;')


def test_single_ring_and_single_cycloid_disk_are_centered_in_own_coordinates(tmp_path):
    ring=export_cad(small('internal'),tmp_path/'ring.step',target='wheel')
    assert ring['solids']==1
    assert ring['bounds_mm'][0]+ring['bounds_mm'][3]==pytest.approx(0,abs=1e-6)
    disk=export_cad(small('cycloidal'),tmp_path/'disk.step',target='pinion')
    assert disk['solids']==1
