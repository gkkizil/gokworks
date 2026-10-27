from dataclasses import replace
from math import cos, pi, radians, sin, tan

import pytest

from modules.gear_calculator import GearSpecification, GearPairSpecification, LoadSpecification, calculate_gear, calculate_pair
from modules.gear_calculator.models import FutureGearData
from modules.gear_calculator.validation import SpecificationError, require_manufacturable
from modules.gear_calculator.serialization import to_dict, from_dict


def test_reference_20_40_pair_and_exact_unit_conversion():
    r=calculate_pair(GearPairSpecification())
    for actual,expected in ((r.pinion.pitch_diameter_mm,40),(r.wheel.pitch_diameter_mm,80),
                            (r.pinion.outside_diameter_mm,44),(r.wheel.outside_diameter_mm,84),
                            (r.pinion.root_diameter_mm,35),(r.wheel.root_diameter_mm,75),
                            (r.center_distance_mm,60),(r.ratio,2),(r.output_rpm,-750)):
        assert actual==pytest.approx(expected)
    assert r.input_torque_nm==pytest.approx(9.55,abs=.001)
    assert r.tangential_force_n==pytest.approx(477.5,abs=.04)
    assert r.radial_force_n==pytest.approx(173.78298576534377)
    assert r.transverse_contact_ratio==pytest.approx(1.6351859635714583)
    assert r.output_torque_nm*abs(r.output_rpm)==pytest.approx(r.input_torque_nm*1500)
    assert r.power_kw==pytest.approx(r.input_torque_nm*1500*2*pi/60000)


@pytest.mark.parametrize('m,z,angle',[(.1,40,14.5),(.5,18,20),(1,24,25),(4,60,20),(10,200,30)])
def test_dimensions_and_contact_path_have_correct_scaling(m,z,angle):
    g=calculate_gear(GearSpecification(m,z,angle,bore_mm=0))
    assert g.pitch_diameter_mm==pytest.approx(m*z)
    assert g.base_diameter_mm==pytest.approx(m*z*cos(radians(angle)))
    assert g.addendum_mm+g.dedendum_mm==pytest.approx(g.whole_depth_mm)
    assert g.clearance_mm==pytest.approx(.25*m)
    assert g.tooth_thickness_mm*2==pytest.approx(g.circular_pitch_mm)
    assert g.undercut_limit_teeth==pytest.approx(2/sin(radians(angle))**2)


@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf'),'2',True])
def test_invalid_module_is_rejected_before_math(value):
    with pytest.raises(SpecificationError):
        calculate_gear(GearSpecification(module_mm=value))


@pytest.mark.parametrize('key,value',[('teeth',20.5),('teeth',True),('teeth',301),('teeth',0),
    ('face_width_mm',0),('bore_mm',35),('pressure_angle_deg',0),('helix_angle_deg',15),
    ('backlash_mm',.1),('profile_shift',.2),('gear_type','helical'),('future',FutureGearData(material='steel'))])
def test_invalid_or_unimplemented_gear_input_cannot_masquerade_as_supported(key,value):
    with pytest.raises(SpecificationError):
        calculate_gear(replace(GearSpecification(),**{key:value}))


@pytest.mark.parametrize('field,value',[('module_mm',2.5),('pressure_angle_deg',25),('face_width_mm',16)])
def test_incompatible_pair_is_rejected(field,value):
    s=GearPairSpecification(wheel=replace(GearSpecification(teeth=40),**{field:value}))
    with pytest.raises(SpecificationError):calculate_pair(s)


def test_load_mode_conflict_zero_speed_and_signed_rotation():
    s=GearPairSpecification()
    with pytest.raises(SpecificationError):calculate_pair(replace(s,load=LoadSpecification(torque_nm=10)))
    with pytest.raises(SpecificationError):calculate_pair(replace(s,load=LoadSpecification(input_rpm=0)))
    r=calculate_pair(replace(s,load=LoadSpecification(mode='torque',power_kw=None,torque_nm=12,input_rpm=-1200)))
    assert r.output_rpm==pytest.approx(600) and r.input_torque_nm==pytest.approx(12)
    assert r.power_kw==pytest.approx(12*1200*2*pi/60000)
    assert r.tangential_force_n==pytest.approx(600)
    assert r.radial_force_n==pytest.approx(600*tan(radians(20)))


def test_undercut_depends_on_pressure_angle_and_is_not_claimed_as_manufactured():
    s=GearPairSpecification(pinion=GearSpecification(teeth=16,bore_mm=0))
    r=calculate_pair(s)
    assert any(i.code=='undercut' for i in r.warnings)
    with pytest.raises(SpecificationError):require_manufacturable(r)
    s=replace(s,pinion=replace(s.pinion,pressure_angle_deg=25),wheel=replace(s.wheel,pressure_angle_deg=25))
    assert not any(i.code=='undercut' for i in calculate_pair(s).warnings)


def test_reserved_application_factor_life_do_not_silently_modify_nominal_loads():
    s=GearPairSpecification();r=calculate_pair(s)
    changed=calculate_pair(replace(s,load=replace(s.load,application_factor=2,design_life_hours=20000)))
    assert changed.tangential_force_n==pytest.approx(r.tangential_force_n)


def test_versioned_contract_roundtrip_and_strict_fields():
    s=GearPairSpecification();d=to_dict(s)
    assert from_dict(d)==s
    for key,value in (('version',2),('version',True),('units','in'),('extra',42)):
        bad=dict(d);bad[key]=value
        with pytest.raises(ValueError):from_dict(bad)
    bad=to_dict(s);bad['pinion']['unknown']=1
    with pytest.raises(ValueError):from_dict(bad)
