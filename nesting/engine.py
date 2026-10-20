"""True-contour NFP search: Minkowski obstacles + feasible translations + multistart.

Own Python implementation. No JavaScript/Node, C++ ABI or external executable.
It returns the best verified heuristic solution; mathematical optimality is not asserted.
"""

from collections import Counter
from datetime import datetime, timezone
import random
import time

from shapely import affinity, union_all
from shapely.geometry import box, Point

from . import ENGINE, ENGINE_VERSION
from .geometry import footprint, rotated, minkowski
from .models import Placement, Result
from .validation import validate_result


def _vertices(g):
    if g.is_empty:
        return []
    if hasattr(g, 'exterior'):
        return list(g.exterior.coords) + [xy for ring in g.interiors for xy in ring.coords]
    if g.geom_type in ('LineString', 'LinearRing', 'Point'):
        return list(g.coords)
    return [v for piece in g.geoms for v in _vertices(piece)]


class SearchEnded(Exception):
    pass


def nest(project, *, stop=None, progress=None):
    project.validate()
    started = time.monotonic(); deadline = started+project.options.seconds
    o = project.options; rng = random.Random(o.seed)
    cache = {}; rotated_cache = {}; best = None; iterations = 0
    instances = [(p, i) for p in project.parts for i in range(1, p.quantity+1)]
    digest = project.fingerprint()

    def checkpoint():
        if (stop is not None and stop.is_set()) or time.monotonic() >= deadline:
            raise SearchEnded()

    def geometry(part, angle):
        key = (part.id, angle)
        if key not in rotated_cache:
            rotated_cache[key] = footprint(rotated(part, angle))
        return rotated_cache[key]

    def nfp(fixed_part, fixed_angle, moving_part, moving_angle):
        key = (fixed_part.id, fixed_angle, moving_part.id, moving_angle)
        if key not in cache:
            fixed = geometry(fixed_part, fixed_angle)
            reflected = affinity.scale(geometry(moving_part, moving_angle), -1, -1, origin=(0, 0))
            obstacle = minkowski(fixed, reflected, checkpoint)
            distance = max(o.gap, o.kerf)+fixed_part.geometry_error+moving_part.geometry_error
            # Mitre expansion conservatively contains the round Euclidean offset.
            cache[key] = obstacle.buffer(distance+2e-6, join_style=2) if distance else obstacle
        return cache[key]

    def candidate(part, sheet, previous):
        angles = [0] if not o.rotation else o.angles
        if o.grain_locked or part.grain_locked:
            angles = [a for a in angles if abs(a % 180) < 1e-7]
        winner = None
        for angle in angles:
            checkpoint()
            g = geometry(part, angle); x0, y0, x1, y1 = g.bounds
            margin = o.margin+part.geometry_error+o.kerf/2
            left, bottom = margin-x0, margin-y0
            right, top = sheet.width-margin-x1, sheet.height-margin-y1
            if right < left-1e-7 or top < bottom-1e-7:
                continue
            # Degenerate exact-fit translation domains must remain lines/points.
            if abs(right-left) < 1e-7 and abs(top-bottom) < 1e-7:
                from shapely.geometry import Point
                feasible = Point(left, bottom)
            elif abs(right-left) < 1e-7 or abs(top-bottom) < 1e-7:
                from shapely.geometry import LineString
                feasible = LineString([(left, bottom), (right, top)])
            else:
                feasible = box(left, bottom, right, top)
            contact_points = _vertices(feasible)
            if previous:
                obstacles = []
                for old in previous:
                    checkpoint()
                    other = project.part(old.part_id)
                    obstacles.append(affinity.translate(nfp(other, old.angle, part, angle), old.x, old.y))
                forbidden = union_all(obstacles)
                contact_points.extend(_vertices(forbidden.intersection(feasible)))
                feasible = feasible.difference(forbidden)
            # A polygonal feasible translation region contains its best bottom-
            # left extreme at a vertex. Validate each candidate against real shapes.
            for x, y in sorted(set(_vertices(feasible)+contact_points), key=lambda xy: (xy[1], xy[0])):
                checkpoint()
                if not (left-1e-7 <= x <= right+1e-7 and bottom-1e-7 <= y <= top+1e-7):
                    continue
                translated = affinity.translate(g, x, y)
                valid = True
                for old in previous:
                    other = project.part(old.part_id)
                    fixed = affinity.translate(geometry(other, old.angle), old.x, old.y)
                    distance = max(o.gap, o.kerf)+part.geometry_error+other.geometry_error
                    if translated.intersection(fixed).area > 1e-6 or translated.distance(fixed)+1e-6 < distance:
                        valid = False; break
                if valid:
                    score = (y+y1, x+x1, angle)
                    if winner is None or score < winner[0]:
                        winner = (score, x, y, angle)
                    break
        return winner

    max_trials = {'Hızlı': 3, 'Dengeli': 12, 'Yüksek': 40}[o.quality]
    for trial in range(max_trials):
        placements = []; remaining = []; sheets = []; counts = Counter()
        order = sorted(instances, key=lambda item: item[0].area, reverse=True)
        if trial == 1:
            order.sort(key=lambda item: max(item[0].polygon.bounds[2:]), reverse=True)
        elif trial > 1:
            # Elite-informed random order perturbation; reproducible seed.
            if trial % 3:
                for _ in range(max(1, len(order)//5)):
                    a, b = rng.randrange(len(order)), rng.randrange(len(order)); order[a], order[b] = order[b], order[a]
            else:
                rng.shuffle(order)
        interrupted = False
        try:
            for index, (part, instance) in enumerate(order):
                checkpoint()
                found = False
                for sheet, number, previous in sheets:
                    if sheet.material != part.material or abs(sheet.thickness-part.thickness) > 1e-7:
                        continue
                    point = candidate(part, sheet, previous)
                    if point:
                        _, x, y, angle = point
                        p = Placement(part.id, instance, sheet.id, number, x, y, angle)
                        placements.append(p); previous.append(p); found = True; break
                if not found:
                    choices = [s for s in project.sheets if s.material == part.material
                               and abs(s.thickness-part.thickness) <= 1e-7 and counts[s.id] < s.stock]
                    if trial % 3 == 2:
                        rng.shuffle(choices)
                    else:
                        # Try both fewer large sheets and less purchased area;
                        # choosing only the smallest sheet can needlessly split a job.
                        choices.sort(key=lambda s: s.width*s.height, reverse=trial % 3 == 0)
                    for sheet in choices:
                        point = candidate(part, sheet, [])
                        if point:
                            _, x, y, angle = point; counts[sheet.id] += 1
                            p = Placement(part.id, instance, sheet.id, counts[sheet.id], x, y, angle)
                            placements.append(p); sheets.append((sheet, counts[sheet.id], [p])); found = True; break
                if not found:
                    remaining.append(part.id)
                if progress:
                    progress(min(99, int(100*(time.monotonic()-started)/o.seconds)),
                             f'{trial+1}. arama · {len(placements)}/{len(order)} parça · {len(sheets)} levha')
        except SearchEnded:
            interrupted = True
            used = {(p.part_id, p.instance) for p in placements}
            remaining = [p.id for p, i in instances if (p.id, i) not in used]
        iterations += 1
        result = Result(digest, placements, remaining, ENGINE, ENGINE_VERSION, time.monotonic()-started,
                        iterations, datetime.now(timezone.utc).isoformat(), interrupted)
        validate_result(project, result, complete=False)
        used_area = sum(s.width*s.height for s, _, _ in sheets)
        score = (len(remaining), len(sheets), used_area,
                 sum(max((p.y+geometry(project.part(p.part_id), p.angle).bounds[3] for p in rows), default=0)
                     for _, _, rows in sheets))
        if best is None or score < best[0]:
            best = (score, result)
        if interrupted:
            break
    result = best[1]
    result.elapsed = time.monotonic()-started; result.iterations = iterations
    result.stopped = stop is not None and stop.is_set()
    validate_result(project, result, complete=False)
    if progress:
        progress(100, f'Kontrol tamamlandı · {len(result.placements)} yerleşti · {len(result.unplaced)} yerleşmedi')
    return result
