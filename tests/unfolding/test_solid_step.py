"""Solid STEP acceptance: independent volume, wall thickness and real openings."""
import math
from dataclasses import replace

import pytest

from core.unfolding import UnfoldService,ExportOptions
from core.unfolding.cad import read_step
from core.unfolding.solid_cad import write_solid_step
from .test_source_models import calculate

pytest.importorskip('OCP')


def inside(shape,point):
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN,TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.gp import gp_Pnt
    solid=TopExp_Explorer(shape,TopAbs_SOLID).Current()
    return BRepClass3d_SolidClassifier(solid,gp_Pnt(*point),1e-6).State()==TopAbs_IN


@pytest.mark.parametrize('reference,ri,ro',[('mid',99.,101.),('inner',100.,102.),('outer',98.,100.)])
def test_cylinder_solid_is_centred_on_the_normalized_midsurface(tmp_path,reference,ri,ro):
    r=calculate('cylinder',thickness=2.,dimension_reference=reference)
    assert r.capabilities['step_solid']
    path=tmp_path/(reference+'.step')
    stats=write_solid_step(r.parts,path,2.);shape,again=read_step(path)
    assert stats==again and stats['solids']==1 and stats['closed'] and stats['free_faces']==0
    assert stats['volume_mm3']==pytest.approx(math.pi*(ro*ro-ri*ri)*300.,rel=1e-9)
    assert stats['bounds_mm']==pytest.approx((-ro,-ro,0.,ro,ro,300.),abs=2e-6)
    assert inside(shape,((ri+ro)/2,0.,150.))
    assert not inside(shape,(0.,0.,150.))
    assert not inside(shape,(ro+1.,0.,150.))


def test_hole_in_the_trunk_remains_a_real_through_hole_in_the_solid(tmp_path):
    r=calculate('pipe-to-pipe-90-trunk',thickness=2.,parameters=dict(Dt=400.,Db=100.,H=800.,Hb=400.,Z=0.))
    path=tmp_path/'trunk-with-hole.step'
    write_solid_step(r.parts,path,2.);shape,stats=read_step(path)
    assert stats['solids']==1 and stats['closed']
    assert not inside(shape,(200.,0.,400.))
    assert inside(shape,(-200.,0.,400.))
    assert not inside(shape,(0.,0.,400.))


def test_angle_cut_solid_volume_uses_adaptive_integration_over_piecewise_linear_trims(tmp_path):
    r=calculate('cylinder-top-angle',thickness=2.)
    stats=write_solid_step(r.parts,tmp_path/'cosine-cut.step',2.)
    # The zero-mean cosine cut preserves pi*(Ro²-Ri²)*center-height.
    assert stats['volume_mm3']==pytest.approx(math.pi*(101**2-99**2)*250,rel=1e-8)
    assert stats['volume_integration_relative_error']<1e-7
    assert stats['faces']<=8  # exact UV segments are grouped, not smoothed away


def test_split_parts_keep_separate_solids_and_total_material_volume(tmp_path):
    r=calculate('cylinder',thickness=2.,model_options={'cut_type':'2_parts'})
    stats=write_solid_step(r.parts,tmp_path/'two-halves.step',2.)
    assert stats['solids']==2==len(r.parts)
    assert stats['volume_mm3']==pytest.approx(math.pi*(101**2-99**2)*300.,rel=1e-8)


def test_duct_has_four_real_plate_solids_and_analytical_material_volume(tmp_path):
    r=calculate('rectangular-duct-straight',thickness=2.)
    stats=write_solid_step(r.parts,tmp_path/'duct.step',2.)
    assert stats['solids']==4
    assert stats['volume_mm3']==pytest.approx(2*(500+250)*700*2.,rel=1e-9)


