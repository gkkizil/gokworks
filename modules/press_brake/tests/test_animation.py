"""Smooth playback: display-only poses on a real-time line; the result stays with the checked frames."""
from dataclasses import replace
import threading
import pytest
from modules.press_brake.animation import (APPROACH, BEND_SPEED, FPS, TRAVEL_SPEED, Builder, Timeline, build,
                                           pose_mesh, schedule)
from modules.press_brake.demo import load_demo
from modules.press_brake.service import Frame, run


@pytest.fixture(scope='module')
def checked():
    plan = load_demo('L120')
    return plan, run(plan)


def test_schedule_runs_each_step_at_the_display_speeds():
    plan = load_demo('U'); segments = schedule(plan)
    assert [s.phase for s in segments[:3]] == ['approach', 'bend', 'retract']
    assert len(segments) == 3*len(plan.steps)
    for a, b in zip(segments, segments[1:]):
        assert b.start == pytest.approx(a.start+a.duration)
    turn = plan.turn(plan.steps[0])
    assert segments[0].duration == pytest.approx(APPROACH/TRAVEL_SPEED)
    assert segments[1].duration == pytest.approx(abs(turn)/BEND_SPEED)


@pytest.mark.timeout(120)
def test_checked_frames_sit_in_order_on_the_time_line_and_poses_cover_it(checked):
    plan, result = checked
    cache = {}; poses = build(plan, cache=cache)
    timeline = Timeline(plan, result, poses, cache)
    assert timeline.frame_times == sorted(timeline.frame_times)
    assert timeline.frame_times[0] == pytest.approx(0.) and timeline.frame_times[-1] == pytest.approx(timeline.duration)
    assert poses[0].time == 0. and poses[-1].time == pytest.approx(timeline.duration)
    assert len(poses) >= timeline.duration*FPS                        # at least 60 poses per second at 1x
    gaps = [b.time-a.time for a, b in zip(poses, poses[1:])]
    assert max(gaps) <= 1/FPS+1e-9 and min(gaps) > 0
    # Every checked frame has a pose at its time with the same step / phase.
    for frame, t in zip(result.frames, timeline.frame_times):
        pose = timeline.pose_at(t+1e-9)
        assert pose.step == frame.step and abs(pose.time-t) <= 1/FPS+1e-9
    # Bend poses turn monotonically towards the checked final angle.
    bend = [p.angle for p in poses if p.phase == 'bend']
    final = [f.angle for f in result.frames if f.phase == 'bend'][-1]
    retract = next(p for p in poses if p.phase == 'retract')          # the bend's end pose opens the retract
    assert abs(bend[-1]) <= abs(final)+1e-6 and retract.angle == pytest.approx(final, abs=.05)
    assert all(abs(b) >= abs(a)-1e-6 for a, b in zip(bend, bend[1:]))
    # Composing a pose uses the warmed cache only (no new triangulation).
    before = len(cache); mesh = pose_mesh(timeline.pose_at(timeline.duration/2), cache)
    assert len(cache) == before and mesh.triangles > 100


def test_hits_come_only_from_checked_frames():
    plan = load_demo('L120')
    frames = [Frame(0, 'approach', 0., None, (), (), (), APPROACH), Frame(0, 'bend', 10., None, (), ('hit',), ()),
              Frame(0, 'bend', 20., None, (), (), ())]
    result = type('R', (), {'frames': frames})()
    timeline = Timeline(plan, result, [], {})
    t_hit = timeline.frame_times[1]
    assert timeline.hit_between(frames, 0., t_hit-.01) is None
    assert timeline.hit_between(frames, 0., t_hit) == 1
    assert timeline.hit_between(frames, t_hit, t_hit+1) is None       # already standing on it
    assert timeline.frame_at(t_hit+.001) == 1 and timeline.frame_at(0.) == 0


@pytest.mark.timeout(120)
def test_builder_posts_a_timeline_and_cancel_posts_nothing(checked):
    plan, result = checked
    got = []; done = threading.Event()
    Builder(plan, result, lambda t: (got.append(t), done.set())).thread.join(60)
    assert done.is_set() and got[0].poses
    got.clear(); b = Builder(plan, result, got.append); b.cancel(); b.thread.join(60)
    assert not got
