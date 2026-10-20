"""Rigid placement transforms and collision footprints; holes are never nestable."""

from shapely import affinity, union_all
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
import math


def polygons(g):
    if g.geom_type == 'Polygon':
        return [g]
    return [p for p in getattr(g, 'geoms', []) if p.geom_type == 'Polygon']


def footprint(g):
    return union_all([Polygon(p.exterior) for p in polygons(g)])


def rotated(part, angle):
    return affinity.rotate(part.polygon, angle, origin=(0, 0))


def placed(part, placement):
    return affinity.translate(rotated(part, placement.angle), placement.x, placement.y)


def rings(g):
    for p in polygons(g):
        yield False, list(p.exterior.coords)
        for ring in p.interiors:
            yield True, list(ring.coords)


def convex_parts(g, checkpoint=lambda: None):
    """Exact constrained triangulation; convex pieces need no decomposition."""
    from shapely import constrained_delaunay_triangles
    result = []
    for p in polygons(g):
        if p.equals(p.convex_hull):
            result.append(p)
        else:
            pieces = list(constrained_delaunay_triangles(p).geoms)
            # Merge adjacent triangles when the union is still convex. No hull
            # replacement of a concavity is permitted.
            changed = True
            while changed:
                checkpoint()
                changed = False
                for i in range(len(pieces)):
                    checkpoint()
                    for j in range(i+1, len(pieces)):
                        if pieces[i].intersection(pieces[j]).length == 0:
                            continue
                        combined = pieces[i].union(pieces[j])
                        if combined.geom_type == 'Polygon' and combined.equals(combined.convex_hull):
                            pieces[i] = combined; pieces.pop(j); changed = True; break
                    if changed:
                        break
            result.extend(pieces)
    return result


def convex_sum(a, b):
    """Merge CCW edge vectors in angular order, linear-size convex sum."""
    a = list(orient(a, 1).exterior.coords)[:-1]
    b = list(orient(b, 1).exterior.coords)[:-1]
    # Start each polygon at its lowest y, then lowest x vertex; all following
    # CCW edges are sorted from angle 0 through 2π after circular rotation.
    def ordered(points):
        i = min(range(len(points)), key=lambda k: (points[k][1], points[k][0]))
        return points[i:]+points[:i]
    a,b = ordered(a),ordered(b)
    edges = []
    for points in (a,b):
        for i,(x,y) in enumerate(points):
            u,v = points[(i+1)%len(points)]
            dx,dy = u-x,v-y
            edges.append((math.atan2(dy,dx) % (2*math.pi),dx,dy))
    edges.sort(key=lambda e:e[0])
    x,y = a[0][0]+b[0][0],a[0][1]+b[0][1]; result = [(x,y)]
    for _,dx,dy in edges:
        x += dx; y += dy; result.append((x,y))
    return Polygon(result).convex_hull


def minkowski(a, b, checkpoint=lambda: None):
    """A ⊕ B via convex decomposition, not bounding rectangles (own implementation)."""
    pieces = []
    aa,bb = convex_parts(a,checkpoint),convex_parts(b,checkpoint)
    for pa in aa:
        for pb in bb:
            checkpoint()
            pieces.append(convex_sum(pa,pb))
    return union_all(pieces)
