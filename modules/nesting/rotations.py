"""One rotation contract: None means continuous; lists remain exact restrictions."""
from math import atan2, degrees, hypot, isfinite


def minimum_span(geometry):
    """Minimum caliper width, used only to reject impossible strip inputs.

    A convex hull supplies the support directions; cutting geometry is untouched.
    """
    points = list(geometry.convex_hull.exterior.coords)
    best = float('inf')
    for a, b in zip(points, points[1:]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = hypot(dx, dy)
        if not length:
            continue
        projections = [(dy*x-dx*y)/length for x, y in points[:-1]]
        best = min(best, max(projections)-min(projections))
    return best


def allowed_angles(part, options):
    if not options.rotation:
        return [0.]
    angles = options.angles
    if options.grain_locked or part.grain_locked:
        return [0., 180.] if angles is None else [a for a in angles if abs(a % 180) < 1e-7]
    return angles


def angle_allowed(part, options, angle):
    if not isfinite(angle):
        return False
    allowed = allowed_angles(part, options)
    return allowed is None or any(abs((angle-a+180) % 360-180) < 1e-6 for a in allowed)


def search_angles(part, options):
    """Finite NFP proposals for continuous mode; native Sparrow searches freely.

    Align major contour edges and the minimum rectangle before the regular
    angular spread. Recorded discrete angles are never expanded.
    """
    allowed = allowed_angles(part, options)
    if allowed is not None:
        return list(dict.fromkeys(a % 360 for a in allowed))
    polygon = part.polygon
    regions = [polygon] if polygon.geom_type == 'Polygon' else list(polygon.geoms)
    edges = []
    for region in regions:
        points = list(region.exterior.coords)
        edges.extend((hypot(b[0]-a[0], b[1]-a[1]), degrees(atan2(b[1]-a[1], b[0]-a[0])))
                     for a, b in zip(points, points[1:]))
    rectangle = list(polygon.minimum_rotated_rectangle.exterior.coords)
    major = degrees(atan2(rectangle[1][1]-rectangle[0][1], rectangle[1][0]-rectangle[0][0]))
    proposals = [0., 90., 180., 270.]
    for direction in [major, *(angle for _, angle in sorted(edges, reverse=True)[:8])]:
        proposals.extend((quarter-direction) % 360 for quarter in (0, 90, 180, 270))
    proposals.extend(range(0, 360, 15))
    return list(dict.fromkeys(round(a % 360, 8) for a in proposals))
