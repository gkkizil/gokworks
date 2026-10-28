"""Independent physical invariants and primary published dimensional references."""
from dataclasses import replace
from math import cos,sin,tan,radians,pi,hypot
import pytest
from modules.gear_calculator.families import MechanismSpecification,CATALOG,calculate
from modules.gear_calculator.families.calculation import cylindrical
from modules.gear_calculator.families.geometry import sections,section_polygon,poses,verify,cycloid_point,sample
from modules.gear_calculator.serialization import to_dict,from_dict


def spec(kind):
    if kind=='chain_sprocket':
        from modules.gear_calculator.sprockets import SprocketPairSpecification
        return SprocketPairSpecification()
    return MechanismSpecification(kind=kind,width_mm=10,teeth1=24 if kind=='internal' else 20,
        teeth2=72 if kind=='internal' else 12 if kind=='cycloidal' else 40)


@pytest.mark.parametrize('kind',CATALOG)
def test_each_type_has_explicit_capability_and_strict_roundtrip(kind):
    s=spec(kind);r=calculate(s)
    assert r.cad_available==CATALOG[kind].geometry
    assert from_dict(to_dict(s))==s
    for key,value in (('version',True),('version',2),('units','inch'),('unexpected',1)):
        d=to_dict(s);d[key]=value
        with pytest.raises(ValueError):from_dict(d)
    if not r.cad_available:
        assert any('henüz tamamlanmış' in w for w in r.warnings)
        with pytest.raises(ValueError):sections(s)


def test_helical_normal_transverse_reference_from_drivetrainhub():
    s=replace(spec('helical'),module_mm=1,helix_deg=15,teeth1=17,bore1_mm=0,bore2_mm=0)
    r=calculate(s)
    assert r.value('mₜ')==pytest.approx(1.035276,abs=.0000005)
    assert r.value('αₜ')==pytest.approx(20.646896,abs=.0000005)
    assert r.value('d₁')==pytest.approx(17.599695,abs=.0000005)
    # Normal tooth depth, not transverse tooth depth.
    assert r.value('dₐ₁')-r.value('d₁')==pytest.approx(2)
    assert r.value('d₁')-r.value('d𝒻₁')==pytest.approx(2.5)


@pytest.mark.parametrize('m,beta,z1,z2',[(.5,15,24,48),(2,20,20,40),(3,35,16,32)])
def test_helical_base_pitch_hand_load_and_width_invariants(m,beta,z1,z2):
    s=replace(spec('helical'),module_mm=m,helix_deg=beta,teeth1=z1,teeth2=z2,bore1_mm=0,bore2_mm=0)
    r=calculate(s);g=cylindrical(s,z1);q=cylindrical(s,z2)
    assert g['r']*cos(radians(beta))==pytest.approx(m*z1/2)
    assert r.value('Fₐ')/r.value('Fₜ')==pytest.approx(tan(radians(beta)))
    assert r.value('T₂ ideal')*abs(r.value('n₂'))==pytest.approx(r.value('T₁')*abs(r.value('n₁')))
    for z in (0,s.width_mm*.25,s.width_mm*.5,s.width_mm):
        p1,p2=poses(s,.27,z)
        assert g['r']*(p1[1]-.27)+q['r']*(p2[1]-(pi-pi/z2-.27*z1/z2))==pytest.approx(0,abs=1e-12)
    wide=calculate(replace(s,width_mm=s.width_mm*2))
    assert wide.value('εβ')==pytest.approx(2*r.value('εβ'))
    assert wide.value('Fₜ')==pytest.approx(r.value('Fₜ'))


def test_herringbone_midplane_continuity_and_ideal_axial_balance():
    s=spec('herringbone');r=calculate(s)
    assert r.value('Fₐ net (ideal)')==0
    assert poses(s,.5,0)==poses(s,.5,s.width_mm)
    assert poses(s,.5,s.width_mm/2-1e-9)[0][1]==pytest.approx(poses(s,.5,s.width_mm/2+1e-9)[0][1],abs=1e-12)


