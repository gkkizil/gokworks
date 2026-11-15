"""Smooth, real-time playback of a checked plan: display-only poses between the checked ones.

The collision result comes only from the checked frames (service.run). Here the same
kinematics and geometry produce extra poses at a fixed rate on a time line, so playback
can run at 60 fps and at any speed. Nothing here is checked; a pose between two checked
samples is shown, never reported.

Time line at 1x: the upper assembly travels at TRAVEL_SPEED (approach / retract) and the
bend turns at BEND_SPEED. A step's three phases follow each other; steps follow steps.
"""
from bisect import bisect_right
from dataclasses import dataclass
from math import ceil, degrees
import threading

FPS = 60
TRAVEL_SPEED = 30.   # mm/s at 1x (display pace, not a machine setting)
BEND_SPEED = 30.     # deg/s at 1x
APPROACH = 15.       # mm, same span as the check (service.run)
SPEEDS = (.25, .5, 1., 1.5, 2., 4.)


@dataclass(frozen=True)
class Segment:
    step: int
    phase: str
    start: float      # s at 1x
    duration: float   # s at 1x
    a: float          # mm (approach / retract) or deg (bend)
    b: float


@dataclass(frozen=True)
class Pose:
    time: float
    step: int
    phase: str
    angle: float              # deg, signed as in the checked frames
    parts: tuple              # (base solid, 4x4 placement, kind) per body, machine included
    axis: tuple
    tool_bounds: tuple


def schedule(plan):
    """Segments of the whole plan on the 1x time line."""
    segments, t = [], 0.
    for index, step in enumerate(plan.steps):
        turn = plan.turn(step)
        for phase, a, b, rate in (('approach', APPROACH, 0., TRAVEL_SPEED), ('bend', 0., turn, BEND_SPEED),
                                  ('retract', 0., APPROACH, TRAVEL_SPEED)):
            duration = abs(b-a)/rate
            segments.append(Segment(index, phase, t, duration, a, b)); t += duration
    return segments


def frame_time(segments, frame):
    """Where a checked frame sits on the time line (its step, phase and value)."""
    for segment in segments:
        if segment.step == frame.step and segment.phase == frame.phase:
            value = abs(frame.angle) if frame.phase == 'bend' else getattr(frame, 'travel', 0.)
            span = segment.b-segment.a
            fraction = 0. if not span else min(1., max(0., (value-segment.a)/span))
            return segment.start+fraction*segment.duration
    return 0.


def build(plan, stop=None, progress=None, fps=FPS, cache=None):
    """Poses at ``fps`` on the 1x time line (the last pose of each segment included).

    ``cache`` (a dict) receives every solid's display triangles here, off the GUI thread,
    so playback only places them.
    """
    from .geometry import Geometry, machine_bodies, solid_part
    from .kinematics import step_angles
    geometry = Geometry(plan); poses = []
    segments = schedule(plan)
    for number, segment in enumerate(segments):
        bend = plan.bend(plan.steps[segment.step].bend)
        turn = plan.turn(plan.steps[segment.step])
        count = max(1, ceil(segment.duration*fps))
        for k in range(count+1 if number == len(segments)-1 or segments[number+1].step != segment.step else count):
            if stop is not None and stop.is_set():
                return None
            value = segment.a+(segment.b-segment.a)*k/count
            fraction = value/turn if segment.phase == 'bend' else 0. if segment.phase == 'approach' else 1.
            angles = step_angles(plan, segment.step, fraction)
            bodies, _ = geometry.scene(segment.step, angles, segment.phase, value if segment.phase != 'bend' else 0)
            shown = list(bodies)+machine_bodies(bodies)
            if cache is not None:
                for b in shown:
                    base = b.base if b.base is not None else b.shape
                    if id(base) not in cache:
                        cache[id(base)] = (base, solid_part(base))
            poses.append(Pose(segment.start+segment.duration*k/count, segment.step, segment.phase,
                              degrees(angles.get(bend.id, 0)),
                              tuple((b.base if b.base is not None else b.shape, b.matrix, b.kind) for b in shown),
                              ((-bend.length/2, 0, 0), (bend.length/2, 0, 0)),
                              tuple((b.id, b.bounds) for b in bodies if b.kind != 'sheet')))
        if progress:
            progress(number+1, len(segments))
    return poses


class Part:
    """What mesh() needs from a body, for an already computed pose."""
    __slots__ = ('base', 'matrix', 'kind', 'shape')

    def __init__(self, base, matrix, kind):
        import numpy as np
        self.base, self.kind, self.shape = base, kind, base
        self.matrix = np.eye(4) if matrix is None else matrix


def pose_mesh(pose, cache):
    """Display mesh of a pose; each source solid is triangulated once (``cache``)."""
    from .geometry import mesh
    return mesh([Part(*part) for part in pose.parts], None, cache, limit=None)


class Timeline:
    """Poses on the time line plus where the checked frames sit, for one result."""

    def __init__(self, plan, result, poses, cache=None):
        self.segments = schedule(plan)
        self.poses = poses; self.times = [p.time for p in poses]
        self.duration = self.segments[-1].start+self.segments[-1].duration if self.segments else 0.
        self.frame_times = [frame_time(self.segments, f) for f in result.frames]
        self.cache = {} if cache is None else cache

    def pose_at(self, t):
        return self.poses[max(0, min(len(self.poses)-1, bisect_right(self.times, t)-1))]

    def frame_at(self, t):
        """Index of the last checked frame at or before ``t`` (for the slider and the read-out)."""
        index = 0
        for i, ft in enumerate(self.frame_times):
            if ft <= t+1e-9:
                index = i
        return index

    def hit_between(self, frames, t0, t1):
        """First checked frame with a collision in (t0, t1]; playback stops there."""
        for i, (frame, ft) in enumerate(zip(frames, self.frame_times)):
            if frame.hits and t0 < ft <= t1+1e-9:
                return i
        return None


class Builder:
    """Builds a Timeline on a plain thread; ``done(timeline)`` runs on the GUI thread via ``post``."""

    def __init__(self, plan, result, post, progress=None):
        self.stop = threading.Event()
        def run():
            cache = {}
            try:
                poses = build(plan, self.stop, progress, cache=cache)
            except Exception:      # display only: the checked frames still play
                poses = None
            if poses and not self.stop.is_set():
                post(Timeline(plan, result, poses, cache))
        self.thread = threading.Thread(target=run, name='press-brake-animation', daemon=True)
        self.thread.start()

    def cancel(self):
        self.stop.set()
