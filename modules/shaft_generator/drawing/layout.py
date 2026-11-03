"""Deterministic sheet, scale, view and annotation placement (sheet millimetres).

The planner gives each annotation an anchor along the shaft axis; this module
chooses tiers/positions so text boxes do not overlap, keeps the title block
free and reports anything it cannot place instead of hiding it. SOLIDWORKS maps
the results through each view's real transform and outline, then re-checks.
"""

from dataclasses import dataclass, field
from .models import SHEET_SIZES

# ISO 5455 preferred scales (enlargement and reduction), as (numerator, denominator).
SCALES = ((10, 1), (5, 1), (2, 1), (1, 1), (1, 2), (1, 5), (1, 10), (1, 20))
TEXT_HEIGHT = 3.5          # mm on paper (ISO 3098 / ISO 129-1 common size)
CHAR_WIDTH = .62 * TEXT_HEIGHT
TIER = 8.                  # spacing between dimension lines
FIRST_TIER = 10.           # first dimension line from the view outline
BORDER = (20., 10., 10., 10.)   # left (binding), right, top, bottom — ISO 5457
TITLE_BLOCK = (180., 56.)       # ISO 7200 field reserve, bottom-right
GAP = 18.                  # free space between views
MIN_FEATURE = 2.5          # smallest readable feature on paper before a detail view


@dataclass
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    def overlaps(self, other, margin=0.):
        return not (self.x1 + margin <= other.x0 or other.x1 + margin <= self.x0 or
                    self.y1 + margin <= other.y0 or other.y1 + margin <= self.y0)

    def inside(self, other):
        return self.x0 >= other.x0 - 1e-9 and self.y0 >= other.y0 - 1e-9 and self.x1 <= other.x1 + 1e-9 and self.y1 <= other.y1 + 1e-9


def text_width(text):
    return max(1, len(text)) * CHAR_WIDTH


@dataclass
class SheetChoice:
    size: str
    width: float
    height: float
    scale: tuple
    fits: bool
    note: str = ''

    @property
    def factor(self):
        return self.scale[0] / self.scale[1]

    def usable(self):
        left, right, top, bottom = BORDER
        return Box(left, bottom, self.width - right, self.height - top)

    def title_block(self):
        left, right, top, bottom = BORDER
        return Box(self.width - right - TITLE_BLOCK[0], bottom, self.width - right, bottom + TITLE_BLOCK[1])


def required_area(length, diameter, views, factor, tiers_below, tiers_above):
    """Paper width/height for the main view, its dimension bands and companion views."""
    main_w, main_h = length * factor, diameter * factor
    band_below = FIRST_TIER + tiers_below * TIER
    band_above = (FIRST_TIER + tiers_above * TIER) if tiers_above else 6.
    width = main_w + 2 * 14.
    height = main_h + band_below + band_above
    extra_w = 0.
    for view in views:
        if view in ('top',):
            height += GAP + diameter * factor + FIRST_TIER + 2 * TIER
        elif view.startswith('side') or view.startswith('section'):
            extra_w += GAP + diameter * factor + 2 * TIER
        elif view == 'iso':
            extra_w = max(extra_w, GAP + .9 * (length + diameter) * factor * .6)
    return width + extra_w, height


