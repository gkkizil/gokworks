"""Contours -> closed loops -> parts, collecting every geometry-hygiene issue.

Nothing is silently repaired: zero-length pieces and exact duplicates are left
out *and reported*; end gaps up to ``closure`` are bridged *and reported*;
everything else (open ends, branches, overlaps, crossings) is reported as an
error and the affected contour does not become a part.
"""

from dataclasses import dataclass, field
import math

from shapely import line_merge, maximum_inscribed_circle
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.ops import nearest_points
from shapely.strtree import STRtree

JOIN = 1e-3          # mm: ends closer than this are the same point (exact CAD join)


@dataclass
class Loop:
    polygon: Polygon
    handles: list
    circle: tuple | None = None       # (cx, cy, r) when the loop is one round hole/outline
    depth: int = 0

    @property
    def round(self):
        return self.circle is not None


@dataclass
class Part:
    name: str
    outline: Loop
    holes: list                        # [Loop]
    island: bool = False               # material inside another part's cut-out

    @property
    def material(self):
        return Polygon(self.outline.polygon.exterior, [h.polygon.exterior for h in self.holes])


@dataclass
class Topology:
    parts: list = field(default_factory=list)
    zero_length: list = field(default_factory=list)       # [(handle, point)]
    duplicates: list = field(default_factory=list)        # [(handle, of_handle, points)]
    overlaps: list = field(default_factory=list)          # [(handles, shared_points_list, length)]
    bridged: list = field(default_factory=list)           # [(a, b, gap, handles)]
    open_ends: list = field(default_factory=list)         # [(point, gap or None, handle)]
    branches: list = field(default_factory=list)          # [(point, handles)]
    self_intersections: list = field(default_factory=list)  # [(handle, points)]
    crossings: list = field(default_factory=list)         # [(handles, points)]
    short_segments: list = field(default_factory=list)    # [(handle, a, b, length)]
    open_paths: list = field(default_factory=list)        # [(handles, points)] chains that never closed


def _key(point, step):
    return round(point[0] / step), round(point[1] / step)


def _canonical(points, step):
    forward = tuple(_key(p, step) for p in points)
    backward = tuple(reversed(forward))
    if forward[0] == forward[-1] and len(forward) > 2:      # closed: rotation-independent
        ring = forward[:-1]
        variants = []
        for seq in (ring, tuple(reversed(ring))):
            i = seq.index(min(seq))
            variants.append(seq[i:] + seq[:i])
        return min(variants)
    return min(forward, backward)


def _intersection_points(geometry):
    points = []
    for g in getattr(geometry, 'geoms', [geometry]):
        if g.is_empty:
            continue
        if g.geom_type == 'Point':
            points.append((g.x, g.y))
        elif g.geom_type in ('LineString', 'LinearRing'):
            points.extend(list(g.coords)[:1])
        else:
            points.extend((p.x, p.y) for p in getattr(g, 'geoms', []))
    return points


def _round_circle(contour, polygon, tolerance):
    if contour['circle']:
        return contour['circle']
    if not contour.get('curved') or len(polygon.exterior.coords) < 9:
        return None
    centre = polygon.centroid
    radii = [math.dist((centre.x, centre.y), p) for p in polygon.exterior.coords[:-1]]
    if max(radii) - min(radii) <= 2 * tolerance:
        return centre.x, centre.y, max(radii)         # vertices lie on the true circle
    return None