def test_rack_motion_matches_pitch_line_speed_and_true_straight_flanks():
    s=spec('rack');r=calculate(s)
    assert r.value('s / tur')==pytest.approx(40*pi)
    assert r.value('v kremayer')==pytest.approx(1000*pi)
    assert poses(s,.25)[1][2]==pytest.approx(5)
    assert all(seg.kind=='line' for seg in sections(s)[1].outer)
    assert r.value('L kremayer')==pytest.approx(s.rack_teeth*r.value('p'))


def test_internal_circle_order_and_direction_are_not_external_gear_formulas():
    s=spec('internal');r=calculate(s)
    assert r.value('a')==pytest.approx(48)
    assert r.value('n₂')==pytest.approx(500)
    assert r.value('dₐ₂')==140 and r.value('d𝒻₂')==149
    p=section_polygon(sections(s)[1],.0005)
    assert len(p.interiors)==1
    with pytest.raises(ValueError):calculate(replace(s,teeth2=32))


def test_planet_willis_equation_assembly_and_neighbour_clearance():
    s=spec('planetary');r=calculate(s)
    zs,zp,zr=s.teeth1,s.teeth2,r.value('z halka')
    assert zr==zs+2*zp
    ns,nc,nr=r.value('n₁'),r.value('n₂'),r.value('n halka')
    assert (ns-nc)*zs+(nr-nc)*zr==pytest.approx(0,abs=1e-10)
    assert r.value('i')==6 and r.value('n₂')==250
    with pytest.raises(ValueError):calculate(replace(s,planets=6))
    with pytest.raises(ValueError):calculate(replace(s,teeth1=21))


def test_bevel_cone_geometry_and_worm_lead_are_independent_of_spur_assumptions():
    r=calculate(spec('bevel'));a=radians(r.value('δ₁'));b=radians(r.value('δ₂'))
    assert a+b==pytest.approx(pi/2)
    assert sin(a)/sin(b)==pytest.approx(.5)
    assert r.value('R dış')==pytest.approx(hypot(20,40))
    w=calculate(spec('worm'))
    assert w.value('i')==20 and w.value('d vida')==20 and w.value('d çark')==80
    assert w.value('a')==50 and tan(radians(w.value('γ')))==pytest.approx(.2)
    assert w.value('İlerleme')==pytest.approx(4*pi)
    h=calculate(spec('hypoid'))
    assert not any(k in ('d₁','d₂','a') for k,v,u in h.values)


def test_cycloid_pin_envelope_is_tangent_at_all_contact_phases():
    s=spec('cycloidal');N=s.teeth2;R=s.module_mm*N/2;e=s.eccentricity_mm
    for j in range(N):
        for k in range(21):
            u=2*pi*j/N+2*pi*k/20/(N-1)
            p,derivative=cycloid_point(s,u)
            import cmath
            center=R*cmath.exp(1j*u)-e*cmath.exp(1j*N*u)
            delta=center-p
            assert abs(delta)==pytest.approx(s.roller_radius_mm,abs=1e-12)
            assert (delta*derivative.conjugate()).real==pytest.approx(0,abs=1e-11)
    assert calculate(s).value('i')==11
    with pytest.raises(ValueError):calculate(replace(s,eccentricity_mm=R/N))


@pytest.mark.parametrize('kind',['rack','helical','herringbone','internal','planetary','cycloidal'])
def test_real_profiles_are_closed_simple_and_mesh_over_a_full_cycle(kind):
    s=spec(kind)
    for section in sections(s):
        p=section_polygon(section,.0005)
        assert p.is_valid and p.area>0
    r=verify(s)
    assert r['maximum_overlap_mm2']<=r['overlap_tolerance_mm2']


@pytest.mark.parametrize('key,value',[('module_mm',0),('module_mm',float('nan')),('module_mm',10**1000),
    ('teeth1',True),('teeth2',400),('helix_deg',41),('width_mm',0),('load',None)])
def test_invalid_input_does_not_reach_geometry_or_cad(key,value):
    with pytest.raises(ValueError):calculate(replace(spec('helical'),**{key:value}))