def choose_sheet(length, diameter, views, *, size='auto', scale_mode='auto', scale=(1, 1),
                 tiers_below=3, tiers_above=1, detail_views=0):
    """Smallest sheet / largest preferred scale whose usable area holds the drawing."""
    sizes = list(SHEET_SIZES) if size == 'auto' else [size]
    scales = SCALES if scale_mode == 'auto' else (tuple(scale),)
    detail_w = detail_views * (GAP + 45.)
    for name in sizes:
        w, h = SHEET_SIZES[name]
        choice = SheetChoice(name, w, h, (1, 1), False)
        usable, title = choice.usable(), choice.title_block()
        for candidate in scales:
            factor = candidate[0] / candidate[1]
            need_w, need_h = required_area(length, diameter, views, factor, tiers_below, tiers_above)
            need_w += detail_w
            # The title block occupies the lower-right corner: drawings may use
            # the full width above it, or the height beside it.
            fits = ((need_w <= usable.x1 - usable.x0 and need_h <= usable.y1 - title.y1) or
                    (need_w <= title.x0 - usable.x0 and need_h <= usable.y1 - usable.y0))
            if fits:
                return SheetChoice(name, w, h, candidate, True)
    # Nothing fits: report the largest requested sheet with the smallest scale.
    name = sizes[-1]; w, h = SHEET_SIZES[name]
    best = scales[-1]
    hint = ('Seçilen sayfa/ölçeğe sığmıyor; daha büyük sayfa veya küçük ölçek seçin.'
            if size != 'auto' or scale_mode != 'auto' else 'A0 ve 1:20 ölçekte bile sığmıyor.')
    return SheetChoice(name, w, h, tuple(best), False, hint)


@dataclass
class Placement:
    id: str
    view: str
    box: Box
    band: str
    tier: int
    x: float          # sheet x of the dimension line / text centre
    y: float


@dataclass
class Layout:
    sheet: SheetChoice
    views: dict
    placements: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)

    def as_dict(self):
        return dict(sheet=dict(size=self.sheet.size, width_mm=self.sheet.width, height_mm=self.sheet.height,
                               scale=list(self.sheet.scale), fits=self.sheet.fits, note=self.sheet.note,
                               title_block=_box(self.sheet.title_block())),
                    views={k: dict(v, box=_box(v['box'])) for k, v in self.views.items()},
                    placements={p.id: dict(view=p.view, band=p.band, tier=p.tier, x_mm=round(p.x, 4),
                                           y_mm=round(p.y, 4), box=_box(p.box)) for p in self.placements},
                    conflicts=list(self.conflicts))


def _box(box):
    return [round(box.x0, 4), round(box.y0, 4), round(box.x1, 4), round(box.y1, 4)]


def band_height(tiers, view, band, minimum=0):
    used = tiers.get((view, band), -1) + 1
    used = max(used, minimum)
    return FIRST_TIER + max(0, used - 1) * TIER + TEXT_HEIGHT * 1.5 if used else 4.


def place_views(sheet, length, diameter, views, projection, detail_ids=(), tiers=None):
    """Sheet boxes for each view; dimension bands are sized from the tiers they really use."""
    tiers = tiers if tiers is not None else {('main', 'below'): 3, ('main', 'above'): 2, ('top', 'above'): 1}
    f = sheet.factor
    usable, title = sheet.usable(), sheet.title_block()
    main_w, main_h = length * f, diameter * f
    has_top = 'top' in views
    top_h = diameter * f
    # Vertical stack: [top view (third angle)] main [top view (first angle)].
    below_main = band_height(tiers, 'main', 'below')
    above_main = band_height(tiers, 'main', 'above')
    above_top = band_height(tiers, 'top', 'above') if has_top else 0.
    below_top = band_height(tiers, 'top', 'below') if has_top else 0.
    stack_h = main_h + below_main + above_main + ((GAP + top_h + above_top + below_top) if has_top else 0)
    top_y = usable.y1 - max(4., (usable.y1 - max(usable.y0, title.y1) - stack_h) / 2)
    x0 = usable.x0 + 14.
    boxes = {}
    if has_top and projection == 'third':
        top_y -= above_top
        boxes['top'] = Box(x0, top_y - top_h, x0 + main_w, top_y)
        top_y -= top_h + below_top + GAP
    main_top = top_y - above_main
    boxes['main'] = Box(x0, main_top - main_h, x0 + main_w, main_top)
    if has_top and projection == 'first':
        y = boxes['main'].y0 - below_main - GAP - above_top
        boxes['top'] = Box(x0, y - top_h, x0 + main_w, y)
    # End views and sections to the right of the main view (first angle: a view
    # from the left is drawn on the right; third angle: view from the right).
    cursor = boxes['main'].x1 + GAP + 2 * TIER
    for view in views:
        if view.startswith('side') or view.startswith('section'):
            size = diameter * f
            cy = (boxes['main'].y0 + boxes['main'].y1) / 2
            boxes[view] = Box(cursor, cy - size / 2, cursor + size, cy + size / 2)
            cursor += size + GAP + 2 * TIER
    detail_y = (boxes['top'].y0 - below_top if 'top' in boxes and projection == 'first' else boxes['main'].y0 - below_main) - GAP
    detail_x = usable.x0 + 14.
    for view in detail_ids:
        boxes[view] = Box(detail_x, detail_y - 40., detail_x + 40., detail_y)
        detail_x += 40. + GAP
    if 'iso' in views:
        size = .45 * (length + diameter) * f
        boxes['iso'] = Box(usable.x1 - size, title.y1 + 8., usable.x1, title.y1 + 8. + size * .6)
    return {name: dict(box=box) for name, box in boxes.items()}


