"""Reference dimensions, independent mounting solutions, strict v1 compatibility."""
from dataclasses import replace
from math import pi,sqrt,sin,cos
import json,subprocess,sys
import pytest
from modules.gear_calculator.sprockets import *
from modules.gear_calculator.sprockets.geometry import profile,polygon,verify,poses,chain_route
from modules.gear_calculator.serialization import to_dict,from_dict
from modules.gear_calculator.models import GearPairSpecification,LoadSpecification
from modules.gear_calculator.families.models import MechanismSpecification


def test_iso_08b_20_40_reference_and_force_is_not_spur_pitch_radius_force():
    s=SprocketPairSpecification();r=calculate(s)
    assert r.driver.pitch_diameter_mm==pytest.approx(81.1842,abs=.00005)
    assert r.driver.pitch_radius_mm==pytest.approx(40.59207795652285)
    assert r.driver.angular_pitch_deg==pytest.approx(18)
    assert r.driven.pitch_diameter_mm==pytest.approx(161.8678,abs=.00005)
    assert r.driver.nominal_root_diameter_mm==pytest.approx(72.6742,abs=.00005)
    assert r.driver.profile_root_diameter_mm==pytest.approx(72.5890559130457)
    assert r.chain_speed_m_s==pytest.approx(6.35)
    assert r.effective_force_n==pytest.approx(236.22047244)
    assert r.input_torque_nm==pytest.approx(30/pi)
    assert r.output_rpm==pytest.approx(750) and r.ratio==pytest.approx(2)
    assert r.ideal_output_torque_nm==pytest.approx(60/pi)
    assert r.effective_force_n!=pytest.approx(2000*r.input_torque_nm/r.driver.pitch_diameter_mm,rel=1e-4)


@pytest.mark.parametrize('series,p,d,b',[('08B-1',12.7,8.51,7.75),('10B-1',15.875,10.16,9.65),('12B-1',19.05,12.07,11.68),('16B-1',25.4,15.88,17.02)])
def test_catalogue_primary_dimensions_are_exact_and_identity_is_preserved(series,p,d,b):
    c=CHAINS[series]
    assert (c.pitch_mm,c.roller_diameter_mm,c.inner_width_mm)==(p,d,b)
    assert c.standard=='ISO 606:2015' and c.strands==1
    s=SprocketPairSpecification(driver=SprocketSpecification(chain=c),driven=SprocketSpecification(chain=c,teeth=40))
    assert from_dict(to_dict(s))==s


@pytest.mark.parametrize('mode,rpm',[('power',1500),('power',-750),('torque',300)])
def test_primary_load_energy_balance_and_same_signed_output(mode,rpm):
    load=LoadSpecification(mode=mode,input_rpm=rpm,power_kw=1.5 if mode=='power' else None,torque_nm=20 if mode=='torque' else None)
    r=calculate(replace(SprocketPairSpecification(),load=load))
    assert r.output_rpm*r.ratio==pytest.approx(rpm)
    assert r.effective_force_n*r.chain_speed_m_s==pytest.approx(1000*r.power_kw)
    assert r.ideal_output_torque_nm*abs(r.output_rpm)==pytest.approx(r.input_torque_nm*abs(rpm))


@pytest.mark.parametrize('z1,z2,C',[(20,40,300),(40,20,300),(20,20,200),(9,80,700),(120,120,1800)])
def test_even_link_selection_and_inverse_matches_independent_quadratic_large_root(z1,z2,C):
    s=SprocketPairSpecification(driver=SprocketSpecification(teeth=z1),driven=SprocketSpecification(teeth=z2),center_distance_mm=C)
    r=calculate(s);p=s.driver.chain.pitch_mm;S=r.selected_links-(z1+z2)/2;A=((z2-z1)/(2*pi))**2
    expected=p/4*(S+sqrt(S*S-8*A))
    assert r.corrected_center_mm==pytest.approx(expected,abs=1e-9)
    assert r.selected_links%2==0 and r.selected_links>=r.theoretical_links-1e-10
    assert r.corrected_center_mm>=C-1e-9
    inverse=calculate(replace(s,mounting_mode='links',center_distance_mm=None,link_count=r.selected_links))
    assert inverse.corrected_center_mm==pytest.approx(r.corrected_center_mm)
    assert r.small_wrap_deg+r.large_wrap_deg==pytest.approx(360)
    assert r.chain_length_mm==pytest.approx(r.selected_links*p)


def test_odd_link_warning_and_no_silent_rounding_in_link_input_mode():
    r=calculate(SprocketPairSpecification(mounting_mode='links',center_distance_mm=None,link_count=79))
    assert r.selected_links==79 and any('offset' in w for w in r.warnings)


@pytest.mark.parametrize('changes',[dict(teeth=True),dict(teeth=0),dict(teeth=8),dict(teeth=121),dict(teeth=20.5),dict(bore_mm=-1),
    dict(bore_mm=.5),dict(bore_mm=100),dict(width_mm=.1),dict(width_mm=7.5),dict(hub_diameter_mm=20),
    dict(hub_diameter_mm=5,hub_length_mm=10),dict(profile_reference='involute'),dict(width_mm=float('nan'))])
def test_invalid_sprocket_geometry_is_rejected(changes):
    with pytest.raises(ValueError):calculate(replace(SprocketPairSpecification(),driver=replace(SprocketSpecification(),**changes)))


