"""The 2D section proof that skips the solid boolean must never hide an overlap."""
from itertools import combinations
import numpy as np
import pytest
from modules.press_brake import collision
from modules.press_brake.demo import load_demo
from modules.press_brake.geometry import Geometry, translation
from modules.press_brake.kinematics import step_angles


def facets(points):
    """Outward planes (normal, offset) of the convex hull of a few points."""
    out = []
    for i, j, k in combinations(range(len(points)), 3):
        n = np.cross(points[j]-points[i], points[k]-points[i]); length = np.linalg.norm(n)
        if length < 1e-12:
            continue
        n /= length; d = (points-points[i])@n
        if (d <= 1e-9).all():
            out.append((n, points[i]@n))
        elif (d >= -1e-9).all():
            out.append((-n, -(points[i]@n)))
    return out


def surface_points(shape):
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    BRepMesh_IncrementalMesh(shape, .01, False, .05, True)
    explorer, points = TopExp_Explorer(shape, TopAbs_FACE), []
    while explorer.More():
        location = TopLoc_Location(); tri = BRep_Tool.Triangulation_s(TopoDS.Face(explorer.Current()), location)
        if tri is not None:
            tr = location.Transformation()
            for i in range(1, tri.NbNodes()+1):
                p = tri.Node(i).Transformed(tr); points.append((p.X(), p.Y(), p.Z()))
        explorer.Next()
    return np.array(points)


@pytest.mark.parametrize('kind', ['L120', 'box'])
def test_convex_pieces_contain_every_sheet_solid(kind):
    plan = load_demo(kind); g = Geometry(plan)
    for fraction in (0, .4, 1):
        for body in g.part_bodies(step_angles(plan, len(plan.steps)-1, fraction)):
            points = surface_points(body.base); inside = np.zeros(len(points), bool)
            for piece in g.covers[id(body.base)][1]:
                planes = facets(piece)
                normals = np.array([n for n, _ in planes]); offsets = np.array([c for _, c in planes])
                inside |= ((points@normals.T-offsets) <= 1e-7).all(axis=1)
            assert inside.all(), (body.id, fraction, points[~inside][:3])


@pytest.mark.timeout(120)
def test_section_proof_agrees_with_the_solid_boolean_and_catches_a_pushed_in_tool():
    plan = load_demo('L120'); g = Geometry(plan)
    proven = 0
    for fraction, phase in ((0, 'approach'), (.5, 'bend'), (1, 'bend')):
        bodies, contacts = g.scene(0, step_angles(plan, 0, fraction), phase, 0)
        tools = [b for b in bodies if b.prism is not None]; sheet = [b for b in bodies if b.kind == 'sheet']
        assert tools and all(b.pieces is not None for b in sheet)
        for tool in tools:
            for s in sheet:
                if collision.prism_clear(tool, s, contacts):
                    proven += 1
                    common = collision.intersection(tool.shape, s.shape); mass, _ = collision.volume(common)
                    if mass > 1e-5:
                        mass, _ = collision.volume(collision.remove_contacts(common, tool, s, contacts))
                    assert mass <= .001, (tool.id, s.id, fraction)
        # The punch pushed 2 mm into the sheet: never proven clear, and the boolean reports it.
        punch = next(b for b in tools if b.kind == 'punch')
        pushed = g.placed_body(punch.id, 'punch', punch.base, translation(z=-2)@punch.matrix)
        hits, _ = collision.check([pushed]+sheet, contacts)
        assert hits and not all(collision.prism_clear(pushed, s, contacts) for s in sheet)
    assert proven >= 6


def test_tool_against_tool_uses_the_exact_sections():
    plan = load_demo('L120'); g = Geometry(plan)
    bodies, _ = g.scene(0, step_angles(plan, 0, 0), 'approach', 10)
    punch = next(b for b in bodies if b.kind == 'punch'); die = next(b for b in bodies if b.kind == 'die')
    assert collision.prism_clear(punch, die)
    low = g.placed_body(punch.id, 'punch', punch.base, translation(z=-40)@punch.matrix)
    assert not collision.prism_clear(low, die)
    assert collision.check([low, die])[0]
