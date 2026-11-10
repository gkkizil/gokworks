"""AABB broad phase, OCCT solid narrow phase, bounded local contact masks."""
from dataclasses import dataclass
from itertools import combinations
from math import prod, sqrt


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


def check(bodies, contacts=(), *, near_margin=0, cache=None, sheet_hits=None):
    """Return all colliding pairs plus proximity needing denser angle sampling."""
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
        distance = box_distance(a.bounds, b.bounds)
        if distance > near_margin:
            continue
        if distance > 1e-7:
            near = True
            continue
        # Intersection volume cannot exceed the boxes' common volume. This
        # also eliminates exact tangent/edge contact without an OCCT boolean.
        box_volume = prod(max(0., min(a.bounds[i+3], b.bounds[i+3])-max(a.bounds[i], b.bounds[i])) for i in range(3))
        if box_volume <= .001:
            near |= bool(near_margin)
            continue
        key = (a.id, a.kind, a.shape, b.id, b.kind, b.shape, tuple(contacts))
        if sheet_hits is not None and a.kind == b.kind == 'sheet':
            hit = sheet_hits.get((a.id, b.id))
        elif cache is not None and key in cache:
            hit = cache[key]
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
        if near_margin:
            # Conservative AABB proximity refines even a near miss through a
            # hole. Every actual overlap above still uses solid intersection.
            # No distance-based continuous-clearance certificate is claimed.
            near = True
    return tuple(hits), near
