from dataclasses import replace
from math import pi

import pytest

from modules.gear_calculator import GearSpecification,GearPairSpecification
from modules.gear_calculator import cad
from modules.gear_calculator.export import export_cad
from .independent_reference import volume


@pytest.mark.parametrize('m,z1,z2,angle,width,bore1,bore2',[
    (.1,32,64,14.5,.1,0.,0.),(.15,20,40,20.,5.,2.225,0.),
    (2.,8,8,30.,15.,0.,0.),(3.,37,61,25.,22.,10.,14.),(19.,73,300,20.,50.,0.,0.)])
def test_step_regeneration_matches_independent_analytic_volume_and_units(tmp_path,m,z1,z2,angle,width,bore1,bore2):
    common=dict(module_mm=m,pressure_angle_deg=angle,face_width_mm=width)
    s=GearPairSpecification(GearSpecification(teeth=z1,bore_mm=bore1,**common),
                            GearSpecification(teeth=z2,bore_mm=bore2,**common))
    result=export_cad(s,tmp_path/'pair.step')
    expected=float(volume(s.pinion)+volume(s.wheel))
    assert result['solids']==2 and result['volume_mm3']==pytest.approx(expected,rel=1e-4)
    assert result['bounds_mm'][2]==pytest.approx(0,abs=1e-6)
    assert result['bounds_mm'][5]==pytest.approx(width,abs=1e-6)
    assert result['units']=='mm'


def test_width_and_bore_change_true_solid_volume_without_changing_pitch_geometry():
    s=GearSpecification();base=cad.shape_stats(cad.build_gear(s))
    wide=cad.shape_stats(cad.build_gear(replace(s,face_width_mm=30)))
    bored=cad.shape_stats(cad.build_gear(replace(s,bore_mm=12)))
    assert wide['volume_mm3']==pytest.approx(2*base['volume_mm3'],rel=1e-10)
    removed=pi*((12/2)**2-(8/2)**2)*s.face_width_mm
    assert base['volume_mm3']-bored['volume_mm3']==pytest.approx(removed,rel=1e-10)
    assert base['bounds_mm']==pytest.approx(bored['bounds_mm'],abs=1e-8)


def test_uniform_length_scaling_has_cubic_volume_and_linear_bounds():
    base=GearSpecification(module_mm=.5,teeth=24,face_width_mm=4,bore_mm=2)
    scaled=replace(base,module_mm=2,face_width_mm=16,bore_mm=8)
    a=cad.shape_stats(cad.build_gear(base));b=cad.shape_stats(cad.build_gear(scaled))
    assert b['volume_mm3']==pytest.approx(a['volume_mm3']*64,rel=1e-9)
    assert b['bounds_mm']==pytest.approx(tuple(x*4 for x in a['bounds_mm']),abs=1e-6)
