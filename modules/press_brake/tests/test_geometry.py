from dataclasses import replace
from math import pi
import pytest
from shapely.geometry import Point, box
from modules.gear_calculator.cad import shape_stats
from modules.press_brake.demo import load_demo
from modules.press_brake.geometry import Geometry, bend_shape, body, prism, translation, transform
from modules.press_brake.kinematics import step_angles
from modules.press_brake.collision import check
from modules.press_brake.models import Mount, Region, Segment
from modules.press_brake.service import step_scope


def test_l_exact_sector_has_2mm_thickness_constant_volume_and_real_holes():
    plan = load_demo('L120'); g = Geometry(plan); bend = plan.part.bends[0]
    volume = shape_stats(bend_shape(bend, 2, 0))['volume_mm3']
    for phi in (pi/6, pi/3, -pi/3):
        assert shape_stats(bend_shape(bend, 2, phi))['volume_mm3'] == pytest.approx(volume, rel=1e-8)
    root = next(b for b in g.part_bodies({}) if b.id == 'F0')
    assert shape_stats(root.shape)['volume_mm3'] < 80*60*2-390
    # Probe through the actual hole: no painted/surface-only cutout.
    probe = body('hole-probe', 'punch', prism(Region.from_polygon(Point(0, 0).buffer(3)), 10))
    assert not check([root, probe])[0]


def test_box_real_reliefs_holes_and_tool_change_remove_known_interference():
    p = load_demo('box'); g = Geometry(p)
    flat_area = sum(f.region.polygon().area for f in p.part.flanges)+sum(b.region.polygon().area for b in p.part.bends)
    assert len(p.part.flanges[0].region.holes) == 1
    assert all(len(f.region.holes) == 1 for f in p.part.flanges)
    assert p.part.thickness == 2 and len(p.part.bends) == 4
    assert flat_area > 12000
    for i in range(4):
        bodies, contacts = g.scene(i, step_angles(p, i, 1))
        assert not check(bodies, contacts)[0]
    bad = p.changed(steps=tuple(replace(s, punch='demo-wide') for s in p.steps)); gb = Geometry(bad)
    bodies, contacts = gb.scene(2, step_angles(bad, 2, 1))
    assert any('punch:DEMO-WIDE' in ' '.join(h.pair) for h in check(bodies, contacts)[0])


def test_multi_v_is_one_body_channel_moves_body_and_axial_gaps_are_preserved():
    p = load_demo('L120'); s = p.steps[0]
    segmented = replace(s, punch_segments=(Segment(-40, 20), Segment(5, 25)))
    p = p.changed(steps=(segmented,)); g = Geometry(p)
    a, _ = g.scene(0, step_angles(p, 0, .5))
    upper = [b for b in a if b.kind == 'punch']
    assert len(upper) == 2
    assert upper[0].bounds[3] == pytest.approx(-20)
    assert upper[1].bounds[0] == pytest.approx(5)
    original_die = next(b for b in a if b.kind == 'die')
    q = p.changed(steps=(replace(segmented, channel='V24'),))
    alt, _ = Geometry(q).scene(0, step_angles(q, 0, .5))
    other_die = next(b for b in alt if b.kind == 'die')
    assert other_die.bounds[1]-original_die.bounds[1] == pytest.approx(-36)
    assert len([b for b in alt if b.kind == 'die']) == 1


def test_expected_work_contact_not_exempt_whole_active_flange():
    p = load_demo('L120'); g = Geometry(p)
    for fraction in (0, .5, 1):
        bodies, contacts = g.scene(0, step_angles(p, 0, fraction))
        assert not check(bodies, contacts)[0]
    bad = p.changed(steps=(replace(p.steps[0], punch='demo-wide'),))
    bodies, contacts = Geometry(bad).scene(0, step_angles(bad, 0, 1))
    assert any('F0' in hit.pair or 'F1' in hit.pair for hit in check(bodies, contacts)[0])


def test_missing_geometry_or_incompatible_exact_mount_is_not_checked():
    p = load_demo('L120'); punch = p.tools[0]
    for change in ({'section': None}, {'holder_section': None}, {'mount': Mount('WILA', '')},
                   {'mount': Mount('tongue-A', 'holder-B')}, {'mount': Mount('A', 'B', 'A', 'C')}):
        q = p.changed(tools=(replace(punch, **change),)+p.tools[1:])
        assert step_scope(q, q.steps[0])
    assert Mount('A', 'B', 'A', 'B').compatible


@pytest.mark.parametrize('angle', [pi/6, pi/3, -pi/6, -pi/3])
def test_trimmed_bend_retains_cutout_in_intermediate_closed_solid(angle):
    p = load_demo('L120'); b = p.part.bends[0]
    poly = b.region.polygon(); c = poly.centroid
    cutout = Point(c.x, c.y).buffer(.35, quad_segs=8)
    trimmed = replace(b, region=Region.from_polygon(poly.difference(cutout)))
    whole = shape_stats(bend_shape(b, 2, pi/3))['volume_mm3']
    shape = bend_shape(trimmed, 2, angle)
    assert 0 < shape_stats(shape)['volume_mm3'] < whole-.5


def test_local_contact_tolerance_does_not_exempt_an_unrelated_flange():
    from modules.press_brake.collision import remove_contacts, volume, intersection
    section = Region.from_polygon(box(-.1, -.1, .1, .1))
    sheet = body('unrelated-flange', 'sheet', prism(section, .2))
    punch = body('punch:fixture', 'punch', prism(section, .2))
    common = intersection(sheet.shape, punch.shape)
    contact = [('punch', 0, 0, .3, ('active-bend', 'parent', 'child'))]
    assert volume(remove_contacts(common, sheet, punch, contact))[0] == pytest.approx(.008)


def test_aabb_overlap_is_not_itself_a_solid_collision():
    ring = Region.from_polygon(box(-10, -10, 10, 10).difference(box(-5, -5, 5, 5)))
    a = body('ring', 'sheet', prism(ring, 2))
    b = body('pin', 'punch', prism(Region.from_polygon(box(-2, -2, 2, 2)), 4))
    assert not check([a, b])[0]
    c = body('pin', 'punch', transform(b.shape, translation(x=7)))
    assert check([a, c])[0]
