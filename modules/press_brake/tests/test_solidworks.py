"""Published API doubles, not a live SolidWorks qualification."""
from math import radians
from types import SimpleNamespace as NS
import threading
import numpy as np
import pytest
from shapely.ops import unary_union
from modules.cad_converter.models import Cancelled
from modules.cad_converter.api import ApiError, RestoreError
from modules.press_brake.demo import load_demo
from modules.press_brake import solidworks as sw
from modules.press_brake.models import Region


def test_partition_real_contour_holes_and_non_90_angle():
    p = load_demo('L120').part; b = p.bends[0]
    outline = Region.from_polygon(unary_union([f.region.polygon() for f in p.flanges]+[b.region.polygon()]))
    row = dict(id='persist:B01', start=b.start, end=b.end, width=b.width, turn=60, radius=2, direction=1)
    got = sw.partition('Part', 'Active-2mm', 'S235', 2, outline, [row], (-20, 0), 'face:root', 'source.SLDPRT')
    assert got.configuration == 'Active-2mm' and got.bends[0].inside_angle == 120
    assert got.bends[0].direction == 1 and sum(len(f.region.holes) for f in got.flanges) == 2
    assert got.bends[0].width == pytest.approx(b.width)


def test_partition_ambiguity_is_explicit_instead_of_defaulting_a_bend():
    p = load_demo('L120').part; b = p.bends[0]
    outline = Region.from_polygon(unary_union([f.region.polygon() for f in p.flanges]+[b.region.polygon()]))
    bad = dict(id='B-missing-axis', start=(0, 0), end=(1, 0), width=3, turn=60, radius=2, direction=1)
    with pytest.raises(ApiError, match='B-missing-axis'):
        sw.partition('Part', 'A', '', 2, outline, [bad], (-20, 0), 'root', 'source')


class Feature:
    def __init__(self, name, definition, suppressed=False):
        self.Name = name; self.ref = name; self.definition = definition; self.suppressed = suppressed; self.history = []
    def IsSuppressed2(self, configuration, names):
        assert configuration == 1
        return (self.suppressed,)
    def SetSuppression2(self, mode, configuration, names):
        self.history.append((mode, configuration)); self.suppressed = mode == 0; return True
    def GetDefinition(self):
        return self.definition
    def GetFaces(self):
        return (NS(ref='bend-cylinder'),)


def _face(region, id):
    def loop(points, outer):
        edges = []
        for a, b in zip(points, points[1:]+points[:1]):
            a, b = (*[v/1000 for v in a], 0.), (*[v/1000 for v in b], 0.)
            curve = NS(GetTessPts=lambda tol, length_tol, start, end, a=a, b=b: a+b)
            cp = NS(StartPoint=a, EndPoint=b)
            edges.append(NS(GetCurve=lambda curve=curve: curve, GetCurveParams3=lambda cp=cp: cp))
        return NS(GetEdges=lambda: tuple(edges), IsOuter=lambda: outer)
    surface = NS(IsPlane=lambda: True, PlaneParams=(0, 0, 1, 0, 0, 0))
    loops = [loop(list(region.outer), True)]+[loop(list(h), False) for h in region.holes]
    return NS(ref=id, GetSurface=lambda: surface, GetLoops=lambda: tuple(loops))


@pytest.fixture
def capture(tmp_path):
    p = load_demo('L120').part; b = p.bends[0]
    path = tmp_path/'source.SLDPRT'; path.write_bytes(b'unchanged native source')
    faces = [_face(f.region, f.id) for f in p.flanges]+[_face(b.region, b.id)]
    body = NS(Name='Sheet-body', IsSheetMetal=lambda: True, GetFaces=lambda: tuple(faces))
    def segment(a, b):
        def xyz(p):
            return NS(X=p[0]/1000, Y=p[1]/1000, Z=0.)
        transform = NS(Inverse=lambda: 'inverse-transform')
        sketch = NS(ModelToSketchTransform=transform)
        return NS(GetType=lambda: 0, GetSketch=lambda: sketch, GetStartPoint2=lambda: xyz(a), GetEndPoint2=lambda: xyz(b))
    n = np.array([0, b.width])
    bend_def = NS(BendAngle=radians(60), BendRadius=.002, BendDirection=1,
                  FlatPatternSketchSegments2=(segment(b.start, b.end), segment(tuple(np.array(b.start)+n), tuple(np.array(b.end)+n))))
    bend = Feature('Bend-60', bend_def)
    flat = Feature('Flat-Pattern', NS(FixedFace2=faces[0]), True)
    manager = NS(suspended=0)
    def suspend():
        manager.suspended += 1
    def resume(append):
        assert append is False; manager.suspended -= 1
    manager.SuspendSelectionList = suspend; manager.ResumeSelectionList2 = resume
    model = NS(SelectionManager=manager, Extension=NS(NeedsRebuild2=0), ConfigurationManager=NS(ActiveConfiguration=NS(Name='Actual-Active')),
               GetType=lambda: 1, GetPathName=lambda: str(path), GetTitle=lambda: 'source.SLDPRT',
               GetBodies2=lambda *args: (body,), EditRebuild3=lambda: True)
    def math_point(data):
        return NS(MultiplyTransform=lambda transform: NS(ArrayData=data.value))
    app = NS(ActiveDoc=model, GetMathUtility=lambda: NS(CreatePoint=math_point))
    constants = {'swDocPART': 1, 'swSolidBody': 0, 'swThisConfiguration': 1, 'swUnSuppressFeature': 1,
                 'swSuppressFeature': 0, 'swSketchLINE': 0, 'swBendDirection_UP': 1, 'swBendDirection_DOWN': 2}
    state = NS(entered=0, exited=0)
    class Session(sw.Capture):
        def __enter__(self):
            self.app = app; self.constants = constants; state.entered += 1; return self
        def __exit__(self, *args):
            state.exited += 1; self.app = None
        def part(self, model):
            return model
        def features(self, model, stop):
            yield bend, 'OneBend'; yield flat, 'FlatPattern'
        def persistent_ref(self, model, obj):
            return getattr(obj, 'ref', getattr(obj, 'Name', 'missing'))
        def thickness(self, *args):
            return 2.
        def document_properties(self, *args):
            return {}
        def material(self, *args):
            return 'S235'
    return NS(session=Session, model=model, flat=flat, bend=bend, body=body, manager=manager, path=path, state=state)


