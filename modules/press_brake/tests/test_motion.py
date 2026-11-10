from shapely.geometry import box
from modules.press_brake.geometry import body, prism, transform, translation
from modules.press_brake.models import Region
from modules.press_brake.collision import check
from modules.press_brake.motion import sample_interval


def test_mid_motion_collision_is_found_when_both_end_poses_are_clear():
    moving = prism(Region.from_polygon(box(-.4, -.4, .4, .4)), 1)
    fixed = body('tutucu', 'holder', prism(Region.from_polygon(box(-.3, -.3, .3, .3)), 1))
    cache = {}
    def probe(x):
        if x not in cache:
            a = body('sac', 'sheet', transform(moving, translation(x=x)))
            hits, near = check([a, fixed], near_margin=2)
            cache[x] = (hits, near)
        return cache[x]
    assert not probe(-8)[0] and not probe(8)[0]
    frames = sample_interval(probe, -8, 8, maximum=2, minimum=.25)
    assert any(frames)
    assert any(-1 < x < 1 and hit for x, (hit, _) in cache.items())
    # All broad intervals are inspected, then close pairs force extra samples.
    assert len(cache) > 9


def test_refinement_and_temporal_order_do_not_depend_on_playback_rate():
    seen = set()
    def probe(x):
        seen.add(x); return x, abs(x) < 2
    forward = sample_interval(probe, -10, 10, maximum=3, minimum=.25)
    reverse = sample_interval(probe, 10, -10, maximum=3, minimum=.25)
    assert forward == sorted(forward)
    assert reverse == forward[::-1]
    assert len(seen) > 10
