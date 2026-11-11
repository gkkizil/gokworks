"""Transactional finite-stock repairs around a verified Sparrow layout.

Sparrow optimizes an infinite strip. These repairs optimize physical plates:
evacuate either direction, rebuild obstructed layouts, then use smaller stock.
Only complete drafts are committed; the caller owns geometry and time limits.
"""
from collections import Counter
from dataclasses import replace


def refine_stock(project, plates, place, bounds, checkpoint, commit):
    parts = {p.id:p for p in project.parts}
    metrics = {}

    def metric(row):
        if row.part_id not in metrics:
            shape = parts[row.part_id].polygon
            from .geometry import footprint
            x0,y0,x1,y1 = shape.bounds
            metrics[row.part_id] = (footprint(shape).area,shape.area,max(x1-x0,y1-y0))
        return metrics[row.part_id]

    def area(plate): return plate[0].width*plate[0].height
    def net(rows): return sum(metric(p)[1] for p in rows)
    def compatible(row, sheet):
        p = parts[row.part_id]
        return p.material==sheet.material and abs(p.thickness-sheet.thickness)<=1e-7

    def normalize(draft):
        counts = Counter(); normalized = []
        for sheet,_,rows in draft:
            if not rows: continue
            counts[sheet.id] += 1; number = counts[sheet.id]
            normalized.append((sheet,number,[replace(p,sheet_id=sheet.id,sheet_number=number) for p in rows]))
        return normalized

    def accept(draft):
        nonlocal plates
        # No original placement/list is mutated, including during renumbering.
        plates = normalize(draft)
        commit(plates)

    def insert(rows, targets, precise):
        draft = [(s,n,list(previous)) for s,n,previous in targets]
        for old in rows:
            checkpoint()
            # More free material area is only a search order, never a fit test.
            choices = sorted(range(len(draft)),key=lambda i:area(draft[i])-net(draft[i][2]),reverse=True)
            for i in choices:
                sheet,number,previous = draft[i]
                if not compatible(old,sheet): continue
                point = place(parts[old.part_id],sheet,previous,precise)
                if point is not None:
                    x,y,angle = point
                    previous.append(replace(old,sheet_id=sheet.id,sheet_number=number,x=x,y=y,angle=angle))
                    break
            else:
                return None
        return draft

    def rebuild(rows, targets):
        orders = [sorted(rows,key=lambda p:(metric(p)[0],metric(p)[1]),reverse=True),
                  sorted(rows,key=lambda p:(metric(p)[2],metric(p)[0]),reverse=True)]
        unique = []; seen = set()
        for order in orders:
            key = tuple((p.part_id,p.instance) for p in order)
            if key not in seen: unique.append(order); seen.add(key)
        empty = [(s,n,[]) for s,n,_ in targets]
        for precise in (False,True):
            for order in unique:
                checkpoint()
                draft = insert(order,empty,precise)
                if draft is not None: return draft
        return None

    failed = set()
    while len(plates)>1:
        changed = False
        order = sorted(range(len(plates)),key=lambda i:(net(plates[i][2])/area(plates[i]),len(plates[i][2])))
        for source_index in order:
            checkpoint()
            if source_index in failed: continue
            source = plates[source_index]
            indices = [i for i,p in enumerate(plates) if i!=source_index
                       and any(compatible(row,p[0]) for row in source[2])]
            targets = [plates[i] for i in indices]
            pool = source[2]+[p for _,_,rows in targets for p in rows]
            # An admissible area rejection; holes remain subtracted, not filled.
            if not targets or net(pool)>sum(area(p) for p in targets)+1e-6:
                failed.add(source_index); continue
            draft = insert(sorted(source[2],key=metric,reverse=True),targets,False)
            if draft is None: draft = rebuild(pool,targets)
            if draft is None:
                failed.add(source_index); continue
            replacements = dict(zip(indices,draft))
            accept([replacements.get(i,p) for i,p in enumerate(plates) if i!=source_index])
            failed.clear(); changed = True
            break
        if not changed: break

    for index in range(len(plates)):
        checkpoint(); source = plates[index]
        used = Counter(p[0].id for p in plates)
        choices = sorted((s for s in project.sheets if used[s.id]<s.stock
                          and s.width*s.height<area(source)-1e-6
                          and net(source[2])<=s.width*s.height+1e-6
                          and all(compatible(p,s) for p in source[2])),key=lambda s:s.width*s.height)
        for sheet in choices:
            checkpoint()
            edge = project.options.margin+project.options.kerf/2
            largest_error = max(parts[p.part_id].geometry_error for p in source[2])
            extents = [(p,bounds(p.part_id,p.angle)) for p in source[2]]
            dx = edge+largest_error-min(p.x+b[0] for p,b in extents)
            dy = edge+largest_error-min(p.y+b[1] for p,b in extents)
            shifted = [replace(p,x=p.x+dx,y=p.y+dy) for p in source[2]]
            # A rigid translation preserves all original gaps, angles and holes.
            fits = all(edge+parts[p.part_id].geometry_error-1e-7<=p.x+b[0]
                       and edge+parts[p.part_id].geometry_error-1e-7<=p.y+b[1]
                       and p.x+b[2]<=sheet.width-edge-parts[p.part_id].geometry_error+1e-7
                       and p.y+b[3]<=sheet.height-edge-parts[p.part_id].geometry_error+1e-7
                       for p,(_,b) in zip(shifted,extents))
            draft = [(sheet,1,shifted)] if fits else rebuild(source[2],[(sheet,1,[])])
            if draft is not None:
                accept(plates[:index]+draft+plates[index+1:])
                break
    return plates,Counter(p[0].id for p in plates)
