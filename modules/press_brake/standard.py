"""Generic market-standard press brake tools, drawn from parameters (no manufacturer drawing).

There is no DIN/ISO standard for press brake punch or die *profiles* (EN 12622 /
DIN EN 12622 covers machine safety; DIN ISO 16367 covers other pressing tool
parts). What the market shares are conventions, used here as parameters:

* European (Promecam-type) clamping with a 13 mm tang, 835 mm sectioned sets
  (10+15+20+40+50+100+200+400 mm),
* 88° air-bending punches with R 0.8 tip, 30° acute punches, a gooseneck for
  return flanges,
* single-V dies at 88° in the usual opening series V6…V50, chosen by the
  V ≈ 6–12 × t rule (8 × t for mild steel); inside radius ≈ 0.16 × V in air bending.

Sections are GOKWORKS' own simplified drawings with these dimensions; a real
supplier's tool differs in body shape and holder. Results with them say so.
"""
from math import radians, tan
from shapely.geometry import Polygon
from .models import Channel, Mount, Region, Segment, Tool

MAKER = 'GENEL · piyasa standardı'
FAMILY = 'Avrupa tipi (Promecam) · genel ölçü'
SOURCE = 'GOKWORKS parametrik kesit · piyasa standardı ölçüler, üretici çizimi değil'
INTERFACE = 'GENEL-AVRUPA-13'          # same string on tool and generic holder: geometrically placed, not a supplier fit
SECTIONED = (10, 15, 20, 40, 50, 100, 200, 400)   # 835 mm set
V_SERIES = (6, 8, 10, 12, 16, 20, 25, 32, 40, 50)
NOTE = 'Genel standart ölçülü takım: üretici kesiti değil; gerçek takım ve tutucuyla doğrulayın.'


def sectioned_set(length=835):
    """Segments of a standard sectioned set, centred on the bend line."""
    pieces, x = [], -length/2
    for piece in (SECTIONED if length == 835 else (length,)):
        pieces.append(Segment(x, piece)); x += piece
    return tuple(pieces)


def is_generic(tool):
    return tool.id.startswith('std:')


def station(length):
    """Fewest sectioned-set pieces whose total covers ``length``, centred (a tool station built from the bend)."""
    from itertools import combinations
    best = None
    for count in range(1, len(SECTIONED)+1):
        for pieces in combinations(SECTIONED, count):
            total = sum(pieces)
            if total >= length-1e-9 and (best is None or (total, count) < (sum(best), len(best))):
                best = pieces
    if best is None:
        raise ValueError(f'{length:g} mm büküm 835 mm standart setten uzun.')
    pieces, x = [], -sum(best)/2
    for piece in sorted(best, reverse=True):
        pieces.append(Segment(x, piece)); x += piece
    return tuple(pieces)


def default_segments(tool, bend):
    """Segments used when a step has none of its own: generic tools form a station from the bend length."""
    return station(bend.length) if is_generic(tool) else tool.segments


def rounded(polygon, radius, quad_segs=8):   # chord error < 0.02 mm at R4; far fewer faces to intersect
    """Round convex corners (tips, shoulders) by ``radius``; concave corners stay sharp."""
    if radius <= 0:
        return polygon
    return polygon.buffer(-radius, quad_segs=quad_segs, join_style='round').buffer(radius, quad_segs=quad_segs, join_style='round')


def recommended_v(thickness):
    """Opening from the 8 × t rule, snapped to the nearest series value."""
    return min(V_SERIES, key=lambda v: (abs(v-8*thickness), v))


def shoulder_radius(opening):
    return max(.5, round(opening*.08*2)/2)


TANG, CLEAR = 6.5, .05     # half-width of the 13 mm tang; slot clearance so a seated tool never overlaps its holder


def _bolt(y, z, radius=4.):
    from shapely.geometry import Point
    return Point(y, z).buffer(radius, quad_segs=4)   # 16-sided: reads as a bolt, keeps the mesh and check light


def punch_holder(height):
    """Intermediate clamp seated on the punch shoulder (z = height-20), tang slot below, beam tang on top.

    Generic Promecam-type proportions drawn by GOKWORKS: chamfered body, front
    clamp plate with its clamping bolt, rear body; not a supplier holder.
    """
    from shapely.geometry import box
    base = height-20
    body = Polygon([(-16, base), (16, base), (16, base+5), (24, base+13), (24, base+52), (20, base+58),
                    (11, base+58), (11, base+78), (-11, base+78), (-11, base+58), (-22, base+58), (-26, base+52),
                    (-26, base+13), (-16, base+5)])
    slot = box(-TANG-CLEAR, base-1, TANG+CLEAR, height+CLEAR)                     # holds the tool's 13 mm tang
    split = box(9, base+20, 9.8, base+58)                                         # gap between clamp plate and body
    shape = body.difference(slot).difference(split).difference(_bolt(17, base+36)).difference(_bolt(-19, base+36, 3))
    return Region.from_polygon(rounded(shape, .8, 2))   # edge breaks, not working surfaces