def build(contours, *, closure=.05, short_segment=.05, tolerance=.01, stop=None):
    """Return :class:`Topology`. ``tolerance`` is the flattening chord error (mm)."""
    topo = Topology()
    kept = []
    seen = {}
    for c in contours:
        if stop is not None and stop.is_set():
            raise InterruptedError('Analiz durduruldu.')
        line = LineString(c['points']) if len(c['points']) > 1 else None
        if line is None or line.length <= JOIN:
            topo.zero_length.append((c['handle'], c['points'][0]))
            continue
        key = _canonical(c['points'], JOIN)
        if key in seen:
            topo.duplicates.append((c['handle'], seen[key], c['points']))
            continue
        seen[key] = c['handle']
        for a, b in zip(c['points'], c['points'][1:]):
            length = math.dist(a, b)
            if JOIN < length < short_segment and not c.get('curved'):
                topo.short_segments.append((c['handle'], a, b, length))
        kept.append(dict(c, line=line))

    # Overlaps (partial copies) and crossings between different contours.
    lines = [c['line'] for c in kept]
    tree = STRtree(lines)
    bad = set()
    for i, line in enumerate(lines):
        if stop is not None and stop.is_set():
            raise InterruptedError('Analiz durduruldu.')
        # Closed contours are checked as polygons below; open ones must be simple.
        if not kept[i]['closed'] and not line.is_simple:
            shared = _self_touch_points(line)
            topo.self_intersections.append((kept[i]['handle'], shared or [line.coords[0]]))
            bad.add(i)
        for j in tree.query(line):
            j = int(j)
            if j <= i:
                continue
            other = lines[j]
            common = line.intersection(other)
            if common.is_empty:
                continue
            shared_length = sum(g.length for g in getattr(common, 'geoms', [common]) if g.geom_type in ('LineString', 'MultiLineString'))
            if shared_length > JOIN:
                pieces = [list(g.coords) for g in getattr(common, 'geoms', [common]) if g.geom_type == 'LineString']
                topo.overlaps.append(([kept[i]['handle'], kept[j]['handle']], pieces, shared_length))
                bad.update((i, j))
                continue
            # Touching only at shared end points is how open pieces join.
            ends = [Point(p) for c in (kept[i], kept[j]) if not c['closed'] for p in (c['points'][0], c['points'][-1])]
            points = [p for p in _intersection_points(common)
                      if not any(Point(p).distance(e) <= JOIN for e in ends)]
            if points:
                topo.crossings.append(([kept[i]['handle'], kept[j]['handle']], points))
                bad.update((i, j))

    # End points of open pieces: exact joins, bridged gaps, open ends, branches.
    open_items = [(i, c) for i, c in enumerate(kept) if not c['closed'] and i not in bad]
    clusters = []                       # [[point, [(item, end)]]]
    for i, c in open_items:
        for end in (0, -1):
            p = c['points'][end]
            for cluster in clusters:
                if math.dist(cluster[0], p) <= JOIN:
                    cluster[1].append((i, end)); break
            else:
                clusters.append([p, [(i, end)]])
    loose = [k for k, cl in enumerate(clusters) if len(cl[1]) == 1]
    for k, cl in enumerate(clusters):
        if len(cl[1]) > 2:
            topo.branches.append((cl[0], sorted({kept[i]['handle'] for i, _ in cl[1]})))
    paired = {}
    for k in loose:
        if k in paired:
            continue
        best, distance = None, math.inf
        for m in loose:
            if m != k and m not in paired:
                d = math.dist(clusters[k][0], clusters[m][0])
                if d < distance:
                    best, distance = m, d
        if best is not None and distance <= closure:
            # Mutual nearest only: never bridge across a closer partner.
            back = min((m for m in loose if m != best and m not in paired),
                       key=lambda m: math.dist(clusters[best][0], clusters[m][0]), default=None)
            if back == k:
                paired[k], paired[best] = best, k
                handles = sorted({kept[i]['handle'] for i, _ in clusters[k][1] + clusters[best][1]})
                topo.bridged.append((clusters[k][0], clusters[best][0], distance, handles))
    for k in loose:
        if k in paired:
            continue
        others = [math.dist(clusters[k][0], clusters[m][0]) for m in loose if m != k]
        topo.open_ends.append((clusters[k][0], min(others) if others else None, kept[clusters[k][1][0][0]]['handle']))

    # Chain open pieces (with bridges) into loops.
    representative = {}
    for cl in clusters:
        for i, end in cl[1]:
            representative[(i, end)] = cl[0]
    pieces, owners = [], []
    for i, c in open_items:
        points = list(c['points'])
        points[0], points[-1] = representative[(i, 0)], representative[(i, -1)]
        pieces.append(LineString(points)); owners.append(c['handle'])
    for k, m in paired.items():
        if k < m:
            pieces.append(LineString([clusters[k][0], clusters[m][0]])); owners.append('köprü')
    branch_points = [Point(b[0]) for b in topo.branches]
    loops = []
    if pieces:
        merged = line_merge(MultiLineString(pieces))
        for chain in getattr(merged, 'geoms', [merged]):
            handles = sorted({owners[n] for n, piece in enumerate(pieces) if piece.distance(chain) <= JOIN
                              and piece.intersection(chain).length > 0})
            if chain.is_ring and not any(chain.distance(b) <= JOIN for b in branch_points):
                polygon = Polygon(chain.coords)
                if polygon.is_valid and polygon.area > 0:
                    loops.append(Loop(polygon, handles))
                else:
                    topo.self_intersections.append((handles[0] if handles else '', [chain.coords[0]]))
            else:
                topo.open_paths.append((handles, list(chain.coords)))
    for i, c in enumerate(kept):
        if c['closed'] and i not in bad:
            polygon = Polygon(c['points'])
            if not polygon.is_valid or polygon.area <= 0:
                topo.self_intersections.append((c['handle'], _self_touch_points(LineString(c['points'])) or [c['points'][0]]))
                continue
            loops.append(Loop(polygon, [c['handle']], _round_circle(c, polygon, tolerance)))

    # Classify: depth 0 outline, 1 cut-out, 2 island (loose material), ...
    polygons = [loop.polygon for loop in loops]
    tree = STRtree(polygons) if polygons else None
    for n, loop in enumerate(loops):
        containers = [int(j) for j in tree.query(loop.polygon, predicate='within') if int(j) != n]
        loop.depth = len(containers)
    count = 0
    for n, loop in enumerate(loops):
        if loop.depth % 2:
            continue
        holes = [h for h in loops if h.depth == loop.depth + 1 and h.polygon.within(loop.polygon)]
        count += 1
        topo.parts.append(Part(f'Parça {count}', loop, holes, island=loop.depth >= 2))
    return topo


