"""B-Rep bodies used by BOTH collision service and tessellated scene (mm)."""
from dataclasses import dataclass
from math import sin, cos, pi, tan
import numpy as np
from .kinematics import arc_parameters, basis, poses, station_transform
from .models import Region
from modules.gear_calculator.cad import compound, triangulate


@dataclass
class Body:
    id: str
    kind: str
    shape: object
    bounds: tuple
    base: object = None     # unplaced source solid (shared between poses) and its rigid placement;
    matrix: object = None   # lets the display mesh be built once per solid, not once per pose
    hull: object = None     # (points, unit axes) of a convex volume containing the solid, station mm


def bounds(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    b = Bnd_Box(); BRepBndLib.AddOptimal_s(shape, b, False, False)
    a, c = b.CornerMin(), b.CornerMax()
    return a.X(), a.Y(), a.Z(), c.X(), c.Y(), c.Z()


def body(id, kind, shape):
    return Body(id, kind, shape, bounds(shape))


def transform(shape, matrix):
    from OCP.gp import gp_Trsf
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    tr = gp_Trsf(); tr.SetValues(*map(float, np.asarray(matrix)[:3].reshape(-1)))
    # Rigid placement can share the original B-Rep and its triangulation.
    # OCCT copies automatically if a transform cannot be represented by location.
    return BRepBuilderAPI_Transform(shape, tr, False).Shape()


def joined(segments):
    """Abutting segments of one tool as single solids (same section end to end: the same volume).

    Fewer, simpler solids for the check and the scene; segments with a gap stay
    separate. A joined run keeps the number of its first segment in body ids.
    """
    from .models import Segment
    result = []
    for segment in sorted(segments, key=lambda s: s.start):
        if result and segment.length > 0 and result[-1].length > 0 and abs(result[-1].start+result[-1].length-segment.start) <= 1e-6:
            result[-1] = Segment(result[-1].start, result[-1].length+segment.length)
        else:
            result.append(segment)
    return result


def translation(x=0, y=0, z=0):
    result = np.eye(4); result[:3, 3] = x, y, z
    return result


def section_rotation(degrees):
    phi = degrees*pi/180
    result = np.eye(4)
    result[1:3, 1:3] = ((cos(phi), -sin(phi)), (sin(phi), cos(phi)))
    return result


def _wire(points):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt
    maker = BRepBuilderAPI_MakePolygon()
    for p in points:
        maker.Add(gp_Pnt(*map(float, p)))
    maker.Close()
    if not maker.IsDone():
        raise ValueError('Katı kesit teli üretilemedi.')
    return maker.Wire()


def prism(region, thickness):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec
    r = Region.from_polygon(region.polygon())
    face = BRepBuilderAPI_MakeFace(_wire([(x, y, -thickness/2) for x, y in r.outer]), True)
    for hole in r.holes:
        face.Add(_wire([(x, y, -thickness/2) for x, y in hole]))
    return BRepPrimAPI_MakePrism(face.Face(), gp_Vec(0, 0, thickness)).Shape()


def _bent_rectangle(bend, t, phi, x0, length):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.GC import GC_MakeArcOfCircle
    from OCP.gp import gp_Pnt, gp_Vec
    r, sign, a = arc_parameters(bend, t, phi), np.sign(phi), abs(phi)
    def p(d, angle):
        return gp_Pnt(x0, (r-sign*d)*sin(angle), sign*r*(1-cos(angle))+d*cos(angle))
    edges = [BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(p(-t/2, 0), p(-t/2, a/2), p(-t/2, a)).Value()).Edge(),
             BRepBuilderAPI_MakeEdge(p(-t/2, a), p(t/2, a)).Edge(),
             BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(p(t/2, a), p(t/2, a/2), p(t/2, 0)).Value()).Edge(),
             BRepBuilderAPI_MakeEdge(p(t/2, 0), p(-t/2, 0)).Edge()]
    wire = BRepBuilderAPI_MakeWire()
    for edge in edges:
        wire.Add(edge)
    face = BRepBuilderAPI_MakeFace(wire.Wire(), True)
    return BRepPrimAPI_MakePrism(face.Face(), gp_Vec(length, 0, 0)).Shape()


