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


def test_tangent_solids_keep_refinement_without_expensive_boolean(monkeypatch):
    from modules.press_brake import collision
    a = body('left', 'sheet', prism(Region.from_polygon(box(0, 0, 10, 10)), 2))
    b = body('right', 'sheet', prism(Region.from_polygon(box(10, 0, 20, 10)), 2))
    monkeypatch.setattr(collision, 'intersection', lambda *args: pytest.fail('tangent boxes cannot contain collision volume'))
    hits, near = check([a, b], near_margin=3)
    assert not hits and near


def test_collision_cache_retains_actual_hits_and_changes_with_contact_masks(monkeypatch):
    from modules.press_brake import collision
    region = Region.from_polygon(box(-.1, -.1, .1, .1))
    sheet = body('active', 'sheet', prism(region, .2))
    punch = body('punch:tool', 'punch', prism(region, .2))
    cache = {}; actual = collision.intersection; calls = []
    def count(*args):
        calls.append(1); return actual(*args)
    monkeypatch.setattr(collision, 'intersection', count)
    contact = [('punch', 0, 0, .3, ('active',))]
    assert not check([sheet, punch], contact, cache=cache)[0]
    assert not check([sheet, punch], contact, cache=cache)[0] and len(calls) == 1
    assert check([sheet, punch], cache=cache)[0] and len(calls) == 2


def test_rotated_die_channel_preserves_one_body_and_physical_work_reference():
    from shapely.affinity import rotate
    p = load_demo('L120'); die = p.tool('demo-die')
    raw = replace(die, section=Region.from_polygon(rotate(die.section.polygon(), -90, origin=(0, 0))),
                  holder_section=Region.from_polygon(rotate(die.holder_section.polygon(), -90, origin=(0, 0))),
                  channels=tuple(replace(c, rotation=90) for c in die.channels))
    q = p.changed(tools=tuple(raw if t.id == die.id else t for t in p.tools))
    for channel in ('V16', 'V24'):
        a = p.changed(steps=(replace(p.steps[0], channel=channel),))
        b = q.changed(steps=(replace(q.steps[0], channel=channel),))
        before, _ = Geometry(a).scene(0, step_angles(a, 0, .5))
        after, _ = Geometry(b).scene(0, step_angles(b, 0, .5))
        actual = [s for s in after if s.kind == 'die']
        expected = next(s for s in before if s.kind == 'die')
        assert len(actual) == 1 and actual[0].bounds == pytest.approx(expected.bounds, abs=1e-7)
        assert shape_stats(actual[0].shape)['volume_mm3'] == pytest.approx(shape_stats(expected.shape)['volume_mm3'])


def test_canonical_sheet_hit_retains_volume_position_and_refinement_at_station():
    import numpy as np
    from modules.press_brake.collision import Hit
    from modules.press_brake.geometry import section_rotation
    shapes = [body('a', 'sheet', prism(Region.from_polygon(box(0, 0, 10, 10)), 2)),
              body('b', 'sheet', prism(Region.from_polygon(box(5, 0, 15, 10)), 2))]
    local, _ = check(shapes)
    assert len(local) == 1 and local[0].volume == pytest.approx(100)
    matrix = translation(5, 3, 7)@section_rotation(60)
    world = [body(s.id, s.kind, transform(s.shape, matrix)) for s in shapes]
    expected, expected_near = check(world, near_margin=3)
    canonical = {h.pair: Hit(h.pair, tuple((matrix@np.r_[h.location, 1.])[:3]), h.volume) for h in local}
    actual, near = check(world, near_margin=3, sheet_hits=canonical)
    assert near == expected_near and actual[0].pair == expected[0].pair
    assert actual[0].volume == pytest.approx(expected[0].volume)
    assert actual[0].location == pytest.approx(expected[0].location, abs=1e-7)