def _self_touch_points(line):
    """Points where a polyline meets itself (for marking)."""
    coords = list(line.coords)
    segments = [LineString(coords[k:k + 2]) for k in range(len(coords) - 1)]
    points = []
    for a in range(len(segments)):
        for b in range(a + 2, len(segments)):
            if a == 0 and b == len(segments) - 1 and coords[0] == coords[-1]:
                continue
            hit = segments[a].intersection(segments[b])
            if not hit.is_empty:
                points.extend(_intersection_points(hit))
        if len(points) > 20:
            break
    return points


def hole_width(loop, accuracy=.01):
    """Round hole: exact diameter. Otherwise the narrowest passage of the opening:
    twice the radius of its largest inscribed circle (accuracy in mm)."""
    if loop.circle:
        return 2 * loop.circle[2], [(loop.circle[0] - loop.circle[2], loop.circle[1]),
                                    (loop.circle[0] + loop.circle[2], loop.circle[1])]
    radius_line = maximum_inscribed_circle(loop.polygon, accuracy)
    (cx, cy), (bx, by) = radius_line.coords[0], radius_line.coords[-1]
    return 2 * radius_line.length, [(2 * cx - bx, 2 * cy - by), (bx, by)]


def closest(a, b):
    """Shortest distance between two boundaries and its two end points."""
    pa, pb = nearest_points(a, b)
    return pa.distance(pb), [(pa.x, pa.y), (pb.x, pb.y)]
