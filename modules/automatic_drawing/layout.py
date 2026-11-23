"""Deterministic sheet-space layout. Geometry, labels and title strip are separate."""

from dataclasses import replace
from itertools import combinations

from .models import Box, PAPERS, SheetPlan, finite


class LayoutError(ValueError):
    pass


def usable_area(width, height, options):
    margin, title = options.margin_mm, options.title_height_mm
    usable_width, usable_height = width-2*margin, height-2*margin-title
    if usable_width <= 0 or usable_height <= 0:
        raise ValueError('Kenar boşluğu ve antet paftada görünüş alanı bırakmıyor.')
    return Box(margin, margin+title, usable_width, usable_height)


def arrange(views, scale, area, options, *, measured=None, positions=None):
    """Aligned 2x2 orthographic group, with native anchor offsets when available.

    First angle: top BELOW main, right-side view LEFT of main.
    Third angle: top ABOVE main, right-side view RIGHT of main.
    """
    roles = {v.role: v for v in views}
    if not views or len(roles) != len(views):
        raise ValueError('Yerleşim için benzersiz görünüşler gerekli.')
    if len(views) > 1 and 'main' not in roles:
        raise ValueError('Ana görünüş olmadan izdüşüm yerleşimi yapılamaz.')
    pad, gap = options.annotation_padding_mm, options.gap_mm
    local = {}
    for role, view in roles.items():
        if measured and role in measured:
            box = measured[role]
            # Text can extend on only one side of a view. Its union's centre
            # is not the native IView.Position used for projection alignment.
            origin = positions[role] if positions is not None else box.center
            box = box.shifted(-origin[0], -origin[1])
        else:
            own = view.derived.scale if view.derived and view.derived.scale else scale
            width, height = (v*own for v in view.footprint)
            box = Box(-width/2, -height/2, width, height)
        local[role] = box.grow(pad)
    centers = {views[0].role if len(views) == 1 else 'main': (0., 0.)}
    sign = -1 if options.projection == 'first' else 1

    def separation(first, second, axis):
        if axis == 0:
            return first.right-second.x+gap if sign > 0 else first.x-second.right-gap
        return first.top-second.y+gap if sign > 0 else first.y-second.top-gap

    if len(views) > 1 and 'side' in roles:
        centers['side'] = (separation(local['main'], local['side'], 0), 0.)
    if len(views) > 1 and 'top' in roles:
        distance = separation(local['main'], local['top'], 1)
        if 'side' in centers:
            side = local['side'].shifted(*centers['side'])
            if side.overlaps(local['top'].shifted(0., distance), gap):
                distance = sign*max(sign*distance, sign*separation(side, local['top'], 1))
        centers['top'] = (0., distance)
    if len(views) > 1 and 'isometric' in roles:
        iso = local['isometric']
        dx = sign*max([sign*centers.get('side', (0., 0.))[0]]+
                      [sign*separation(local[r].shifted(*centers[r]), iso, 0)
                       for r in ('main', 'top') if r in centers])
        dy = sign*max([sign*centers.get('top', (0., 0.))[1]]+
                      [sign*separation(local[r].shifted(*centers[r]), iso, 1)
                       for r in ('main', 'side') if r in centers])
        centers['isometric'] = (dx, dy)
    for role in ('section', 'detail'):
        if role not in roles:
            continue
        axis = roles[role].derived.offset_axis
        occupied = [local[r].shifted(*center) for r, center in centers.items()]
        own = local[role]
        if role == 'section':
            distance = sign*max(sign*separation(other, own, axis) for other in occupied)
        else:
            # A free-positioned detail goes opposite the orthographic group.
            distance = (min(b.x for b in occupied)-own.right-gap if sign > 0 else
                        max(b.right for b in occupied)-own.x+gap)
        centers[role] = (distance, 0.) if axis == 0 else (0., distance)
    boxes = {r: local[r].shifted(*c) for r, c in centers.items()}
    left, right = min(b.x for b in boxes.values()), max(b.right for b in boxes.values())
    bottom, top = min(b.y for b in boxes.values()), max(b.top for b in boxes.values())
    if right-left > area.width+.001 or top-bottom > area.height+.001:
        return None
    if any(a.overlaps(b) for a, b in combinations(boxes.values(), 2)):
        return None
    dx, dy = area.center[0]-(left+right)/2, area.center[1]-(bottom+top)/2
    return [replace(view, center=(centers[view.role][0]+dx, centers[view.role][1]+dy))
            for view in views]


ISO_STEP = 5.  # an isometric on its own scale is at most 5 × smaller than the sheet; else its own sheet
FILL = .4     # automatic paper: the smallest sheet whose main view spans at least 40 % of its width or height
OFFICE = ('A4', 'A3')   # when no sheet reaches FILL (small parts), stay on these rather than a big sheet


def fill(plan):
    """Share of the usable width or height (the larger) the main view takes at its scale."""
    main = next((v for v in plan.views if v.role == 'main'), plan.views[0])
    scale = plan.view_scales.get(main.role, plan.scale)
    return max(main.footprint[0]*scale/plan.usable.width, main.footprint[1]*scale/plan.usable.height)