def bend_shape(bend, thickness, phi):
    if abs(phi) < 1e-9:
        return prism(bend.region, thickness)
    from shapely.ops import transform as shapely_transform
    inv = np.linalg.inv(basis(bend))
    def local(x, y, z=None):
        return inv[0, 0]*np.asarray(x)+inv[0, 1]*np.asarray(y)+inv[0, 3], inv[1, 0]*np.asarray(x)+inv[1, 1]*np.asarray(y)+inv[1, 3]
    region = shapely_transform(local, bend.region.polygon())
    xmin, ymin, xmax, ymax = region.bounds
    from shapely.geometry import box
    if abs(ymin) < 1e-5 and abs(ymax-bend.width) < 1e-5 and region.symmetric_difference(box(xmin, 0, xmax, bend.width)).area < 1e-5:
        return transform(_bent_rectangle(bend, thickness, phi, xmin, xmax-xmin), basis(bend))
    return transform(_faceted_bend(region, bend, thickness, phi), basis(bend))


def _faceted_bend(region, bend, t, phi):
    """Trimmed bend bands: shared-node closed faceted B-Rep, ≤2° per chord.

    Holes/reliefs are retained. Numerical clearance below the chord error is
    never certified by the collision service.
    """
    from shapely import constrained_delaunay_triangles, set_precision
    from shapely.geometry import box
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
    from OCP.TopoDS import TopoDS
    from OCP.BRepLib import BRepLib
    r, sign = arc_parameters(bend, t, phi), np.sign(phi)
    def mapped(x, y, d):
        angle = abs(phi)*y/bend.width
        return (x, (r-sign*d)*sin(angle), sign*r*(1-cos(angle))+d*cos(angle))
    # Slice first so long triangles cannot bridge the entire circular sector.
    count = max(1, int(abs(phi)*180/pi/2)+1)
    sewing = BRepBuilderAPI_Sewing(1e-6)
    def triangle(points):
        a, b, c = np.asarray(points)
        if np.linalg.norm(np.cross(b-a, c-a)) < 1e-8:
            return
        sewing.Add(BRepBuilderAPI_MakeFace(_wire(points), True).Face())
    for i in range(count):
        clipped = set_precision(region.intersection(box(region.bounds[0]-1, bend.width*i/count, region.bounds[2]+1, bend.width*(i+1)/count)), 1e-7)
        polygons = [clipped] if clipped.geom_type == 'Polygon' else [p for p in getattr(clipped, 'geoms', ()) if p.geom_type == 'Polygon']
        for polygon in polygons:
            for tri in constrained_delaunay_triangles(polygon).geoms:
                points = list(tri.exterior.coords)[:3]
                triangle([mapped(x, y, t/2) for x, y in points])
                triangle([mapped(x, y, -t/2) for x, y in points[::-1]])
            for ring in [polygon.exterior, *polygon.interiors]:
                points = list(ring.coords)
                for a, b in zip(points, points[1:]):
                    # Slice boundaries shared by adjacent strips are interior.
                    from shapely.geometry import LineString
                    line = LineString([a, b])
                    if region.boundary.buffer(2e-7).intersection(line).length < line.length-1e-6:
                        continue
                    v = [mapped(*a, -t/2), mapped(*b, -t/2), mapped(*b, t/2), mapped(*a, t/2)]
                    triangle([v[0], v[1], v[2]]); triangle([v[0], v[2], v[3]])
    sewing.Perform()
    shape = sewing.SewedShape()
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    shells = TopExp_Explorer(shape, TopAbs_SHELL); solids = []
    while shells.More():
        solid = BRepBuilderAPI_MakeSolid(TopoDS.Shell(shells.Current())).Solid()
        if not BRepLib.OrientClosedSolid_s(solid):
            raise ValueError(f'{bend.id}: kesikli büküm bölgesi kapalı katıya dönüşmedi.')
        solids.append(solid); shells.Next()
    if not solids:
        raise ValueError(f'{bend.id}: büküm bölgesi katı üretilemedi.')
    return compound(solids)


