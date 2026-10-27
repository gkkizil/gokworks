from dataclasses import fields,replace
from itertools import product
from math import isclose,pi

import pytest
from shapely.affinity import rotate,translate

from modules.gear_calculator import GearSpecification,GearPairSpecification,LoadSpecification,calculate_gear,calculate_pair
from modules.gear_calculator.geometry import gear_profile,polygon,pair_angles,verify_mesh
from modules.gear_calculator.validation import gear_issues,SpecificationError,require_manufacturable
from . import independent_reference as ref

TEETH=(8,12,18,20,37,100,300)
ANGLES=(14.5,20.,25.,30.)
LOADS=(LoadSpecification(power_kw=.0001,input_rpm=100000),LoadSpecification(),
       LoadSpecification(power_kw=1e7,input_rpm=.001),
       LoadSpecification(mode='torque',power_kw=None,torque_nm=.0001,input_rpm=100000),
       LoadSpecification(mode='torque',power_kw=None,torque_nm=9.5492966,input_rpm=-1500),
       LoadSpecification(mode='torque',power_kw=None,torque_nm=1e7,input_rpm=-.001))


@pytest.mark.parametrize('m',(.1,.15,.5,1.25,2.,3.,8.,19.))
def test_9408_parametric_cases_against_independent_60_digit_reference(m):
    for z1,z2,angle,load in product(TEETH,TEETH,ANGLES,LOADS):
        s=GearPairSpecification(GearSpecification(m,z1,angle,bore_mm=0),GearSpecification(m,z2,angle,bore_mm=0),load)
        actual=calculate_pair(s);expected=ref.pair(s)
        case=(m,z1,z2,angle,load)
        for name,value in expected.items():
            assert isclose(getattr(actual,name),float(value),rel_tol=2e-11,abs_tol=1e-22),(case,name,getattr(actual,name),value)
        assert actual.working_center_distance_mm==pytest.approx(float(expected['center_distance_mm']))
        for spec,got in ((s.pinion,actual.pinion),(s.wheel,actual.wheel)):
            g=ref.gear(m,spec.teeth,angle)
            for field in fields(got):
                assert isclose(getattr(got,field.name),float(g[field.name]),rel_tol=2e-12,abs_tol=1e-11),(case,field.name)


def test_manufacturer_khk_table_4_1_literal_example():
    # Published m=3, alpha=20, z=12/24; dimensions are valid nominal calculations
    # even though the small zero-shift pinion has an undercut warning.
    s=GearPairSpecification(GearSpecification(3,12,bore_mm=0),GearSpecification(3,24,bore_mm=0))
    r=calculate_pair(s)
    assert r.center_distance_mm==pytest.approx(54)
    for g,pitch,base,tip,root in ((r.pinion,36,33.829,42,28.5),(r.wheel,72,67.658,78,64.5)):
        assert g.pitch_diameter_mm==pytest.approx(pitch)
        assert g.base_diameter_mm==pytest.approx(base,abs=.0005)
        assert g.outside_diameter_mm==pytest.approx(tip)
        assert g.root_diameter_mm==pytest.approx(root)
    assert any(i.code=='undercut' for i in r.warnings)


def test_exact_undercut_boundary_is_not_rejected_due_to_binary_sine_roundoff():
    g=GearSpecification(teeth=8,pressure_angle_deg=30,bore_mm=0)
    assert not any(i.code=='undercut' for i in gear_issues(g))
    assert any(i.code=='undercut' for i in gear_issues(replace(g,teeth=7)))
    assert any(i.code=='undercut' for i in gear_issues(replace(g,pressure_angle_deg=29.9999)))
    s=GearPairSpecification(g,g);r=calculate_pair(s)
    assert r.transverse_contact_ratio==pytest.approx(1.1802490816594808)
    assert any(i.code=='low_contact_margin' for i in r.warnings)
    require_manufacturable(r)
    verify_mesh(s)


def test_minimum_web_equality_accepts_roundoff_but_rejects_real_loss_of_material():
    s=GearSpecification(module_mm=.15,teeth=20,bore_mm=2.225)
    assert not any(i.severity=='error' for i in gear_issues(s))
    with pytest.raises(SpecificationError):calculate_gear(replace(s,bore_mm=s.bore_mm+.000001))


def test_huge_integer_input_is_rejected_before_float_overflow():
    with pytest.raises(SpecificationError):calculate_gear(GearSpecification(module_mm=10**1000))


@pytest.mark.parametrize('factor',(.1,.5,1.,3.,9.))
def test_module_scaling_and_load_mode_have_physical_dimensional_invariants(factor):
    base=GearPairSpecification();r=calculate_pair(base)
    changed=replace(base,pinion=replace(base.pinion,module_mm=2*factor,bore_mm=0),
                         wheel=replace(base.wheel,module_mm=2*factor,bore_mm=0))
    q=calculate_pair(changed)
    assert q.center_distance_mm==pytest.approx(r.center_distance_mm*factor)
    assert q.transverse_contact_ratio==pytest.approx(r.transverse_contact_ratio)
    assert q.tangential_force_n==pytest.approx(r.tangential_force_n/factor)
    assert q.input_torque_nm==pytest.approx(r.input_torque_nm)
    assert q.output_torque_nm*abs(q.output_rpm)==pytest.approx(q.input_torque_nm*1500)
    explicit=replace(changed,load=LoadSpecification(mode='torque',power_kw=None,torque_nm=q.input_torque_nm))
    assert calculate_pair(explicit).power_kw==pytest.approx(base.load.power_kw)


@pytest.mark.parametrize('z1,z2,angle',[(8,8,30),(18,300,20),(20,40,20),(37,61,25),(64,32,14.5)])
def test_profiles_remain_in_contact_through_a_pitch_not_only_nonintersecting(z1,z2,angle):
    s=GearPairSpecification(GearSpecification(teeth=z1,pressure_angle_deg=angle,bore_mm=0),
                           GearSpecification(teeth=z2,pressure_angle_deg=angle,bore_mm=0))
    r=calculate_pair(s);p1,p2=polygon(s.pinion,.00025),polygon(s.wheel,.00025)
    maximum_gap=0.
    for i in range(96):
        a,b=pair_angles(s,2*pi/z1*i/96)
        x=rotate(p1,a,origin=(0,0),use_radians=True)
        y=translate(rotate(p2,b,origin=(0,0),use_radians=True),xoff=r.center_distance_mm)
        assert x.intersection(y).area<=s.pinion.module_mm**2*2e-5
        maximum_gap=max(maximum_gap,x.distance(y))
    allowed=2*(gear_profile(s.pinion).curve_tolerance_mm+.00025)
    assert maximum_gap<=allowed
