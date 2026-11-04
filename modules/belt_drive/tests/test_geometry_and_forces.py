from dataclasses import replace
import math

import pytest

from modules.belt_drive import calculate, BeltDriveSpecification, CenterSpecification, PulleySpecification, SpecificationError
from modules.belt_drive.geometry import Point, open_belt_path, path_between_centers


def close(a, b, tolerance=1e-9):
    assert (a - b).norm < tolerance


@pytest.mark.parametrize('d1,d2', [(100., 200.), (200., 100.), (100., 100.)])
@pytest.mark.parametrize('angle', [0., .7, -2.1])
def test_actual_tangencies_continuity_arc_radii_and_wrapped_length(d1, d2, angle):
    path = open_belt_path(d1, d2, 400., origin=Point(12., -20.), angle_rad=angle)
    for index, segment in enumerate(path.segments):
        following = path.segments[(index + 1) % 4]
        close(segment.end, following.start)
        assert segment.tangent(1.).dot(following.tangent(0.)) == pytest.approx(1., abs=2e-14)
    upper, driven_arc, lower, driver_arc = path.segments
    for line, center, contact in ((upper, path.driver_center, upper.start), (upper, path.driven_center, upper.end),
                                  (lower, path.driven_center, lower.start), (lower, path.driver_center, lower.end)):
        assert (contact-center).dot(line.tangent()) == pytest.approx(0., abs=5e-12)
    for arc in (driven_arc, driver_arc):
        for fraction in (0., .13, .78, 1.):
            assert (arc.point(fraction) - arc.center).norm == pytest.approx(arc.radius_mm, abs=2e-12)
    assert path.length_mm == pytest.approx(path.metrics.exact_mm, abs=2e-12)
    close(path.point_at_distance(-10.), path.point_at_distance(path.length_mm - 10.))
    close(path.point_at_distance(path.length_mm), path.segments[0].start)


def test_numeric_polyline_integral_independently_recovers_analytic_length():
    path = open_belt_path(100., 200., 400.)
    count = 12000
    points = [path.point_at_distance(path.length_mm * i / count) for i in range(count + 1)]
    integral = math.fsum((b-a).norm for a,b in zip(points,points[1:]))
    assert integral < path.metrics.exact_mm
    assert path.metrics.exact_mm - integral < .0001


def test_rotated_centers_produce_the_same_route_and_length():
    first, second = Point(-30., 12.), Point(150., 280.)
    result = path_between_centers(80., 120., first, second)
    close(result.driver_center, first); close(result.driven_center, second)
    assert result.metrics.center_mm == pytest.approx(math.hypot(180., 268.))


@pytest.mark.parametrize('rotation,sign', [('ccw', 1.), ('cw', -1.)])
@pytest.mark.parametrize('count', [1, 2])
def test_span_vector_forces_balance_torque_and_action_reaction(rotation, sign, count):
    base = BeltDriveSpecification(pretension_per_belt_n=500., rotation=rotation)
    spec = replace(base, belt=replace(base.belt, count=count))
    result = calculate(spec); force = result.shaft_forces; path = result.geometry
    assert (force.tight_per_belt_n - force.slack_per_belt_n) * count == pytest.approx(result.effective_force_delta_n)
    upper, lower = (force.tight_per_belt_n, force.slack_per_belt_n) if rotation == 'ccw' else \
                   (force.slack_per_belt_n, force.tight_per_belt_n)
    f1, f2 = path.upper_direction * (upper * count), path.lower_direction * (lower * count)
    arm1, arm2 = path.segments[0].start - path.driver_center, path.segments[2].end - path.driver_center
    cross = lambda a,b: a.x*b.y-a.y*b.x
    assert (cross(arm1,f1)+cross(arm2,f2))/1000 == pytest.approx(-sign * result.input_torque_nm, rel=1e-13)
    assert force.driver_fx_n == pytest.approx(f1.x+f2.x)
    assert force.driver_fy_n == pytest.approx(f1.y+f2.y)
    assert force.driven_fx_n == -force.driver_fx_n and force.driven_fy_n == -force.driver_fy_n
    assert force.resultant_n != pytest.approx((force.tight_per_belt_n + force.slack_per_belt_n) * count)


def test_equal_diameters_have_parallel_spans_and_resultant_twice_initial_tension():
    result = calculate(BeltDriveSpecification(driven=PulleySpecification(100.), pretension_per_belt_n=500.))
    assert result.shaft_forces.resultant_n == pytest.approx(1000.)
    assert result.driver_wrap_deg == result.driven_wrap_deg == 180.


def test_force_rotates_with_actual_layout_and_missing_preload_stays_unevaluated():
    original = calculate(BeltDriveSpecification(pretension_per_belt_n=500.))
    rotated = calculate(replace(original.specification, center=CenterSpecification(axis_angle_deg=90.)))
    assert rotated.shaft_forces.driver_fx_n == pytest.approx(-original.shaft_forces.driver_fy_n)
    assert rotated.shaft_forces.driver_fy_n == pytest.approx(original.shaft_forces.driver_fx_n)
    assert calculate(BeltDriveSpecification()).shaft_forces is None
    with pytest.raises(SpecificationError, match='gevşek kol'):
        calculate(BeltDriveSpecification(pretension_per_belt_n=100.))
