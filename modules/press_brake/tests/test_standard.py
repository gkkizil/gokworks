"""Generic market-standard tools: drawn from shared dimensions, labelled, usable in the check."""
import threading
from dataclasses import replace
import pytest
from modules.press_brake.demo import load_demo
from modules.press_brake.service import run
from modules.press_brake.standard import (NOTE, SECTIONED, V_SERIES, default_segments, is_generic, recommended_v,
                                          single_v_die, standard_tools, station, straight_punch)


def test_library_follows_the_shared_market_dimensions():
    tools = standard_tools()
    assert all(is_generic(t) and t.section is not None and t.holder_section is not None and t.mount.compatible for t in tools)
    assert sum(SECTIONED) == 835
    dies = [t for t in tools if t.kind == 'die']
    assert {c.opening for t in dies for c in t.channels} >= set(V_SERIES)
    for die in dies:
        channel = die.channels[0]; x0, _, x1, top = die.section.polygon().bounds
        assert abs(top) < 1e-9 and x1-x0 > channel.opening and channel.shoulder_radius >= .5
    punch = straight_punch()
    assert (punch.tip_angle, punch.tip_radius, punch.height) == (88, .8, 95)
    assert abs(punch.tip[1]-punch.section.polygon().bounds[1]) < 1e-9          # working point = lowest point of the rounded tip
    width = punch.section.polygon().intersection(__import__('shapely').geometry.box(-50, 90, 50, 95)).bounds
    assert abs(width[2]-width[0]-13) < 1e-6                                   # 13 mm European tang


@pytest.mark.parametrize('thickness, v', [(1, 8), (2, 16), (3, 25), (5, 40), (.8, 6)])
def test_v_opening_follows_the_eight_times_thickness_rule(thickness, v):
    assert recommended_v(thickness) == v


@pytest.mark.parametrize('length', [10, 80, 120, 300, 835])
def test_station_is_built_from_sectioned_pieces_and_covers_the_bend(length):
    pieces = station(length)
    total = sum(p.length for p in pieces)
    assert total >= length and {p.length for p in pieces} <= set(SECTIONED)
    assert abs(pieces[0].start+total/2) < 1e-9
    assert all(abs(a.start+a.length-b.start) < 1e-9 for a, b in zip(pieces, pieces[1:]))
    with pytest.raises(ValueError):
        station(836)


def test_a_demo_part_bent_with_generic_tools_is_checkable_and_says_what_the_tools_are():
    """Placement + one solid check per pose; the full sweep is covered by the service tests (too slow here)."""
    from modules.press_brake.collision import check
    from modules.press_brake.geometry import Geometry
    from modules.press_brake.kinematics import step_angles
    from modules.press_brake.service import plan_notes, step_scope
    plan = load_demo('L120'); tools = standard_tools()
    punch, die = straight_punch(), single_v_die(recommended_v(plan.part.thickness))
    plan = replace(plan, tools=plan.tools+tools,
                   steps=tuple(replace(s, punch=punch.id, die=die.id, channel=die.channels[0].id, punch_segments=None, die_segments=None)
                               for s in plan.steps)).validate()
    step = plan.steps[0]; bend = plan.bend(step.bend)
    assert sum(s.length for s in default_segments(punch, bend)) >= bend.length
    assert step_scope(plan, step) == []                                   # nothing missing: the result can be clear or collision
    assert NOTE in plan_notes(plan, step)
    bodies, contacts = Geometry(plan).scene(0, step_angles(plan, 0, 1), 'bend', 0)
    kinds = {b.kind for b in bodies}
    assert {'sheet', 'punch', 'die', 'holder'} <= kinds
    hits, _ = check(bodies, contacts, near_margin=3.)
    assert not hits                                                       # a 90° air bend with 88° tools and V16 fits


def test_generic_holders_clamp_the_13_mm_tang_without_cutting_into_the_tool():
    from modules.press_brake.service import holder_overlap
    for tool in standard_tools():
        holder = tool.holder_section.polygon(); section = tool.section.polygon()
        assert holder_overlap(tool) == 0 and len(holder.interiors) >= 2          # bolt holes / clamp split are real voids
        seat = section.bounds[3] if tool.kind == 'punch' else section.bounds[1]
        assert (holder.bounds[1] <= seat-20+1e-6) if tool.kind == 'punch' else (holder.bounds[3] >= seat+8-1e-6)   # wraps the tang


def test_a_holder_cutting_into_its_tool_makes_the_step_uncheckable():
    from modules.press_brake.models import Region
    from modules.press_brake.service import holder_overlap, step_scope
    plan = load_demo('L120'); punch = plan.tool(plan.steps[0].punch)
    bad = replace(punch, holder_section=Region(((-8, 70), (8, 70), (8, 90), (-8, 90))))      # 10 mm into the body
    assert holder_overlap(bad) >= 100
    plan = replace(plan, tools=tuple(bad if t.id == punch.id else t for t in plan.tools))
    assert any('tutucu kesiti takım kesitine' in n for n in step_scope(plan, plan.steps[0]))