def place_annotations(sheet, views, annotations):
    """Assign tiers and positions; record every unresolved overlap.

    ``annotations`` items: dict(id, view, kind, text, x0_mm, x1_mm (axial span),
    band='above'|'below'|'inside', priority) in model millimetres along the axis.
    """
    f = sheet.factor
    title = sheet.title_block()
    usable = sheet.usable()
    placed, conflicts = [], []
    tiers = {}
    order = sorted(annotations, key=lambda a: (a['view'], a['band'], abs(a['x1_mm'] - a['x0_mm']), a['priority'], a['id']))
    for item in order:
        view = views[item['view']]['box']
        sx0 = view.x0 + item['x0_mm'] * f
        sx1 = view.x0 + item['x1_mm'] * f
        width = text_width(item['text'])
        if item['band'] == 'inside':
            # Vertical (diameter) dimensions: try positions along the span first.
            box = None
            span = max(sx1 - sx0, 0.)
            steps = max(1, int(span / (TEXT_HEIGHT * 1.5)))
            centre_y = (view.y0 + view.y1) / 2
            for k in range(steps + 1):
                for sign in (1, -1):
                    x = (sx0 + sx1) / 2 + sign * k * span / (2 * steps)
                    if not sx0 - 1e-9 <= x <= sx1 + 1e-9:
                        continue
                    candidate = Box(x - TEXT_HEIGHT * .8, centre_y - width / 2, x + TEXT_HEIGHT * .8, centre_y + width / 2)
                    if not any(candidate.overlaps(p.box, .5) for p in placed if p.band == 'inside' and p.view == item['view']):
                        box = candidate; break
                if box:
                    break
            if box is None:
                x = (sx0 + sx1) / 2
                box = Box(x - TEXT_HEIGHT * .8, centre_y - width / 2, x + TEXT_HEIGHT * .8, centre_y + width / 2)
                conflicts.append(f'{item["id"]}: çap ölçüsü kademe içinde diğer çap ölçüleriyle çakışıyor.')
            placed.append(Placement(item['id'], item['view'], box, 'inside', 0, (box.x0 + box.x1) / 2, centre_y))
            continue
        direction = -1 if item['band'] == 'below' else 1
        key = (item['view'], item['band'])
        tiers.setdefault(key, [])
        mid = (sx0 + sx1) / 2
        for tier in range(40):
            offset = FIRST_TIER + tier * TIER
            y = (view.y0 - offset) if direction < 0 else (view.y1 + offset)
            # Text sits on the dimension line; if wider than the span it is
            # placed beside the arrows, so its box grows to the right.
            tx0 = mid - width / 2 if width <= sx1 - sx0 else sx1 + 1.
            box = Box(min(sx0, tx0), y - TEXT_HEIGHT * .5, max(sx1, tx0 + width), y + TEXT_HEIGHT * 1.2)
            row = [p for p in placed if p.view == item['view'] and p.band == item['band'] and p.tier == tier]
            if not any(box.overlaps(p.box, 1.) for p in row):
                break
        else:
            conflicts.append(f'{item["id"]}: ölçü hattı bulunamadı.')
        placed.append(Placement(item['id'], item['view'], box, item['band'], tier, mid, y))
    # Sheet-level checks: border, title block and other views.
    for p in placed:
        if not p.box.inside(usable):
            conflicts.append(f'{p.id}: sayfa kenar boşluğunun dışına taşıyor.')
        if p.box.overlaps(title):
            conflicts.append(f'{p.id}: antet alanıyla çakışıyor.')
        for name, view in views.items():
            if name != p.view and p.box.overlaps(view['box'], .5):
                conflicts.append(f'{p.id}: {name} görünüşüyle çakışıyor.')
    for name, view in views.items():
        if view['box'].overlaps(title):
            conflicts.append(f'{name} görünüşü antet alanıyla çakışıyor.')
        if not view['box'].inside(usable):
            conflicts.append(f'{name} görünüşü sayfa sınırlarına sığmıyor.')
    return placed, sorted(set(conflicts))