class Geometry:
    def __init__(self, plan=None):
        self.plan = plan
        self.flat = {f.id: prism(f.region, plan.part.thickness) for f in plan.part.flanges} if plan is not None else {}
        self.tools = {}
        self.bend_cache = {}
        self.placed_cache = {}
        self.mesh_cache = {}    # display triangles per source solid; see mesh()
        self.hulls = {}         # convex container per source solid; see local_hull()

    def placed_body(self, id, kind, shape, matrix):
        key = (id, kind, shape, tuple(np.asarray(matrix).ravel()))
        if key not in self.placed_cache:
            if len(self.placed_cache) >= 1024:
                self.placed_cache.clear()
            placed = body(id, kind, transform(shape, matrix))
            placed.base, placed.matrix = shape, np.array(matrix, dtype=float)
            points, axes = self.local_hull(shape); rotation = placed.matrix[:3, :3]
            placed.hull = (points@rotation.T+placed.matrix[:3, 3], axes@rotation.T)
            self.placed_cache[key] = placed
        return self.placed_cache[key]

    def local_hull(self, shape, section=None, span=None):
        """Convex container of a source solid in its own coordinates: (corner points, face normals).

        Extruded tools register the convex hull of their section; every other solid
        uses its bounding box (tight for a flat flange). Two solids whose containers
        are apart along any of these normals cannot touch, whatever their detail.
        """
        entry = self.hulls.get(id(shape))
        if entry is not None and entry[0] is shape:
            return entry[1], entry[2]
        if section is not None:
            ring = np.asarray(section.convex_hull.exterior.coords)[:-1]
            points = np.array([(x, y, z) for x in span for y, z in ring])
            edges = np.roll(ring, -1, axis=0)-ring
            normals = np.c_[np.zeros(len(edges)), edges[:, 1], -edges[:, 0]]
            normals = normals[np.linalg.norm(normals, axis=1) > 1e-9]
            axes = np.r_[[[1., 0, 0]], normals/np.linalg.norm(normals, axis=1)[:, None]]
        else:
            x0, y0, z0, x1, y1, z1 = bounds(shape)
            points = np.array([(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]); axes = np.eye(3)
        if len(self.hulls) >= 1024:
            self.hulls.clear()
        self.hulls[id(shape)] = (shape, points, axes)
        return points, axes

    def part_bodies(self, angles, station=None):
        p = self.plan.part
        transforms = poses(p, angles)
        result = []
        global_t = np.eye(4) if station is None else station
        for flange in p.flanges:
            result.append(self.placed_body(flange.id, 'sheet', self.flat[flange.id], global_t@transforms[flange.id]))
        for bend in p.bends:
            angle = angles.get(bend.id, 0)
            key = (bend.id, round(angle, 9))
            if key not in self.bend_cache:
                self.bend_cache[key] = bend_shape(bend, p.thickness, angle)
                from modules.gear_calculator.cad import shape_stats
                shape_stats(self.bend_cache[key])
            result.append(self.placed_body(bend.id, 'sheet', self.bend_cache[key], global_t@transforms[bend.parent]))
        return result

    def tool_shape(self, tool, segment):
        key = (tool.id, segment.start, segment.length, tool.section_dxf, tool.contour_index)
        if key in self.tools:
            return self.tools[key]
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeEdge
        from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
        from OCP.gp import gp_Pnt, gp_Vec
        from OCP.GC import GC_MakeArcOfCircle
        def wire(edges):
            from OCP.BRep import BRep_Builder
            from OCP.TopExp import TopExp
            maker = BRepBuilderAPI_MakeWire()
            builder = BRep_Builder()
            def add(edge):
                # The DXF reader joins endpoints within 1e-6 mm. Carry the
                # same tolerance into OCCT without moving lines or arcs.
                for vertex in (TopExp.FirstVertex_s(edge), TopExp.LastVertex_s(edge)):
                    builder.UpdateVertex(vertex, 1e-6)
                maker.Add(edge)
                if not maker.IsDone():
                    raise ValueError('Takım kesiti kenarları kapalı tele bağlanamadı.')
            for edge in edges:
                a = gp_Pnt(segment.start, *edge.start); b = gp_Pnt(segment.start, *edge.end)
                if edge.center:
                    if abs(abs(edge.sweep)-2*pi) < 1e-8:
                        # Split a full circle into two exact circular edges.
                        from .tooling import Edge
                        opposite = (edge.center[0]+edge.radius*cos(edge.a0+edge.sweep/2), edge.center[1]+edge.radius*sin(edge.a0+edge.sweep/2))
                        half = Edge(edge.start, opposite, edge.center, edge.radius, edge.a0, edge.sweep/2)
                        for e in (half, Edge(half.end, half.start, edge.center, edge.radius, edge.a0+edge.sweep/2, edge.sweep/2)):
                            mid = gp_Pnt(segment.start, edge.center[0]+edge.radius*cos(e.a0+e.sweep/2), edge.center[1]+edge.radius*sin(e.a0+e.sweep/2))
                            add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(gp_Pnt(segment.start, *e.start), mid, gp_Pnt(segment.start, *e.end)).Value()).Edge())
                        continue
                    mid = gp_Pnt(segment.start, edge.center[0]+edge.radius*cos(edge.a0+edge.sweep/2), edge.center[1]+edge.radius*sin(edge.a0+edge.sweep/2))
                    add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(a, mid, b).Value()).Edge())
                else:
                    add(BRepBuilderAPI_MakeEdge(a, b).Edge())
            return maker.Wire()
        if tool.section_dxf:
            from .tooling import sections
            from shapely.geometry import Polygon
            region, edges, holes = sections(tool.section_dxf, accept_unitless=True)[tool.contour_index]
            def oriented_wire(edges, ccw):
                result = wire(edges)
                points = [p for edge in edges for p in edge.samples()[:-1]]
                if Polygon(points).exterior.is_ccw != ccw:
                    result.Reverse()
                return result
            from OCP.gp import gp_Pln, gp_Dir
            plane = gp_Pln(gp_Pnt(segment.start, 0, 0), gp_Dir(1, 0, 0))
            maker = BRepBuilderAPI_MakeFace(plane, oriented_wire(edges, True), True)
            for loop in holes:
                maker.Add(oriented_wire(loop, False))
            face = maker.Face()
        else:
            r = Region.from_polygon(tool.section.polygon())
            maker = BRepBuilderAPI_MakeFace(_wire([(segment.start, y, z) for y, z in r.outer]), True)
            for hole in r.holes:
                maker.Add(_wire([(segment.start, y, z) for y, z in hole]))
            face = maker.Face()
        shape = BRepPrimAPI_MakePrism(face, gp_Vec(segment.length, 0, 0)).Shape()
        from modules.gear_calculator.cad import shape_stats
        shape_stats(shape)
        self.tools[key] = shape
        outline = region.polygon() if tool.section_dxf else tool.section.polygon()
        self.local_hull(shape, outline, (segment.start, segment.start+segment.length))
        return shape

    def scene(self, index, angles, phase='bend', travel=0):
        plan, t = self.plan, self.plan.part.thickness
        step = plan.steps[index]; bend = next(b for b in plan.part.bends if b.id == step.bend)
        station = station_transform(plan, index, angles)
        result = self.part_bodies(angles, station)
        punch, die = plan.tool(step.punch), plan.tool(step.die)
        channel = next((c for c in die.channels if c.id == step.channel), None)
        phi = abs(angles.get(bend.id, 0))
        # Active tangents symmetric to V. Place die shoulders on lower sheet
        # surface at ±V/2; punch tip follows the upper centre surface.
        die_z = -t/2
        shoulder = (channel.shoulder_radius or 0.) if channel else 0.
        lip_angle = (pi-channel.angle*pi/180)/2 if channel else 0.
        contact_y = channel.opening/2+shoulder*tan(lip_angle/2) if channel else 0.
        contact_z = die_z
        if channel and phi > 1e-8:
            r = arc_parameters(bend, t, phi)
            half = phi/2
            tangent_y = (r+t/2)*sin(half)
            tangent_z = (r+t/2)*(1-cos(half))-t/2
            if shoulder and half > lip_angle+1e-7:
                raise ValueError(f'{bend.id}: hedef büküm V kanalının açısını aşıyor; omuz teması çözülemedi.')
            contact_y = channel.opening/2+shoulder*tan(lip_angle/2)-shoulder*sin(half)
            if contact_y < tangent_y:
                raise ValueError(f'{bend.id}: V açıklığı hedef büküm bölgesinden dar; destek temas geometrisi çözülemedi.')
            contact_z = tangent_z+(contact_y-tangent_y)*sin(half)/cos(half)
            die_z = contact_z+shoulder*(1-cos(half))
        placements = ((punch, step.punch_segments, translation(y=-(punch.tip or (0, 0))[0], z=t/2-(punch.tip or (0, 0))[1]+travel)),
                      (die, step.die_segments, translation(y=-channel.center[0], z=die_z-channel.center[1])@section_rotation(channel.rotation) if channel else np.eye(4)))
        for tool, chosen_segments, tr in placements:
            if tool.section is None:
                continue
            from .standard import default_segments, is_generic
            for j, segment in enumerate(joined(chosen_segments if chosen_segments is not None else default_segments(tool, bend))):
                if segment.length <= 0:
                    raise ValueError(f'{tool.code}: segment boyu pozitif olmalı.')
                result.append(self.placed_body(f'{tool.kind}:{tool.code}:{j+1}', tool.kind, self.tool_shape(tool, segment), tr))
            if tool.holder_section is not None:
                from dataclasses import replace
                holder = replace(tool, id=tool.id+':holder', section=tool.holder_section, section_dxf=tool.holder_dxf, contour_index=0)
                # A generic clamp follows the station it holds; supplier holders keep their own layout.
                holder_segments = (chosen_segments if chosen_segments is not None else default_segments(tool, bend)) if is_generic(tool) else tool.holder_segments
                for j, holder_segment in enumerate(joined(holder_segments)):
                    result.append(self.placed_body(f'holder:{tool.kind}:{j+1}', 'holder', self.tool_shape(holder, holder_segment), tr))
        adjacent = (bend.id, bend.parent, bend.child)
        contacts = [('punch', 0., t/2, .3, adjacent)] if phase == 'bend' or travel <= .2 else []
        # Local contact cylinders only. A whole active flange is NEVER exempt.
        if channel:
            contacts += [('die', -contact_y, contact_z, .3, adjacent), ('die', contact_y, contact_z, .3, adjacent)]
        return result, contacts