def test_faceted_prism_has_the_independent_parallel_polygon_wall_volume(tmp_path):
    from core.unfolding.models import Mesh3D
    r=calculate('prism',thickness=2.,parameters={'n':6,'D':200.,'H':300.})
    # Empty display geometry proves that the CAD material facets are the source.
    parts=tuple(replace(p,mesh_3d=Mesh3D((),())) for p in r.parts)
    path=tmp_path/'hexagonal-tube.step';stats=write_solid_step(parts,path,2.)
    a=100*math.cos(math.pi/6)
    expected=6*math.tan(math.pi/6)*((a+1)**2-(a-1)**2)*300
    assert stats['volume_mm3']==pytest.approx(expected,rel=1e-9)
    shape,_=read_step(path)
    assert not inside(shape,(0.,0.,150.))
    assert inside(shape,(a*math.cos(math.pi/6),a*math.sin(math.pi/6),150.))


@pytest.mark.parametrize('sid',['cylinder-top-angle','oval-cylinder-top-cut',
    'cone-frustum','cone','cone-cut-two-planes','segmented-bend-tapered-angle',
    'mitred-elbow-pipe-cone-angle','rectangle-to-round','prism','pyramid',
    'pipe-to-cone-angle-trunk','pipe-to-oblique-cone-angle-trunk',
    'rectangle-to-pipe-angle-branch','vessel-end-cap-hemispherical','helix-tapered',
    'rectangle-to-round-angled-top','rectangle-to-round-angled-base',
    'ellipse-to-round','ellipse-to-round-offset','ellipse-to-ellipse',
    'ellipse-to-ellipse-offset','ellipse-to-rectangle','ellipse-to-rectangle-offset',
    'ellipse-to-rectangle-angled-top'])
def test_other_families_have_closed_positive_volume_solids_not_surface_files(tmp_path,sid):
    parameters={'D':400.,'Dt':300.,'W':30.,'P':100.,'H':100.} if sid=='helix-tapered' else {}
    thickness=.5 if sid=='rectangle-to-round-angled-top' else 2.
    r=calculate(sid,thickness=thickness,parameters=parameters);path=tmp_path/(sid+'.step')
    stats=write_solid_step(r.parts,path,thickness)
    assert stats['solids']==len(r.parts) and stats['closed'] and stats['volume_mm3']>0
    assert 'CLOSED SOLIDS' in path.read_text(encoding='utf-8')
    assert 'MANIFOLD_SOLID_BREP' in path.read_text(encoding='utf-8')


def test_overconstrained_fan_disables_an_ineligible_solid_without_disabling_2d(tmp_path):
    r=calculate('rectangle-to-round-angled-top',thickness=2.)
    assert r.capabilities['dxf'] and not r.capabilities['step_solid']
    assert 'normal sapması' in r.capabilities['step_solid_reason']
    assert any(w.code=='SOLID_NOT_EVALUATED' for w in r.warnings)
    report=UnfoldService().export(r,ExportOptions(str(tmp_path/'not-a-surface.step'),'step'))
    assert report.status=='error' and not (tmp_path/'not-a-surface.step').exists()


def test_default_export_is_solid_through_the_isolated_cad_worker(tmp_path):
    r=calculate('cylinder',thickness=2.);target=tmp_path/'solid.step'
    report=UnfoldService().export(r,ExportOptions(str(target),'step'))
    assert report.status=='complete',report.errors
    assert read_step(target)[1]['solids']==1


def test_zero_thickness_never_falls_back_to_a_surface_or_overwrites_existing_file(tmp_path):
    r=calculate('cylinder',thickness=0.);target=tmp_path/'previous.step';target.write_bytes(b'previous user file')
    assert not r.capabilities['step_solid']
    report=UnfoldService().export(r,ExportOptions(str(target),'step',overwrite=True))
    assert report.status=='error' and not report.files and 'kalınlığı' in report.errors[0].message
    assert target.read_bytes()==b'previous user file'


def test_a_surface_cannot_be_accepted_as_a_successful_solid(tmp_path,monkeypatch):
    from core.unfolding import solid_cad
    from core.unfolding.cad import build_patch
    r=calculate('cylinder',thickness=2.)
    monkeypatch.setattr(solid_cad,'thicken_part',lambda part,t,quality=None:build_patch(part.surface_patches[0]))
    with pytest.raises(ValueError,match='yüzey|katı'):
        write_solid_step(r.parts,tmp_path/'invalid.step',2.)
    assert not (tmp_path/'invalid.step').exists()