@pytest.mark.parametrize('chain',[replace(ChainSpecification(),standard='ANSI'),replace(ChainSpecification(),series='#40'),
    replace(ChainSpecification(),pitch_mm=0),replace(ChainSpecification(),pitch_mm=-1),replace(ChainSpecification(),roller_diameter_mm=13),
    replace(ChainSpecification(),roller_diameter_mm=7.92),replace(ChainSpecification(),strands=True)])
def test_catalogue_cannot_be_forged_or_ansi_substituted_for_equal_pitch(chain):
    with pytest.raises(ValueError):calculate(replace(SprocketPairSpecification(),driver=SprocketSpecification(chain=chain)))


@pytest.mark.parametrize('changes',[dict(center_distance_mm=-1),dict(center_distance_mm=100),dict(center_distance_mm=float('inf')),
    dict(link_count=80),dict(mounting_mode='links',center_distance_mm=None,link_count=80.5),
    dict(mounting_mode='links',center_distance_mm=None,link_count=True),dict(mounting_mode='links',center_distance_mm=None,link_count=20),
    dict(mounting_mode='links',center_distance_mm=None,link_count=2001),dict(load=LoadSpecification(input_rpm=0)),
    dict(load=LoadSpecification(torque_nm=10))])
def test_invalid_mounting_and_conflicting_load_are_rejected(changes):
    with pytest.raises(ValueError):calculate(replace(SprocketPairSpecification(),**changes))


def test_pair_series_mismatch_is_not_silently_accepted():
    with pytest.raises(ValueError,match='aynı standart'):
        calculate(replace(SprocketPairSpecification(),driven=SprocketSpecification(chain=CHAINS['10B-1'])))


@pytest.mark.parametrize('series',CHAINS)
@pytest.mark.parametrize('z',[9,20,40,120])
def test_true_arc_profile_count_closure_seat_tangency_and_roller_release(series,z):
    wheel=SprocketSpecification(chain=CHAINS[series],teeth=z);s=SprocketPairSpecification(driver=wheel,driven=wheel,center_distance_mm=2000)
    arcs=profile(wheel)
    assert len(arcs)==4*z and {a.tooth for a in arcs}==set(range(z))
    assert len([a for a in arcs if a.role=='seat'])==z
    for a,b in zip(arcs,arcs[1:]+arcs[:1]):
        assert a.point(1)==pytest.approx(b.point(0),abs=1e-8)
        if a.role=='seat' and b.role=='flank':
            # Opposite circle normals at a concave-to-convex tangency.
            u=tuple((x-y)/a.radius for x,y in zip(a.point(1),a.center))
            v=tuple((x-y)/b.radius for x,y in zip(b.point(0),b.center))
            assert sum(x*y for x,y in zip(u,v))==pytest.approx(-1)
    shape=polygon(wheel)
    assert shape.is_valid and shape.area>0
    from shapely.geometry import Point
    radius=wheel.chain.pitch_mm/(2*sin(pi/z));roller=wheel.chain.roller_diameter_mm/2
    for j in range(z):
        seat=Point(radius*cos(2*pi*j/z),radius*sin(2*pi*j/z)).buffer(roller,quad_segs=64)
        assert shape.intersection(seat).area<1e-9
    check=verify(s)
    assert check['minimum_roller_clearance_mm']>=0
    assert not check['manufacturing_approved'] and not check['chain_motion_verified']
    first,second=poses(s,.2)
    assert first[1]==pytest.approx(second[1]) and second[2]==pytest.approx(calculate(s).corrected_center_mm)


def test_static_chain_route_tangents_are_perpendicular_to_pitch_radii():
    s=SprocketPairSpecification();r=calculate(s);a,b,c,d=chain_route(s)
    v=(b[0]-a[0],b[1]-a[1]);w=(c[0]-d[0],c[1]-d[1])
    assert sum(x*y for x,y in zip(a,v))==pytest.approx(0,abs=1e-9)
    assert sum(x*y for x,y in zip(d,w))==pytest.approx(0,abs=1e-9)
    assert (b[0]-r.corrected_center_mm)**2+b[1]**2==pytest.approx((r.driven.pitch_diameter_mm/2)**2)


def test_three_strict_schemas_roundtrip_without_changing_old_field_sets():
    for s,schema in [(SprocketPairSpecification(),'gokworks.chain_sprocket'),(GearPairSpecification(),'gokworks.gear_pair'),
        (MechanismSpecification(),'gokworks.gear_mechanism')]:
        d=to_dict(s);assert d['schema']==schema and d['version']==1 and from_dict(json.loads(json.dumps(d)))==s
    for key,value in [('version',True),('version',2),('units','inch'),('unexpected',1)]:
        d=to_dict(SprocketPairSpecification());d[key]=value
        with pytest.raises(ValueError):from_dict(d)
    d=to_dict(SprocketPairSpecification());d['driver']['chain']['unknown']=1
    with pytest.raises(ValueError):from_dict(d)
    with pytest.raises(ValueError):to_dict(MechanismSpecification(kind='chain_sprocket'))


def test_calculation_import_does_not_load_qt_cad_or_solidworks():
    code='from modules.gear_calculator.sprockets import *; import sys; calculate(SprocketPairSpecification()); assert not any(x in sys.modules for x in ("PySide6", "OCP", "pythoncom", "win32com"))'
    subprocess.run([sys.executable,'-c',code],check=True,timeout=20)