def _best_on(views, options, paper, name):
    """Largest sheet scale for the orthographic views on ``paper``; the isometric may step down on its own."""
    width, height = ((options.custom_width_mm, options.custom_height_mm)
                     if paper == 'custom' else PAPERS[paper])
    try:
        area = usable_area(width, height, options)
    except ValueError:      # margins + title leave no room on this sheet (Codex, e54f50b)
        if options.paper == 'auto':
            return None
        raise
    preferred = tuple(sorted(set(float(v) for v in options.scales), reverse=True))
    scales = (options.manual_scale,) if options.manual_scale is not None else preferred
    isometric = any(v.role == 'isometric' for v in views) and len(views) > 1
    for scale in scales:
        own = [scale]+([s for s in preferred if scale/ISO_STEP-1e-12 <= s < scale] if isometric else [])
        for iso in own:
            own_scales = {v.role: v.derived.scale for v in views if v.derived and v.derived.scale}
            if iso != scale:
                own_scales['isometric'] = iso
            measured = {v.role: Box(0, 0, v.footprint[0]*own_scales.get(v.role, scale),
                                    v.footprint[1]*own_scales.get(v.role, scale)) for v in views}
            arranged = arrange(views, scale, area, options, measured=measured)
            if arranged is not None:
                return SheetPlan(name, paper, width, height, scale, arranged, area, own_scales)
    return None


def plan_sheet(views, options, name='Genel görünüşler'):
    """Orthographic views at the largest scale that fits; an isometric that would pull them down
    gets its own, smaller scale instead. Automatic paper: the smallest sheet whose main view is large enough (FILL)."""
    options.validate()
    papers = tuple(PAPERS) if options.paper == 'auto' else (options.paper,)
    plans = [plan for paper in papers for plan in (_best_on(views, options, paper, name),) if plan is not None]
    if plans:
        # Sheets above A3 are for large parts: never to enlarge a small one (scale > 1:1).
        plans = [plan for plan in plans if plan.paper in OFFICE or plan.scale <= 1.] or plans
        enough = next((plan for plan in plans if fill(plan) >= FILL), None)
        if enough is not None:
            return enough
        office = [plan for plan in plans if plan.paper in OFFICE] or plans
        return max(office, key=fill)
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


def plan_drawing(info, options):
    """Shared draft/generator plan. Keep every cut with its parent view."""
    from .rules import derived_views, plan_views
    plans = plan_sheets(plan_views(info, options), options)
    general = plans[0]
    base = next(v for v in general.views if v.role == 'main')
    deferred = []
    for derived in derived_views(info, base, general.scale):
        fixed = replace(options, manual_scale=general.scale)
        together = _best_on([*general.views, derived], fixed, general.paper, general.name)
        if together is not None:
            general = plans[0] = together
            continue
        name = 'Kesit A-A' if derived.role == 'section' else 'Detay B'
        try:
            plans.append(plan_sheet([base, derived], options, name))
        except LayoutError:
            deferred.append(name)
    return plans, deferred


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


def crosses_box(start, end, box):
    """Clip a leader segment against the interior of an annotation rectangle."""
    lower, upper = 0., 1.
    for a, b, lo, hi in zip(start, end, (box.x, box.y), (box.right, box.top)):
        delta = b-a
        if abs(delta) < 1e-9:
            if not lo < a < hi:
                return False
            continue
        t0, t1 = sorted(((lo-a)/delta, (hi-a)/delta))
        lower, upper = max(lower, t0), min(upper, t1)
        if lower >= upper:
            return False
    return True


def place_texts(records, outlines, area, *, obstacle_boxes=(), obstacle_leaders=(), lanes=20, offset=7.):
    """Move only annotation text, retain its native references and dimension value.

    Bounded greedy search keeps close-to-view positions. Unknown text bounds are
    never claimed to fit. Final native rereading is required after applying moves.
    """
    occupied = list(obstacle_boxes)
    moves, unresolved = {}, []
    for key, owner, box in sorted(records, key=lambda record: (
            record[1], record[2].x if record[2] else 0., record[2].y if record[2] else 0.)):
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
        # If the starting axis itself is blocked by another view, shift along
        # the first lane in equal steps before leaving the view's vicinity.
        for step in range(1, lanes+1):
            for shift in (-offset*step, offset*step):
                candidates.extend((Box(box.x+shift, view.top+offset, box.width, box.height),
                                   Box(box.x+shift, view.y-offset-box.height, box.width, box.height),
                                   Box(view.x-offset-box.width, box.y+shift, box.width, box.height),
                                   Box(view.right+offset, box.y+shift, box.width, box.height)))
        selected = next((b for b in candidates if area.contains(b) and
                         not any(b.overlaps(v, .8) for v in outlines.values()) and
                         not any(b.overlaps(v, .8) for v in occupied) and
                         not any(crosses_box(*line, b) for line in obstacle_leaders)), None)
        if selected is None:
            unresolved.append(key)
            occupied.append(box)
        else:
            occupied.append(selected)
            if selected != box:
                moves[key] = selected.x-box.x, selected.y-box.y
    return moves, unresolved