# Display colours per body kind (scene, legend, labels and PDF share them).
SCENE_COLOURS = {'sheet': '#4A86D4', 'punch': '#C9D0D8', 'die': '#8E99A6', 'holder': '#5E7A96', 'machine': '#6B7580'}


def rgb(colour):
    return tuple(int(colour[i:i+2], 16) for i in (1, 3, 5))


MACHINE_NOTE = 'Üst kiriş ve alt ray yalnız görseldir; çarpışma kontrolüne dahil değildir.'


def machine_bodies(bodies):
    """Schematic upper beam above the punch stack and lower rail below the die stack (mm).

    Display only: never passed to the collision check, never in reports' hit lists.
    Generic proportions, not a specific machine model.
    """
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    tools = [b for b in bodies if b.kind in ('punch', 'die', 'holder')]
    if not tools:
        return []
    x0 = min(b.bounds[0] for b in bodies)-15; x1 = max(b.bounds[3] for b in bodies)+15
    def box(id, y, z0, z1):
        return Body(id, 'machine', BRepPrimAPI_MakeBox(gp_Pnt(x0, -y, z0), gp_Pnt(x1, y, z1)).Shape(), (x0, -y, z0, x1, y, z1))
    result = []
    upper = [b for b in tools if b.kind == 'punch' or b.id.startswith('holder:punch')]
    lower = [b for b in tools if b.kind == 'die' or b.id.startswith('holder:die')]
    if upper:
        top = max(b.bounds[5] for b in upper); result.append(box('machine:beam', 14, top, top+28))
    if lower:
        bottom = min(b.bounds[2] for b in lower); result.append(box('machine:rail', 24, bottom-22, bottom))
    return result


