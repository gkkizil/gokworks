"""AABB broad phase, OCCT solid narrow phase, bounded local contact masks."""
from dataclasses import dataclass
from itertools import combinations
from math import prod, sqrt
import numpy as np


@dataclass(frozen=True)
class Hit:
    pair: tuple[str, str]
    location: tuple[float, float, float]
    volume: float


def box_distance(a, b):
    return sqrt(sum(max(0, a[i]-b[i+3], b[i]-a[i+3])**2 for i in range(3)))


def volume(shape):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    p = GProp_GProps(); BRepGProp.VolumeProperties_s(shape, p)
    c = p.CentreOfMass()
    return abs(p.Mass()), (c.X(), c.Y(), c.Z())


def intersection(a, b):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    try:
        from OCP.TopTools import TopTools_ListOfShape
    except ImportError:  # OCCT 8 bindings use the concrete collection name.
        from OCP.collections import List_TopoDS_Shape as TopTools_ListOfShape
    # The two-shape constructor already builds. Set the options first and build
    # once, while keeping cached source topology unchanged.
    operation = BRepAlgoAPI_Common()
    arguments, tools = TopTools_ListOfShape(), TopTools_ListOfShape()
    arguments.Append(a); tools.Append(b)
    operation.SetArguments(arguments); operation.SetTools(tools)
    operation.SetNonDestructive(True)
    operation.SetFuzzyValue(1e-7); operation.Build()
    if not operation.IsDone():
        raise ValueError('Katı kesişim hesabı tamamlanamadı; kontrol geçerli değil.')
    return operation.Shape()


def remove_contacts(shape, body_a, body_b, contacts):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
    if body_a.kind != 'sheet' and body_b.kind != 'sheet':
        return shape
    kind = body_b.kind if body_a.kind == 'sheet' else body_a.kind
    sheet_id = body_a.id if body_a.kind == 'sheet' else body_b.id
    allowed = [(y, z, r) for tool_kind, y, z, r, ids in contacts if tool_kind == kind and sheet_id in ids]
    xmin = min(body_a.bounds[0], body_b.bounds[0])-1
    length = max(body_a.bounds[3], body_b.bounds[3])-xmin+1
    for y, z, radius in allowed:
        mask = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(xmin, y, z), gp_Dir(1, 0, 0)), radius, length).Shape()
        cut = BRepAlgoAPI_Cut(shape, mask)
        if not cut.IsDone():
            raise ValueError('Yerel temas toleransı katıdan ayrılamadı.')
        shape = cut.Shape()
    return shape


def separation(a, b):
    """Lower bound of the distance between two bodies (mm); 0 when it cannot rule out contact.

    Axis-aligned boxes first, then the bodies' convex containers projected on
    their own face normals (separating axes). A positive value is a proof of
    clearance by at least that much; zero only means a solid check is needed.
    """
    distance = box_distance(a.bounds, b.bounds)
    hull_a, hull_b = getattr(a, 'hull', None), getattr(b, 'hull', None)
    if hull_a is None or hull_b is None:
        return distance
    import numpy as np
    axes = np.concatenate((hull_a[1], hull_b[1]))
    pa, pb = hull_a[0]@axes.T, hull_b[0]@axes.T
    gap = np.maximum(pb.min(axis=0)-pa.max(axis=0), pa.min(axis=0)-pb.max(axis=0)).max()
    return max(distance, float(gap))


CLEAR_VOLUME = 1e-6   # mm³: an overlap bound this small proves "no hit" (a hit needs > 0,001 mm³)


def _pieces_in_slab(pieces, x0, x1):
    """Corner points of each convex piece cut to x0 <= x <= x1, projected on YZ (piece index per point)."""
    from itertools import combinations
    k = pieces.shape[1]; pairs = np.array(list(combinations(range(k), 2)))
    a, b = pieces[:, pairs[:, 0]], pieces[:, pairs[:, 1]]
    groups = [(pieces, (pieces[..., 0] >= x0-1e-9) & (pieces[..., 0] <= x1+1e-9))]
    for plane in (x0, x1):
        da, db = a[..., 0]-plane, b[..., 0]-plane
        crossing = da*db < 0
        with np.errstate(divide='ignore', invalid='ignore'):
            s = np.where(crossing, da/(da-db), 0.)
        groups.append((a+s[..., None]*(b-a), crossing))
    points = np.concatenate([g for g, _ in groups], axis=1)[..., 1:]
    mask = np.concatenate([m for _, m in groups], axis=1)
    index = np.broadcast_to(np.arange(len(pieces))[:, None], mask.shape)
    return points[mask], index[mask]


