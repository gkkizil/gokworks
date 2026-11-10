"""Original GOKWORKS educational shapes; no manufacturer catalogue assets."""
from math import pi
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union
from dataclasses import replace
from .models import Bend, Channel, Flange, Mount, Part, Plan, Region, Segment, Step, Tool


def tools():
    mount = Mount('GOK-DEMO-tongue-10x8', 'GOK-DEMO-tongue-10x8')
    segments = (Segment(-60, 120),)
    # Coordinates are real mm for these ORIGINAL demo tools, never catalogue
    # equivalents. The wide punch intentionally catches a previously bent wall.
    punch = Tool('demo-punch', 'GOKWORKS DEMO', 'DEMO-NARROW', 'punch', 'Özgün demo', 80, (0, 80),
                 Region(((-.2, 0), (.2, 0), (3, 7), (3, 70), (5, 70), (5, 80), (-5, 80), (-5, 70), (-3, 70), (-3, 7))),
                 'GOKWORKS tarafından üretilen mm kesiti', segments, mount,
                 43.6, .2, (0, 0), demo=True)
    wide = Tool('demo-wide', punch.maker, 'DEMO-WIDE', 'punch', punch.family, 80, (0, 80),
                Region(((-.2, 0), (.2, 0), (4, 7), (70, 12), (70, 80), (-70, 80), (-70, 12), (-4, 7))),
                punch.source, segments, mount, 58, .2, (0, 0), demo=True)
    die = Tool('demo-die', punch.maker, 'DEMO-2V', 'die', punch.family, 32, (0, -32),
               Region(((-30, 0), (-8, 0), (0, -12), (8, 0), (24, 0), (36, -16), (48, 0), (55, 0), (55, -32), (-30, -32))),
               punch.source, segments, mount, channels=(Channel('V16', 16, 67.38, (0, 0), 0),
               Channel('V24', 24, 73.74, (36, 0), 0)), demo=True)
    punch_holder = Region(((-8, 80), (8, 80), (8, 90), (-8, 90)))
    die_holder = Region(((-30, -42), (55, -42), (55, -32), (-30, -32)))
    return (replace(punch, holder_section=punch_holder, holder_source='Özgün DEMO üst tutucu', holder_segments=segments),
            replace(wide, holder_section=Region(((-70, 80), (70, 80), (70, 90), (-70, 90))), holder_source='Özgün DEMO geniş üst tutucu', holder_segments=segments),
            replace(die, holder_section=die_holder, holder_source='Özgün DEMO alt tutucu', holder_segments=segments))


def load_demo(kind='box'):
    t, radius = 2., 2.
    width = (radius+t/2)*pi/2
    flanges, bends = [], []
    root_poly = box(-40, -30, 40, 30).difference(Point(0, 0).buffer(8, quad_segs=24))
    if kind == 'L120':
        width = (radius+t/2)*pi/3
        sides = [((-40, 30), (40, 30), box(-40, 30+width, 40, 65+width))]
    elif kind == 'U':
        sides = [((-40, 30), (40, 30), box(-40, 30+width, 40, 65+width)),
                 ((40, -30), (-40, -30), box(-40, -65-width, 40, -30-width))]
    elif kind == 'box':
        # 1.5 mm corner setbacks are real bend reliefs, visible in every pose.
        sides = [((-38.5, 30), (38.5, 30), box(-38.5, 30+width, 38.5, 65+width)),
                 ((40, 28.5), (40, -28.5), box(40+width, -28.5, 75+width, 28.5)),
                 ((38.5, -30), (-38.5, -30), box(-38.5, -65-width, 38.5, -30-width)),
                 ((-40, -28.5), (-40, 28.5), box(-75-width, -28.5, -40-width, 28.5))]
    else:
        raise ValueError('Bilinmeyen demo parçası.')
    flanges.append(Flange('F0', Region.from_polygon(root_poly)))
    for i, (start, end, poly) in enumerate(sides, 1):
        dx, dy = end[0]-start[0], end[1]-start[1]
        length = (dx*dx+dy*dy)**.5
        n = (-dy/length*width, dx/length*width)
        zone = Polygon([start, end, (end[0]+n[0], end[1]+n[1]), (start[0]+n[0], start[1]+n[1])])
        # Hole on each wall; actual cutout, not a painted circle.
        p = poly.centroid
        poly = poly.difference(Point(p.x, p.y).buffer(3, quad_segs=12))
        flanges.append(Flange(f'F{i}', Region.from_polygon(poly)))
        bends.append(Bend(f'B{i:02}', 'F0', f'F{i}', start, end, width,
                          120 if kind == 'L120' else 90, radius, 1, Region.from_polygon(zone), 'DEMO · tasarım ölçüsü'))
    part = Part({'box': 'DEMO · Delikli dört kenarlı kutu', 'U': 'DEMO · U parçası', 'L120': 'DEMO · L / 120°'}[kind],
                'Demo', 'DEMO · S235 (proses verisi yok)', t, 'F0', tuple(flanges), tuple(bends), 'DEMO:F0', 'GOKWORKS özgün demo', True)
    # Check connectivity without healing away the intentional reliefs/holes.
    unary_union([f.region.polygon() for f in flanges]+[b.region.polygon() for b in bends])
    return Plan(part, tuple(Step(b.id, punch_segments=(Segment(-b.length/2, b.length),),
                                     die_segments=(Segment(-b.length/2, b.length),)) for b in bends), tools()).validate()