def test_scene_colours_bodies_by_kind_and_machine_stays_out_of_the_checked_bodies():
    import numpy as np
    from modules.press_brake.geometry import SCENE_COLOURS, machine_bodies, mesh, rgb, scene_mesh
    p = load_demo('L120'); g = Geometry(p)
    bodies, _ = g.scene(0, step_angles(p, 0, 0))
    assert not any(b.kind == 'machine' for b in bodies)          # collision input unchanged
    machine = machine_bodies(bodies)
    assert {b.id for b in machine} == {'machine:beam', 'machine:rail'}
    punch_top = max(b.bounds[5] for b in bodies if b.kind == 'punch')
    die_bottom = min(b.bounds[2] for b in bodies if b.kind == 'die')
    beam, rail = sorted(machine, key=lambda b: -b.bounds[2])
    assert beam.bounds[2] >= punch_top-1e-6 and rail.bounds[5] <= die_bottom+1e-6   # never inside the tools
    colours = {tuple(c) for c in np.frombuffer(scene_mesh(bodies).colours, np.uint8).reshape(-1, 3)}
    assert {rgb(SCENE_COLOURS[k]) for k in ('sheet', 'punch', 'die', 'machine')} <= colours
    flat = mesh(g.part_bodies({}))
    assert {tuple(c) for c in np.frombuffer(flat.colours, np.uint8).reshape(-1, 3)} == {rgb(SCENE_COLOURS['sheet'])}


def test_separation_is_a_true_lower_bound_and_never_hides_an_overlap():
    """The convex-container shortcut may only skip pairs that really are apart."""
    from itertools import combinations
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from modules.press_brake.collision import intersection, separation, volume
    plan = load_demo('U'); plan = replace(plan, steps=tuple(replace(s, punch='demo-wide') for s in plan.steps))   # known collision
    g = Geometry(plan); checked = positive = overlapping = 0
    for index, fraction, phase, travel in ((1, 1., 'retract', 6.), (1, .7, 'bend', 0)):
        bodies, _ = g.scene(index, step_angles(plan, index, fraction), phase, travel)
        assert all(b.hull is not None for b in bodies)
        for a, b in combinations(bodies, 2):
            if a.kind == b.kind != 'sheet' or 'holder' in (a.kind, b.kind):
                continue
            bound = separation(a, b); checked += 1
            if bound > 1e-7:
                positive += 1
                measure = BRepExtrema_DistShapeShape(a.shape, b.shape)
                assert measure.IsDone() and measure.Value() >= bound-1e-6, (a.id, b.id, bound, measure.Value())
            elif volume(intersection(a.shape, b.shape))[0] > .001:
                overlapping += 1
    assert checked >= 10 and positive >= 3 and overlapping >= 1          # both branches really exercised


def test_abutting_segments_become_one_solid_and_gapped_ones_stay_apart():
    from modules.press_brake.geometry import joined
    one = joined([Segment(-40, 50), Segment(30, 10), Segment(10, 20)])
    assert [(s.start, s.length) for s in one] == [(-40, 80)]
    two = joined([Segment(-40, 30), Segment(5, 35)])
    assert [(s.start, s.length) for s in two] == [(-40, 30), (5, 35)]
    plan = load_demo('L120'); step = replace(plan.steps[0], punch_segments=(Segment(-40, 40), Segment(0, 40)), die_segments=(Segment(-40, 30), Segment(5, 35)))
    plan = replace(plan, steps=(step,))
    ids = [b.id for b in Geometry(plan).scene(0, step_angles(plan, 0, 0))[0]]
    assert ids.count('punch:DEMO-NARROW:1') == 1 and 'punch:DEMO-NARROW:2' not in ids
    assert 'die:DEMO-2V:1' in ids and 'die:DEMO-2V:2' in ids


def test_cached_display_mesh_equals_the_uncached_one():
    import numpy as np
    from modules.press_brake.geometry import mesh
    plan = load_demo('U'); g = Geometry(plan)
    bodies, _ = g.scene(1, step_angles(plan, 1, .6), 'bend', 0)
    cached, again, direct = mesh(bodies, None, g.mesh_cache), mesh(bodies, None, g.mesh_cache), mesh(bodies)
    assert cached == again and cached.triangles == direct.triangles and cached.colours == direct.colours
    assert np.allclose(cached.bounds, direct.bounds, atol=1e-4) and np.allclose(cached.origin, direct.origin, atol=1e-4)
    a, b = (np.sort(np.frombuffer(m.positions, '<f4').reshape(-1, 3), axis=0) for m in (cached, direct))
    assert np.allclose(a, b, atol=2e-3)                                   # same triangles, placed numerically vs by OCCT