def test_actual_active_configuration_units_id_and_source_restored_on_success(capture):
    before = capture.path.read_bytes()
    part = sw.read_active(session_factory=capture.session)
    assert part.configuration == 'Actual-Active' and part.thickness == 2
    assert part.bends[0].radius == 2 and part.bends[0].inside_angle == pytest.approx(120)
    assert part.bends[0].id.startswith('SWB-') and part.bends[0].title == 'Bend-60'
    assert capture.flat.suppressed and not capture.bend.suppressed
    assert capture.manager.suspended == 0 and capture.state.entered == capture.state.exited == 1
    assert capture.path.read_bytes() == before


def test_persistent_bend_id_survives_feature_rename(capture):
    first = sw.read_active(session_factory=capture.session)
    capture.bend.Name = 'New display name'
    second = sw.read_active(session_factory=capture.session)
    assert first.bends[0].id == second.bends[0].id
    assert first.bends[0].title != second.bends[0].title


@pytest.mark.parametrize('failure', ['exception', 'cancel'])
def test_source_feature_and_selection_state_restored_on_error_and_cancel(capture, failure):
    stop = threading.Event()
    def broken_faces():
        if failure == 'cancel':
            stop.set(); raise Cancelled()
        raise RuntimeError('deliberate geometry read failure')
    capture.body.GetFaces = broken_faces
    with pytest.raises(Cancelled if failure == 'cancel' else RuntimeError):
        sw.read_active(stop, session_factory=capture.session)
    assert capture.flat.suppressed and not capture.bend.suppressed and capture.manager.suspended == 0
    assert capture.path.read_bytes() == b'unchanged native source'
    assert capture.state.entered == capture.state.exited


def test_missing_radius_is_named_and_does_not_flatten_or_guess(capture):
    del capture.bend.definition.BendRadius
    with pytest.raises(ApiError, match='Bend-60.*iç R'):
        sw.read_active(session_factory=capture.session)
    assert capture.flat.suppressed and not capture.flat.history


def test_pending_rebuild_and_unmapped_partial_cylinder_cannot_skip_bends(capture):
    capture.model.Extension.NeedsRebuild2 = 1
    with pytest.raises(ApiError, match='Ctrl\\+Q'):
        sw.read_active(session_factory=capture.session)
    capture.model.Extension.NeedsRebuild2 = 0
    original = capture.body.GetFaces
    missing = NS(ref='unmapped-bend', GetSurface=lambda: NS(IsPlane=lambda: False, IsCylinder=lambda: True),
                 GetUVBounds=lambda: (0., 1., 0., .05))
    capture.body.GetFaces = lambda: original()+(missing,)
    with pytest.raises(ApiError, match='unmapped-bend.*atlanmadı'):
        sw.read_active(session_factory=capture.session)
    assert capture.flat.suppressed and not capture.flat.history


def test_unsupported_multibody_and_restore_failure_are_not_success(capture):
    capture.model.GetBodies2 = lambda *args: (capture.body, capture.body)
    with pytest.raises(ApiError, match='2 gövde'):
        sw.read_active(session_factory=capture.session)
    capture.model.GetBodies2 = lambda *args: (capture.body,)
    original = capture.flat.SetSuppression2
    capture.flat.SetSuppression2 = lambda mode, *args: False if mode == 0 else original(mode, *args)
    with pytest.raises(RestoreError, match='Flat-Pattern'):
        sw.read_active(session_factory=capture.session)
