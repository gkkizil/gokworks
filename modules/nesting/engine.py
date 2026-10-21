"""True-contour NFP search: Minkowski obstacles + feasible translations + multistart.

Own Python implementation. No JavaScript/Node, C++ ABI or external executable.
It returns the best verified heuristic solution; mathematical optimality is not asserted.
"""

from collections import Counter
from datetime import datetime, timezone
import random
import time

from shapely import affinity, union_all
from shapely.geometry import box, Point, Polygon

from modules.nesting import ENGINE, ENGINE_VERSION
from modules.nesting.geometry import footprint, rotated, minkowski, convex_parts, polygons
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
    parts = {p.id:p for p in project.parts}
    budget_exhausted = False
    instances = [(p, i) for p in project.parts for i in range(1, p.quantity+1)]
    digest = project.fingerprint()

    def checkpoint():
        if (stop is not None and stop.is_set()) or time.monotonic() >= deadline:
            raise SearchEnded()

    def geometry(part, angle):
        key = (part.id, angle)
        if key not in rotated_cache:
            rotated_cache[key] = rotated(part, angle)
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

    def candidate(part, sheet, previous, *, detailed):
        angles = [0] if not o.rotation else o.angles
        if o.grain_locked or part.grain_locked:
            angles = [a for a in angles if abs(a % 180) < 1e-7]
        fixed = [(old, affinity.translate(geometry(parts[old.part_id],old.angle),old.x,old.y),
                  max(o.gap,o.kerf)+part.geometry_error+parts[old.part_id].geometry_error)
                 for old in previous]
        holes = [(Polygon(ring),distance) for _,shape,distance in fixed
                 for polygon in polygons(shape) for ring in polygon.interiors]
        # Test simple edge/corner placements for every rotation before paying
        # for an NFP. Bounds generate candidates; exact contours approve them.
        # The first complete pass never waits on convex decomposition, so one
        # detailed contour cannot consume the budget before the other parts.
        winner = None
        for precise in ((False,True) if detailed and previous else (False,)):
            for angle in angles:
                checkpoint()
                g = geometry(part, angle); x0, y0, x1, y1 = g.bounds
                margin = o.margin+part.geometry_error+o.kerf/2
                left, bottom = margin-x0, margin-y0
                right, top = sheet.width-margin-x1, sheet.height-margin-y1
                if right < left-1e-7 or top < bottom-1e-7:
                    continue
                points = {(left,bottom),(right,bottom),(left,top),(right,top)}
                usable_holes = []
                for hole,distance in holes:
                    checkpoint()
                    a,b,c,d = hole.bounds
                    clearance = distance+2e-6 if distance else 0
                    low_x,high_x = a+clearance-x0,c-clearance-x1
                    low_y,high_y = b+clearance-y0,d-clearance-y1
                    if high_x < low_x-1e-7 or high_y < low_y-1e-7:
                        continue
                    usable_holes.append(hole)
                    fractions = (0,.5,1) if hole.equals(hole.envelope) else tuple(i/6 for i in range(7))
                    xs = tuple(low_x+(high_x-low_x)*f for f in fractions)
                    ys = tuple(low_y+(high_y-low_y)*f for f in fractions)
                    points.update((x,y) for x in xs for y in ys)
                    # Retain fast placements for several parts within one hole.
                    # These are only proposals: the curved/concave material and
                    # every other part are still checked below at full precision.
                    for _,neighbor,gap in fixed:
                        checkpoint()
                        u,v,w,z = neighbor.bounds
                        if w<a or u>c or z<b or v>d:
                            continue
                        pad = gap+2e-6 if gap else 0
                        points.update((x,y) for x in (*xs,u-x0,w-x1)
                                      for y in (z+pad-y0,v-pad-y1))
                        points.update((x,y) for x in (w+pad-x0,u-pad-x1)
                                      for y in (*ys,v-y0,z-y1))
                if precise:
                    # Exact-fit translation domains can be lines or points.
                    if abs(right-left)<1e-7 and abs(top-bottom)<1e-7:
                        feasible = Point(left,bottom)
                    elif abs(right-left)<1e-7 or abs(top-bottom)<1e-7:
                        from shapely.geometry import LineString
                        feasible = LineString([(left,bottom),(right,top)])
                    else:
                        feasible = box(left,bottom,right,top)
                    obstacles = []
                    for old,_,_ in fixed:
                        checkpoint()
                        obstacles.append(affinity.translate(nfp(parts[old.part_id],old.angle,part,angle),old.x,old.y))
                    forbidden = union_all(obstacles)
                    points.update(_vertices(forbidden.intersection(feasible)))
                    points.update(_vertices(feasible.difference(forbidden)))
                else:
                    for _,shape,distance in fixed:
                        a,b,c,d = shape.bounds
                        clearance = distance+2e-6 if distance else 0
                        above,below = d+clearance-y0,b-clearance-y1
                        after,before = c+clearance-x0,a-clearance-x1
                        points.update((x,y) for x in (left,right,a-x0,c-x1) for y in (above,below))
                        points.update((x,y) for x in (after,before) for y in (bottom,top,b-y0,d-y1))
                ordered = sorted(points,key=lambda xy:(xy[1],xy[0]))
                for want_hole in ((True,False) if usable_holes else (False,)):
                    found = False
                    for x,y in ordered:
                        checkpoint()
                        if not (left-1e-7<=x<=right+1e-7 and bottom-1e-7<=y<=top+1e-7):
                            continue
                        translated = affinity.translate(g,x,y)
                        inside = any(hole.covers(translated) for hole in usable_holes)
                        if inside != want_hole:
                            continue
                        if any(translated.intersection(shape).area>1e-6 or translated.distance(shape)+1e-6<distance
                               for _,shape,distance in fixed):
                            continue
                        score = (0 if inside else 1,y+y1,x+x1,angle)
                        if winner is None or score<winner[0]:
                            winner = (score,x,y,angle)
                        found = True
                        break
                    if found:
                        break
        return winner

    max_trials = {'Hızlı': 3, 'Dengeli': 12, 'Yüksek': 40}[o.quality]
    for trial in range(max_trials+1):
        placements = []; remaining = []; sheets = []; counts = Counter()
        # Perforated/thin frames must precede small solid inserts: net material
        # area alone can otherwise put the intended insert on the sheet first.
        outer_areas = {p.id:footprint(p.polygon).area for p in project.parts}
        order = sorted(instances, key=lambda item: (outer_areas.get(item[0].id,item[0].area),item[0].area), reverse=True)
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
                    point = candidate(part, sheet, [], detailed=trial>0)
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
                    point = candidate(part, sheet, previous, detailed=trial>0)
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
            budget_exhausted = time.monotonic() >= deadline
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
    result.timed_out = budget_exhausted and not result.stopped
    validate_result(project, result, complete=False)
    if progress:
        progress(100, f'Kontrol tamamlandı · {len(result.placements)} yerleşti · {len(result.unplaced)} yerleşmedi')
    return result
