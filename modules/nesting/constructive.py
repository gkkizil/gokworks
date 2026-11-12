"""Bounded MaxRects competitors for a Sparrow seed; original contours stay exact.

Rectangles are conservative proposals, never a proof of infeasibility. A
portfolio varies fit rule, order, stock preference and packing axis. All wins
pass the independent contour validator before becoming an incumbent.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import random
import time

from shapely import affinity

from . import ENGINE, ENGINE_VERSION
from .layout_score import layout_score
from .models import Placement, Result
from .rotations import search_angles
from .validation import validate_result


class _Ended(Exception):
    pass


def _split(free, used, checkpoint):
    """Maximal empty rectangles may overlap; remove all occupied intersections."""
    x,y,right,top = used
    pieces = []
    for left,bottom,r,t in free:
        checkpoint()
        if right <= left or r <= x or top <= bottom or t <= y:
            pieces.append((left,bottom,r,t)); continue
        if left < x: pieces.append((left,bottom,x,t))
        if right < r: pieces.append((right,bottom,r,t))
        if bottom < y: pieces.append((left,bottom,r,y))
        if top < t: pieces.append((left,top,r,t))
    # Containment pruning is essential: unpruned overlapping slots grow rapidly.
    pieces = list(dict.fromkeys(pieces)); result = []
    for i,a in enumerate(pieces):
        checkpoint()
        contained = False
        for j,b in enumerate(pieces):
            if j % 64 == 0: checkpoint()
            if i != j and b[0] <= a[0] and b[1] <= a[1] and a[2] <= b[2] and a[3] <= b[3]:
                contained = True; break
        if not contained: result.append(a)
    return result


def nest(project, *, deadline, initial=None, stop=None, progress=None):
    """Use only the caller's remaining budget; retain the best partial on cancel."""
    project.validate()
    started = time.monotonic(); digest = project.fingerprint(); o = project.options
    best = deepcopy(initial) if initial is not None else Result(
        digest,[],[p.id for p in project.parts for _ in range(p.quantity)],
        ENGINE,ENGINE_VERSION,0.,0,datetime.now(timezone.utc).isoformat())
    validate_result(project,best,complete=False)
    best_score = layout_score(project,best); attempts = 0; shapes = {}; orientations = {}
    gap = max(o.gap,o.kerf); edge = o.margin+o.kerf/2
    instances = [(p,i) for p in project.parts for i in range(1,p.quantity+1)]
    rng = random.Random(o.seed)

    def checkpoint():
        if (stop is not None and stop.is_set()) or time.monotonic() >= deadline:
            raise _Ended()

    def variants(part):
        if part.id not in orientations:
            checkpoint()
            shape = part.polygon; shapes[part.id] = shape
            angles = search_angles(part,o)
            # Proposals only: leave exhaustive/free-angle work to Sparrow/NFP.
            if len(angles) > 16 and o.angles is not None:
                selected = {min(angles,key=lambda a:abs((a-360*i/16+180)%360-180)) for i in range(16)}
                angles = [a for a in angles if a in selected]
            angles = angles[:16]
            padding = gap/2+part.geometry_error
            rows = []; seen = set()
            for angle in angles:
                checkpoint()
                a,b,c,d = affinity.rotate(shape,angle,origin=(0,0)).bounds
                key = (round(c-a,9),round(d-b,9))
                if key in seen: continue
                seen.add(key)
                rows.append((c-a+2*padding,d-b+2*padding,angle,a,b,padding))
            orientations[part.id] = rows
        return orientations[part.id]

    def position(part, free, rule, along_y):
        winner = None
        for width,height,angle,x0,y0,padding in variants(part):
            for left,bottom,right,top in free:
                checkpoint()
                dw,dh = right-left-width,top-bottom-height
                if dw < 0 or dh < 0: continue
                short,long = min(dw,dh),max(dw,dh)
                area = (right-left)*(top-bottom)-width*height
                corner = (left+width,bottom+height) if along_y else (bottom+height,left+width)
                key = ((area,short,long) if rule == 'area' else
                       (*corner,short,area) if rule == 'bottom' else (short,long,area))
                key = (*key,*corner,angle)
                if winner is None or key < winner[0]:
                    winner = (key,left+padding-x0,bottom+padding-y0,angle,
                              (left,bottom,left+width,bottom+height))
        return winner

    # Different constructive basins, rather than repeating one greedy ordering.
    plans = [('area','short',False,False),('long','area',True,True),
             ('short','short',False,True),('area','bottom',True,False),
             ('long','bottom',False,False),('area','area',True,True),
             ('noise','short',False,True),('noise','area',True,False)]
    plans = plans[:{'Hızlı':4,'Dengeli':6,'Yüksek':8}[o.quality]]
    for ordering,rule,small_first,along_y in plans:
        rows = []; counts = Counter(); stopped = False
        try:
            checkpoint()
            metrics = {}
            for part in project.parts:
                checkpoint()
                if part.id not in shapes: variants(part)
                a,b,c,d = shapes[part.id].bounds
                metrics[part.id] = ((c-a)*(d-b),max(c-a,d-b),min(c-a,d-b),rng.random())
            def rank(item):
                area,long,short,noise = metrics[item[0].id]
                return ((long,area) if ordering == 'long' else (short,area) if ordering == 'short'
                        else (area*(.75+.5*noise),long) if ordering == 'noise' else (area,long))
            pending = sorted(instances,key=rank,reverse=True)
            while pending:
                checkpoint()
                part,instance = pending.pop(0)
                choices = sorted((s for s in project.sheets if s.material == part.material
                    and abs(s.thickness-part.thickness) <= 1e-7 and counts[s.id] < s.stock),
                    key=lambda s:s.width*s.height,reverse=not small_first)
                opening = None
                for sheet in choices:
                    checkpoint()
                    free = [(edge-gap/2,edge-gap/2,sheet.width-edge+gap/2,sheet.height-edge+gap/2)]
                    point = position(part,free,rule,along_y)
                    if point is not None:
                        opening = (sheet,free,point); break
                if opening is None: continue
                sheet,free,point = opening; counts[sheet.id] += 1
                def add(part,instance,point):
                    nonlocal free
                    _,x,y,angle,used = point
                    # Finish the free-space transaction before recording a pose.
                    next_free = _split(free,used,checkpoint)
                    rows.append(Placement(part.id,instance,sheet.id,counts[sheet.id],x,y,angle))
                    free = next_free
                add(part,instance,point)
                blocked = set(); index = 0
                while index < len(pending):
                    checkpoint()
                    part,instance = pending[index]
                    if (part.id in blocked or part.material != sheet.material
                            or abs(part.thickness-sheet.thickness) > 1e-7):
                        index += 1; continue
                    point = position(part,free,rule,along_y)
                    if point is None:
                        blocked.add(part.id); index += 1
                    else:
                        add(part,instance,point); pending.pop(index)
        except _Ended:
            stopped = True
        attempts += 1
        used = {(p.part_id,p.instance) for p in rows}
        draft = Result(digest,rows,[p.id for p,i in instances if (p.id,i) not in used],
                       ENGINE,ENGINE_VERSION,0.,attempts,datetime.now(timezone.utc).isoformat())
        score = layout_score(project,draft)
        if score < best_score:
            validate_result(project,draft,complete=False)
            best,best_score = draft,score
            if progress: progress(min(99,100*attempts/len(plans)),f'MaxRects · {len(rows)} parça · {score[1]} plaka')
        if stopped: break
    best.iterations = attempts
    best.elapsed = time.monotonic()-started
    best.stopped = stop is not None and stop.is_set()
    best.timed_out = not best.stopped and time.monotonic() >= deadline
    validate_result(project,best,complete=False)
    return best