def candidates(length, diameter, size='auto', scale_mode='auto', scale=(1, 1)):
    """Preference order: readable scale first, then the smallest sheet at that scale.

    Enlargements are only offered on A4/A3 for small parts; 1:1 is preferred
    over a reduction whenever some allowed sheet can hold it.
    """
    sizes = list(SHEET_SIZES) if size == 'auto' else [size]
    if scale_mode != 'auto':
        return [(name, tuple(scale)) for name in sizes]
    order = []
    for num, den in SCALES:
        factor = num / den
        allowed = [n for n in sizes if factor <= 1 or n in ('A4', 'A3')]
        if factor > 1 and max(length, diameter) * factor > 250:
            continue
        order += [(name, (num, den)) for name in allowed]
    return order


def build(length, diameter, views, annotations, *, size='auto', scale_mode='auto', scale=(1, 1),
          projection='first', detail_ids=()):
    """Try sheet/scale candidates until views and annotations fit without sheet conflicts."""
    attempts = candidates(length, diameter, size, scale_mode, scale)
    best = None
    for name, chosen in attempts:
        width, height = SHEET_SIZES[name]
        sheet = SheetChoice(name, width, height, chosen, True)
        view_boxes = place_views(sheet, length, diameter, views, projection, detail_ids)
        placed, conflicts = place_annotations(sheet, view_boxes, [a for a in annotations if a['view'] in view_boxes])
        # Second pass: size every dimension band from the tiers really used.
        used = {}
        for p in placed:
            used[(p.view, p.band)] = max(used.get((p.view, p.band), -1), p.tier)
        view_boxes = place_views(sheet, length, diameter, views, projection, detail_ids, used)
        placed, conflicts = place_annotations(sheet, view_boxes, [a for a in annotations if a['view'] in view_boxes])
        sheet_conflicts = [c for c in conflicts if 'sayfa' in c or 'antet' in c or 'görünüşüyle' in c]
        result = Layout(sheet, view_boxes, placed, conflicts)
        if not sheet_conflicts:
            return result
        if best is None or len(sheet_conflicts) < best[0]:
            best = (len(sheet_conflicts), result)
    result = best[1]
    result.sheet.fits = False
    result.sheet.note = ('Seçilen sayfa/ölçeğe sığmıyor; daha büyük sayfa veya küçük ölçek seçin.'
                         if size != 'auto' or scale_mode != 'auto' else 'A0 ve 1:20 ölçekte bile sığmıyor.')
    result.conflicts.insert(0, result.sheet.note)
    return result


def needs_detail(width_mm, factor):
    return width_mm * factor < MIN_FEATURE


def detail_enlargement(width_mm, factor):
    """Preferred enlargement k (detail scale = sheet scale × k) for a readable feature."""
    for k in (2, 5, 10):
        if width_mm * factor * k >= MIN_FEATURE:
            return k
    return 10
