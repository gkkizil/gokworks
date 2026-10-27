from dataclasses import replace
from math import atan,atan2,cos,hypot,pi,sin,sqrt,tan,radians
import pytest
from shapely.affinity import rotate,translate
from shapely.geometry import Point
from modules.gear_calculator import GearSpecification,GearPairSpecification,calculate_gear,calculate_pair
from modules.gear_calculator.geometry import gear_profile,involute,polygon,pair_angles,verify_mesh


@pytest.mark.parametrize('t',[0,.02,.2,.5,.9])
def test_analytic_involute_radius_and_unwinding_angle(t):
    p=involute(20,t)
    assert hypot(*p)==pytest.approx(20*sqrt(1+t*t),abs=1e-12)
    assert atan2(p[1],p[0])==pytest.approx(t-atan(t),abs=1e-12)


@pytest.mark.parametrize('m,z',[(.2,18),(1,21),(2,20),(3,40),(5,80),(1,300)])
def test_closed_nonintersecting_contour_radii_tooth_count_and_equal_spacing(m,z):
    s=GearSpecification(module_mm=m,teeth=z,bore_mm=0)
    p=gear_profile(s);g=calculate_gear(s);points=p.points(m*.001)
    assert points[0]==pytest.approx(points[-1])
    assert {x.tooth for x in p.segments}==set(range(z))
    poly=polygon(s,m*.001)
    assert poly.is_valid and poly.exterior.is_ccw
    assert min(hypot(*v) for v in points)==pytest.approx(g.root_radius_mm,abs=m*.002)
    assert max(hypot(*v) for v in points)==pytest.approx(g.outside_radius_mm,abs=m*.002)
    first=[x for x in p.segments if x.tooth==0]
    second=[x for x in p.segments if x.tooth==1]
    a=2*pi/z
    for x,y in zip(first,second):
        q=x.point(.37)
        assert y.point(.37)==pytest.approx((q[0]*cos(a)-q[1]*sin(a),q[0]*sin(a)+q[1]*cos(a)),abs=1e-10)


def test_pitch_circle_intersection_has_nominal_tooth_thickness():
    s=GearSpecification();g=calculate_gear(s);poly=polygon(s,.00001)
    # Check the true analytic flank angle at t=tan(alpha); independently locate
    # the CAD approximation's intersection via a high-resolution circle.
    circle=Point(0,0).buffer(g.pitch_radius_mm,quad_segs=8000).boundary
    arcs=poly.intersection(circle)
    assert arcs.length/s.teeth==pytest.approx(g.tooth_thickness_mm,abs=.0002)


@pytest.mark.parametrize('z1,z2,angle',[(18,36,20),(20,40,20),(21,37,20),(32,64,14.5),(16,48,25),(120,300,20)])
def test_full_pitch_sweep_has_correct_phase_and_no_material_overlap(z1,z2,angle):
    s=GearPairSpecification(GearSpecification(teeth=z1,pressure_angle_deg=angle,bore_mm=0),
                            GearSpecification(teeth=z2,pressure_angle_deg=angle,bore_mm=0))
    check=verify_mesh(s)
    assert check.maximum_overlap_mm2<=check.overlap_tolerance_mm2
    a,b=pair_angles(s,.4);a0,b0=pair_angles(s,0)
    assert (b-b0)/(a-a0)==pytest.approx(-z1/z2)


def test_deliberately_wrong_phase_produces_interference_in_independent_polygon_oracle():
    s=GearPairSpecification();r=calculate_pair(s)
    p1,p2=polygon(s.pinion),polygon(s.wheel)
    wrong=translate(rotate(p2,pi,origin=(0,0),use_radians=True),xoff=r.center_distance_mm)
    assert p1.intersection(wrong).area>1


@pytest.mark.parametrize('m,z',[(.1,20),(2,20),(20,250)])
def test_bezier_involute_curve_stays_inside_declared_vector_error_bound(m,z):
    s=GearSpecification(module_mm=m,teeth=z,bore_mm=0);g=calculate_gear(s);p=gear_profile(s)
    alpha=radians(s.pressure_angle_deg);delta=pi/(2*z)+tan(alpha)-alpha
    flanks=[v for v in p.segments if v.tooth==0 and v.kind=='bezier']
    lower=flanks[:len(flanks)//2]
    t0=sqrt(max(0,(g.root_radius_mm/g.base_radius_mm)**2-1))
    t1=sqrt((g.outside_radius_mm/g.base_radius_mm)**2-1)
    for j,segment in enumerate(lower):
        for k in range(101):
            u=k/100;t=t0+(t1-t0)*(j+u)/len(lower)
            a=involute(g.base_radius_mm,t)
            expected=(a[0]*cos(delta)+a[1]*sin(delta),-a[0]*sin(delta)+a[1]*cos(delta))
            actual=segment.point(u)
            assert hypot(actual[0]-expected[0],actual[1]-expected[1])<=p.curve_tolerance_mm
