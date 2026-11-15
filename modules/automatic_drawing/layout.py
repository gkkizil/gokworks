"""Deterministic sheet-space layout. Geometry, labels and title strip are separate."""

from dataclasses import replace
from itertools import combinations

from .models import Box, PAPERS, SheetPlan, finite


class LayoutError(ValueError):
    pass


def usable_area(width, height, options):
    margin, title = options.margin_mm, options.title_height_mm
    area = Box(margin, margin+title, width-2*margin, height-2*margin-title)
    if area.width <= 0 or area.height <= 0:
        raise ValueError('Kenar boşluğu ve antet paftada görünüş alanı bırakmıyor.')
    return area


def arrange(views, scale, area, options, *, measured=None):
    """Aligned 2x2 orthographic group, with native anchor offsets when available.

    First angle: top BELOW main, right-side view LEFT of main.
    Third angle: top ABOVE main, right-side view RIGHT of main.
    """
    roles = {v.role: v for v in views}
    if len(views) == 1:
        view = views[0]
        size = ((measured[view.role].width, measured[view.role].height)
                if measured and view.role in measured else
                (view.footprint[0]*scale, view.footprint[1]*scale))
        pad = options.annotation_padding_mm
        if size[0]+2*pad <= area.width and size[1]+2*pad <= area.height:
            return [replace(view, center=area.center)]
        return None
    if 'main' not in roles:
        raise ValueError('Ana görünüş olmadan izdüşüm yerleşimi yapılamaz.')
    pad, gap = options.annotation_padding_mm, options.gap_mm
    sizes = {role: ((measured[role].width, measured[role].height)
                    if measured and role in measured else
                    (view.footprint[0]*scale, view.footprint[1]*scale))
             for role, view in roles.items()}
    centers = {'main': (0., 0.)}
    if 'side' in roles:
        distance = (sizes['main'][0]+sizes['side'][0])/2 + 2*pad + gap
        centers['side'] = ((-1 if options.projection == 'first' else 1)*distance, 0.)
    if 'top' in roles:
        distance = (sizes['main'][1]+sizes['top'][1])/2 + 2*pad + gap
        centers['top'] = (0., (-1 if options.projection == 'first' else 1)*distance)
    if 'isometric' in roles:
        dx = max((sizes['main'][0]+sizes['isometric'][0])/2+2*pad+gap,
                 abs(centers.get('side', (0., 0.))[0]))
        dy = max((sizes['main'][1]+sizes['isometric'][1])/2+2*pad+gap,
                 abs(centers.get('top', (0., 0.))[1]))
        centers['isometric'] = ((-1 if options.projection == 'first' else 1)*dx,
                                (-1 if options.projection == 'first' else 1)*dy)
    boxes = {r: Box(c[0]-sizes[r][0]/2-pad, c[1]-sizes[r][1]/2-pad,
                    sizes[r][0]+2*pad, sizes[r][1]+2*pad)
             for r, c in centers.items()}
    left, right = min(b.x for b in boxes.values()), max(b.right for b in boxes.values())
    bottom, top = min(b.y for b in boxes.values()), max(b.top for b in boxes.values())
    if right-left > area.width+.001 or top-bottom > area.height+.001:
        return None
    if any(a.overlaps(b) for a, b in combinations(boxes.values(), 2)):
        return None
    dx, dy = area.center[0]-(left+right)/2, area.center[1]-(bottom+top)/2
    return [replace(view, center=(centers[view.role][0]+dx, centers[view.role][1]+dy))
            for view in views]


def plan_sheet(views, options, name='Genel görünüşler'):
    options.validate()
    scales = (options.manual_scale,) if options.manual_scale is not None else tuple(
        sorted(set(float(v) for v in options.scales), reverse=True))
    papers = tuple(PAPERS) if options.paper == 'auto' else (options.paper,)
    for paper in papers:
        width, height = ((options.custom_width_mm, options.custom_height_mm)
                         if paper == 'custom' else PAPERS[paper])
        area = usable_area(width, height, options)
        for scale in scales:
            arranged = arrange(views, scale, area, options)
            if arranged is not None:
                return SheetPlan(name, paper, width, height, scale, arranged, area)
    raise LayoutError('Görünüşler seçilen pafta ve ölçeklere okunaklı biçimde sığmıyor. '
                     'Daha büyük pafta seçin, ek görünüşleri azaltın veya ölçek listesini genişletin.')


def plan_sheets(views, options):
    """Keep related orthographic views together; spill independent isometry."""
    try:
        return [plan_sheet(views, options)]
    except LayoutError:
        separate = [view for view in views if view.role == 'isometric']
        orthographic = [view for view in views if view.role != 'isometric']
        if not separate or not orthographic:
            raise
        return [plan_sheet(orthographic, options),
                plan_sheet(separate, options, 'İzometrik görünüş')]


def union(boxes):
    boxes = list(boxes)
    if not boxes:
        return None
    x, y = min(b.x for b in boxes), min(b.y for b in boxes)
    return Box(x, y, max(b.right for b in boxes)-x, max(b.top for b in boxes)-y)


def text_box(x, y, width, height, angle):
    """Axis-aligned envelope of a native text run, including rotated dimensions."""
    import math
    for value in (x, y, width, height, angle):
        finite(value, 'Anotasyon geometrisi')
    if width <= 0 or height <= 0:
        raise ValueError('Anotasyon metni genişlik/yüksekliği okunamadı.')
    ca, sa = math.cos(angle), math.sin(angle)
    points = [(x+a*ca-b*sa, y+a*sa+b*ca) for a, b in
              ((0., 0.), (width, 0.), (0., height), (width, height))]
    left, bottom = min(p[0] for p in points), min(p[1] for p in points)
    return Box(left, bottom, max(p[0] for p in points)-left, max(p[1] for p in points)-bottom)


def place_texts(records, outlines, area, *, obstacle_boxes=(), lanes=20, offset=7.):
    """Move only annotation text, retain its native references and dimension value.

    Bounded greedy search keeps close-to-view positions. Unknown text bounds are
    never claimed to fit. Final native rereading is required after applying moves.
    """
    occupied = list(obstacle_boxes)
    moves, unresolved = {}, []
    for key, owner, box in records:
        if box is None or owner not in outlines:
            unresolved.append(key)
            continue
        view = outlines[owner]
        candidates = [box]
        for lane in range(1, lanes+1):
            distance = offset*lane
            candidates.extend((Box(box.x, view.top+distance, box.width, box.height),
                               Box(box.x, view.y-distance-box.height, box.width, box.height),
                               Box(view.x-distance-box.width, box.y, box.width, box.height),
                               Box(view.right+distance, box.y, box.width, box.height)))
        selected = next((b for b in candidates if area.contains(b) and
                         not any(b.overlaps(v, .8) for v in outlines.values()) and
                         not any(b.overlaps(v, .8) for v in occupied)), None)
        if selected is None:
            unresolved.append(key)
            occupied.append(box)
        else:
            occupied.append(selected)
            if selected != box:
                moves[key] = selected.x-box.x, selected.y-box.y
    return moves, unresolved