def prism_clear(a, b, contacts=()):
    """True when an extruded tool provably does not overlap the other body (no OCCT boolean needed).

    A tool is its exact YZ section × [x0, x1]. A sheet body is covered by convex
    pieces; each piece cut to the tool's span and projected on YZ is a convex
    polygon. If those polygons and the section (minus the allowed contact
    cylinders, which are discs in YZ) share no area, the solids share no volume.
    False only means "not proven here": the solid intersection decides.
    """
    import shapely
    pa, pb = getattr(a, 'prism', None), getattr(b, 'prism', None)
    if pa is not None and pb is not None:
        span = min(pa[2], pb[2])-max(pa[1], pb[1])
        return span <= 0 or shapely.area(shapely.intersection(pa[0], pb[0]))*span <= CLEAR_VOLUME
    if pa is None:
        a, b, pa = b, a, pb
    if pa is None or b.kind != 'sheet' or getattr(b, 'pieces', None) is None:
        return False
    region = pa[0]
    discs = [shapely.Point(y, z).buffer(r, quad_segs=16) for kind, y, z, r, ids in contacts if kind == a.kind and b.id in ids]
    if discs:   # the inscribed polygon removes slightly less than the cylinder: still a safe bound
        region = region.difference(shapely.union_all(discs))
    if region.is_empty:
        return True
    x0, x1 = pa[1], pa[2]
    pieces = b.pieces
    lo, hi = pieces[..., 0].min(axis=1), pieces[..., 0].max(axis=1)
    y0, z0, y1, z1 = region.bounds
    pieces = pieces[(hi > x0) & (lo < x1) & (pieces[..., 1].max(axis=1) > y0) & (pieces[..., 1].min(axis=1) < y1)
                    & (pieces[..., 2].max(axis=1) > z0) & (pieces[..., 2].min(axis=1) < z1)]
    if not len(pieces):
        return True
    span = np.minimum(pieces[..., 0].max(axis=1), x1)-np.maximum(pieces[..., 0].min(axis=1), x0)
    points, index = _pieces_in_slab(pieces, x0, x1)
    hulls = shapely.convex_hull(shapely.multipoints(points, indices=index))
    used = np.unique(index)
    shapely.prepare(region)
    areas = shapely.area(shapely.intersection(hulls, region))
    return float(np.dot(areas, span[used])) <= CLEAR_VOLUME


def check(bodies, contacts=(), *, near_margin=0, cache=None, sheet_hits=None, still=None):
    """Return all colliding pairs plus proximity needing denser sampling.

    ``still(a, b)``: the pair has no relative motion in the sampled phase; it is
    still tested for overlap in every pose but cannot ask for denser samples.
    """
    hits, near = [], False
    for a, b in combinations(bodies, 2):
        # Bodies are stationary relative to each other within one tool assembly.
        # Their assembly validity is checked when the section/segment is loaded.
        if a.kind == b.kind and a.kind in ('punch', 'die'):
            continue
        if a.kind == b.kind == 'holder' and a.id.split(':')[1] == b.id.split(':')[1]:
            continue
        # A holder and the tool it clamps are one rigid assembly too. Their fit is a
        # section check (service.holder_overlap -> "Kontrol edilemedi"), not motion.
        if 'holder' in (a.kind, b.kind) and a.kind != b.kind:
            holder, other = (a, b) if a.kind == 'holder' else (b, a)
            parts = holder.id.split(':')            # 'holder:<tool kind>:<n>'
            if len(parts) > 1 and other.kind == parts[1]:
                continue
        distance = separation(a, b)
        if distance > near_margin:
            continue
        fixed = still is not None and still(a, b)
        if distance > 1e-7:
            near |= not fixed
            continue
        # Intersection volume cannot exceed the boxes' common volume. This
        # also eliminates exact tangent/edge contact without an OCCT boolean.
        box_volume = prod(max(0., min(a.bounds[i+3], b.bounds[i+3])-max(a.bounds[i], b.bounds[i])) for i in range(3))
        if box_volume <= .001:
            near |= bool(near_margin) and not fixed
            continue
        key = (a.id, a.kind, a.shape, b.id, b.kind, b.shape, tuple(contacts))
        if sheet_hits is not None and a.kind == b.kind == 'sheet':
            hit = sheet_hits.get((a.id, b.id))
        elif cache is not None and key in cache:
            hit = cache[key]
        elif prism_clear(a, b, contacts):
            hit = None      # proven apart on the tools' exact sections: the boolean would find nothing
        else:
            common = intersection(a.shape, b.shape)
            mass, _ = volume(common); hit = None
            if mass > 1e-5:
                common = remove_contacts(common, a, b, contacts)
                mass, location = volume(common)
                if mass > .001:
                    hit = Hit((a.id, b.id), tuple(location), mass)
            if cache is not None:
                if len(cache) >= 2048:
                    cache.clear()
                cache[key] = hit
        if hit is not None:
            hits.append(hit)
            continue
        if near_margin and not fixed:
            # Containers that cannot be separated refine even a near miss through a
            # hole. Every actual overlap above still uses solid intersection.
            # No distance-based continuous-clearance certificate is claimed.
            near = True
    return tuple(hits), near