def die_rail(height):
    """Lower rail under the die (die body seats at z = 8-height), tang slot, side clamping bolts, base flange."""
    from shapely.geometry import box
    top = -height+8
    body = Polygon([(-30, top), (30, top), (30, top-28), (40, top-36), (40, top-50), (-40, top-50), (-40, top-36),
                    (-30, top-28)])
    slot = box(-TANG-CLEAR, top-8-CLEAR, TANG+CLEAR, top+1)
    shape = body.difference(slot).difference(_bolt(-19, top-15, 3.5)).difference(_bolt(19, top-15, 3.5))
    shape = shape.difference(box(-41, top-43, -36, top-41)).difference(box(36, top-43, 41, top-41))   # T-slot grooves
    return Region.from_polygon(rounded(shape, .8, 2))   # edge breaks, not working surfaces


def _punch(id, code, polygon, tip_angle, tip_radius, height):
    polygon = rounded(polygon, tip_radius)
    low = polygon.bounds[1]
    region = Region.from_polygon(polygon)
    holder = punch_holder(height)
    return Tool(f'std:{id}', MAKER, code, 'punch', FAMILY, height, (0, height), region, SOURCE, sectioned_set(),
                Mount(INTERFACE, INTERFACE), tip_angle, tip_radius, (0, low),
                holder_section=holder, holder_source='Genel ara tutucu · Avrupa tipi profil (yaklaşık)', holder_segments=sectioned_set())


def straight_punch(angle=88, radius=.8, height=95):
    half = radians(angle/2)
    blade = 5                                  # half-width of the narrow blade
    wedge = blade/tan(half)
    p = Polygon([(0, 0), (blade, wedge), (blade, height*.55), (13, height-20), (6.5, height-20), (6.5, height),
                 (-6.5, height), (-6.5, height-20), (-13, height-20), (-blade, height*.55), (-blade, wedge)])
    return _punch(f'punch-{angle}-r{radius:g}-h{height}', f'GS-P{angle}-R{radius:g}-H{height}'.replace('.', ','),
                  p, angle, radius, height)


def acute_punch(angle=30, radius=.6, height=95):
    half = radians(angle/2)
    body = 13
    p = Polygon([(0, 0), (body, body/tan(half)), (body, height-20), (6.5, height-20), (6.5, height),
                 (-6.5, height), (-6.5, height-20), (-body, height-20), (-body, body/tan(half))])
    return _punch(f'acute-{angle}-r{radius:g}-h{height}', f'GS-A{angle}-R{radius:g}-H{height}'.replace('.', ','),
                  p, angle, radius, height)


def gooseneck_punch(angle=88, radius=.8, height=95):
    """Neck set back behind the tip line, leaving room for a return flange in front (+y)."""
    half = radians(angle/2)
    p = Polygon([(0, 0), (4, 4/tan(half)), (4, 26), (-14, 42), (-14, 60), (13, 75), (6.5, 75), (6.5, height),
                 (-6.5, height), (-6.5, 75), (-32, 75), (-32, 32), (-4, 4/tan(half))])
    return _punch(f'gooseneck-{angle}-r{radius:g}-h{height}', f'GS-G{angle}-R{radius:g}-H{height}'.replace('.', ','),
                  p, angle, radius, height)


def single_v_die(opening, angle=88, height=60):
    half = radians(angle/2)
    depth = opening/2/tan(half)
    width = opening+2*max(10, opening*.5)
    p = Polygon([(-width/2, 0), (-opening/2, 0), (0, -depth), (opening/2, 0), (width/2, 0), (width/2, -height+8),
                 (6.5, -height+8), (6.5, -height), (-6.5, -height), (-6.5, -height+8), (-width/2, -height+8)])
    r = shoulder_radius(opening)
    p = rounded(p, r)
    holder = die_rail(height)
    return Tool(f'std:die-v{opening}-{angle}', MAKER, f'GS-V{opening}-{angle}', 'die', FAMILY, height, (0, -height),
                Region.from_polygon(p), SOURCE, sectioned_set(), Mount(INTERFACE, INTERFACE),
                channels=(Channel(f'V{opening}', opening, angle, (0, 0), r),),
                holder_section=holder, holder_source='Genel kalıp rayı · Avrupa tipi profil (yaklaşık)', holder_segments=sectioned_set())


def standard_tools():
    """The generic library offered with every plan."""
    tools = (straight_punch(), straight_punch(86, .8), acute_punch(), gooseneck_punch(),
             *(single_v_die(v) for v in V_SERIES), single_v_die(16, 30))
    return tuple(t.validate() for t in tools)
