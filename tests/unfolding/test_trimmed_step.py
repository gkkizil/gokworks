"""Independent analytic surface checks for the formerly missing trimmed STEP."""
import math

import pytest

from core.unfolding import UnfoldService
from core.unfolding.cad import build_patch,surface_stats,write_step,read_step
from .test_source_models import request

pytest.importorskip('OCP')

def test_angle_cut_cylinder_has_an_analytic_cylinder_surface_and_correct_area(tmp_path):
    result=UnfoldService(0).calculate(request('cylinder-top-angle'))
    assert result.status=='success'
    assert result.capabilities['step_surface']
    assert len(result.parts)==1
    patches=result.parts[0].surface_patches
    assert patches and all(p.kind=='trimmed_cylinder' for p in patches)
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    assert all(BRepAdaptor_Surface(build_patch(p)).GetType()==GeomAbs_Cylinder for p in patches)
    path=tmp_path/'angle-cut.step'
    write_step(result.parts,path)
    _,stats=read_step(path)
    # D=200, center height=250: the cosine cut integrates to zero over one turn.
    assert stats['area_mm2']==pytest.approx(math.pi*200*250,abs=.01)
    assert stats['solids']==0
    assert stats['bounds_mm']==pytest.approx((-100,-100,0,100,100,350),abs=.021)


@pytest.mark.parametrize('sid',['oval-cylinder','oval-cylinder-top-cut','pipe-cut-by-plate-angle',
                              'segmented-bend-oval-angle','segmented-bend-oval-opposite-angle'])
def test_profile_extrusion_has_real_trimmed_surfaces_and_step_readback(sid,tmp_path):
    result=UnfoldService(0).calculate(request(sid))
    assert result.status=='success'
    assert result.capabilities['step_surface']
    assert all(p.surface_patches for p in result.parts)
    assert all(s.kind in ('trimmed_cylinder','planar_3d','cylinder') for p in result.parts for s in p.surface_patches)
    path=tmp_path/(sid+'.step')
    stats=write_step(result.parts,path)
    assert stats['area_mm2']>0 and stats['solids']==0


@pytest.mark.parametrize('sid',[
    'pipe-to-pipe-angle-branch','pipe-to-pipe-angle-trunk',
    'pipe-to-cone-angle-branch','pipe-to-cone-angle-trunk',
    'cone-to-cone-vertical-branch','cone-to-cone-vertical-trunk',
    'rectangle-to-pipe-angle-branch','rectangle-to-pipe-angle-trunk',
    'segmented-bend-tapered-angle','mitred-elbow-pipe-cone-angle',
    'cone-cut-two-planes','rain-head-conical','reducing-breech-3-unequal',
    'oblique-cylinder','oblique-cone-offset-xy','oblique-cone-levels',
    'pipe-to-oblique-cone-angle-trunk','cone-to-oblique-cone-horizontal-trunk',
])
def test_trimmed_junctions_and_offset_circle_surfaces_read_back(sid,tmp_path):
    result=UnfoldService(0).calculate(request(sid))
    assert result.status=='success',result.errors
    assert result.capabilities['step_surface']
    assert all(p.surface_patches for p in result.parts)
    stats=write_step(result.parts,tmp_path/(sid+'.step'))
    assert stats['solids']==0 and stats['area_mm2']>0