def scene_mesh(bodies, stop=None, cache=None):
    """Scene for one pose: the checked bodies plus the display-only machine."""
    return mesh(list(bodies)+machine_bodies(bodies), stop, cache)


DISPLAY = np.array([[1., 0, 0], [0, 0, 1.], [0, -1., 0]])   # station Z-up -> viewer Y-up (rigid, display only)
CREASE = .8660254                                           # cos 30 deg, as in the shared preview mesh


def solid_part(shape, stop=None):
    """Display triangles of one solid in its own coordinates: corners, smooth normals, crease/boundary edges."""
    from modules.cad_converter.models import checkpoint
    from modules.dxf_dwg.preview.geometry import smooth_normals
    checkpoint(stop)
    try:
        points = np.asarray(triangulate([shape], .08), dtype=float).reshape(-1, 3, 3)
    except ValueError as error:   # a solid without faces adds nothing
        if 'üretilemedi' not in str(error):
            raise
        return None
    normals = np.cross(points[:, 1]-points[:, 0], points[:, 2]-points[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-12
    points, normals, lengths = points[valid], normals[valid]/np.maximum(lengths[valid], 1e-300)[:, None], lengths[valid]
    if not len(points):
        return None
    vertices = points.reshape(-1, 3)
    quantum = max(float(np.max(vertices.max(axis=0)-vertices.min(axis=0)))*1e-8, 1e-7)
    # Edges: keep boundaries and >= 30 degree creases, not every triangle diagonal.
    _, ids = np.unique(np.rint(vertices/quantum).astype(np.int64), axis=0, return_inverse=True)
    ids = ids.ravel().reshape(-1, 3)
    a, b = ids[:, [0, 1, 2]].ravel(), ids[:, [1, 2, 0]].ravel()
    keys = np.minimum(a, b)*(int(ids.max())+1)+np.maximum(a, b)
    _, first, inverse, counts = np.unique(keys, return_index=True, return_inverse=True, return_counts=True)
    triangle = np.repeat(np.arange(len(points)), 3)
    smooth_with_first = np.einsum('ij,ij->i', normals[triangle[first][inverse.ravel()]], normals[triangle]) >= CREASE
    crease = np.zeros(len(first), dtype=bool); np.logical_or.at(crease, inverse.ravel(), ~smooth_with_first)
    keep = first[(counts == 1) | crease]
    corner = keep % 3; row = keep//3
    lines = np.stack([points[row, corner], points[row, (corner+1) % 3]], axis=1).reshape(-1, 3)
    return vertices, smooth_normals(vertices, normals, lengths, quantum, stop), lines


def mesh(bodies, stop=None, cache=None):
    """One coloured display mesh for the bodies of a pose.

    ``cache`` (a dict kept by the caller for one calculation) stores each source
    solid's triangles once; a pose then only applies the rigid placements. Without
    it every body is triangulated as placed. Display only: collision uses the solids.
    """
    from modules.dxf_dwg.preview.models import Mesh
    vertices, normals, lines, colours = [], [], [], []
    for b in bodies:
        if cache is not None and b.base is not None:
            entry = cache.get(id(b.base))
            if entry is None or entry[0] is not b.base:
                if len(cache) >= 512:
                    cache.clear()
                entry = cache[id(b.base)] = (b.base, solid_part(b.base, stop))   # keeps the solid alive: ids stay unique
            part, rotation, shift = entry[1], b.matrix[:3, :3], b.matrix[:3, 3]
        else:
            part, rotation, shift = solid_part(b.shape, stop), np.eye(3), np.zeros(3)
        if part is None:
            continue
        turn = DISPLAY@rotation
        vertices.append(part[0]@turn.T+DISPLAY@shift); normals.append(part[1]@turn.T); lines.append(part[2]@turn.T+DISPLAY@shift)
        colours.append(np.tile(np.array(rgb(SCENE_COLOURS.get(b.kind, SCENE_COLOURS['sheet'])), dtype=np.uint8), (len(part[0])//3, 1)))
    if not vertices:
        raise ValueError('Katıdan görüntülenebilir üçgen üretilemedi.')
    vertices = np.concatenate(vertices)
    if len(vertices) > 120000*3:
        raise ValueError('3D önizleme 120.000 üçgen sınırını aşıyor; 2D/STEP kullanın.')
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    if np.max(high-low) <= 0 or not np.isfinite(vertices).all():
        raise ValueError('3D parça sınırları geçersiz.')
    origin = (low+high)/2   # keeps float32 precision for a small part far from the origin
    return Mesh((vertices-origin).astype('<f4').tobytes(), np.concatenate(normals).astype('<f4').tobytes(),
                (np.concatenate(lines)-origin).astype('<f4').tobytes(), tuple(low-origin)+tuple(high-origin),
                len(vertices)//3, tuple(origin), np.concatenate(colours).tobytes())
