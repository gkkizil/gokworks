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

from modules.nesting import ENGINE, ENGINE_VERSION
from modules.nesting.geometry import footprint, rotated, minkowski, convex_parts
from modules.nesting.models import Placement, Result
from modules.nesting.validation import validate_result


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
    cache = {}; rotated_cache = {}; convex_cache = {}; best = None; iterations = 0
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
            fixed_key = (fixed_part.id, fixed_angle, False)
            reflected_key = (moving_part.id, moving_angle, True)
            if fixed_key not in convex_cache:
                convex_cache[fixed_key] = convex_parts(fixed, checkpoint)
            if reflected_key not in convex_cache:
                convex_cache[reflected_key] = convex_parts(reflected, checkpoint)
            obstacle = minkowski(fixed, reflected, checkpoint, parts_a=convex_cache[fixed_key], parts_b=convex_cache[reflected_key])
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
            pending = list(order)
            while pending:
                checkpoint()
                part, instance = pending.pop(0)
                choices = [s for s in project.sheets if s.material == part.material
                           and abs(s.thickness-part.thickness) <= 1e-7 and counts[s.id] < s.stock]
                if trial % 3 == 2:
                    rng.shuffle(choices)
                else:
                    choices.sort(key=lambda s: s.width*s.height, reverse=trial % 3 == 0)
                opening = None
                for sheet in choices:
                    point = candidate(part, sheet, [])
                    if point:
                        opening = (sheet, point); break
                if opening is None:
                    remaining.append(part.id)
                    continue
                sheet, point = opening
                counts[sheet.id] += 1; number = counts[sheet.id]
                _, x, y, angle = point
                first = Placement(part.id, instance, sheet.id, number, x, y, angle)
                previous = [first]; placements.append(first); sheets.append((sheet, number, previous))
                blocked = set(); index = 0
                # Fill this physical plate before opening another one. A large
                # part that cannot fit does not prevent smaller remaining parts
                # from filling its gaps. An already rejected shape cannot become
                # placeable by adding more obstacles, so cache that rejection.
                while index < len(pending):
                    checkpoint()
                    part, instance = pending[index]
                    if (part.id in blocked or sheet.material != part.material
                            or abs(sheet.thickness-part.thickness) > 1e-7):
                        index += 1; continue
                    point = candidate(part, sheet, previous)
                    if point:
                        _, x, y, angle = point
                        p = Placement(part.id, instance, sheet.id, number, x, y, angle)
                        placements.append(p); previous.append(p); pending.pop(index)
                        if progress:
                            progress(min(99, int(100*(time.monotonic()-started)/o.seconds)),
                                     f'{trial+1}. yerleşim denemesi · {len(sheets)}. plaka · {len(placements)}/{len(order)} parça')
                    else:
                        blocked.add(part.id); index += 1
                if progress:
                    progress(min(99, int(100*(time.monotonic()-started)/o.seconds)),
                             f'{len(sheets)}. plaka tamamlandı · {len(previous)} parça · {len(pending)} bekliyor')
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
