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
    with pytest.raises(ApiError, match='Sheet-body / yüz #[a-f0-9]{10}.*atlanmadı'):
        sw.read_active(session_factory=capture.session)
    assert capture.flat.suppressed and not capture.flat.history


def _cylinder_face(ref, radius, origin=(0., 0., 0.), owner=None, angle=radians(60)):
    surface = NS(IsPlane=lambda: False, IsCylinder=lambda: True,
                 CylinderParams=(*origin, 1., 0., 0., radius))
    return NS(ref=ref, GetSurface=lambda: surface, GetUVBounds=lambda: (0., angle, 0., .08), GetFeature=lambda: owner)


def test_outer_skin_of_a_measured_onebend_matches_without_equal_face_ids(capture):
    original = capture.body.GetFaces
    inner = _cylinder_face('inner', .002)
    outer = _cylinder_face('outer', .004)
    capture.bend.GetFaces = lambda: (inner,)
    capture.body.GetFaces = lambda: original()+(inner, outer)
    part = sw.read_active(session_factory=capture.session)
    assert len(part.bends) == 1 and part.bends[0].radius == 2
    assert capture.flat.suppressed and capture.manager.suspended == 0


def test_edge_flange_owning_feature_is_matched_with_measured_angle_and_radius(capture):
    original = capture.body.GetFaces
    parent = NS(ref='edge-flange', Name='Kenar-Flanş1', GetOwnerFeature=lambda: None)
    capture.bend.GetOwnerFeature = lambda: parent
    outer = _cylinder_face('outer', .004, owner=parent)
    capture.body.GetFaces = lambda: original()+(outer,)
    assert sw.read_active(session_factory=capture.session).bends[0].label == 'Bend-60'
    outer.GetSurface().CylinderParams = (0., 0., 0., 1., 0., 0., .008)
    with pytest.raises(ApiError, match='Kenar-Flanş1 / yüz #.*atlanmadı'):
        sw.read_active(session_factory=capture.session)
    assert capture.flat.suppressed and capture.manager.suspended == 0


def test_unrelated_cylinder_cannot_match_by_radius_and_angle_alone(capture):
    original = capture.body.GetFaces
    inner = _cylinder_face('inner', .002)
    outer = _cylinder_face('persist:'+'X'*3000, .004, origin=(0., .01, 0.))
    capture.bend.GetFaces = lambda: (inner,)
    capture.body.GetFaces = lambda: original()+(outer,)
    with pytest.raises(ApiError, match='atlanmadı') as caught:
        sw.read_active(session_factory=capture.session)
    assert len(str(caught.value)) < 250 and 'persist:' not in str(caught.value)
    assert capture.flat.suppressed and not capture.flat.history


def test_centreline_uses_an_actual_feature_owned_flat_face_not_an_assumed_allowance(capture):
    from shapely.geometry import box
    row = dict(id='measured', turn=60, radius=2)
    width = 3*radians(60)
    lines = [((-40, width/2), (40, width/2))]
    band = sw._band(row, lines, [box(-40, 0, 40, width)], 2)
    assert band['width'] == pytest.approx(width) and band['start'] == pytest.approx((-40, 0))
    for zones in ([], [box(-40, 0, 40, 50)]):
        with pytest.raises(ApiError, match='ölçülmüş'):
            sw._band(row, lines, zones, 2)


def test_rounded_contour_sidewall_is_not_an_unmapped_bend(capture):
    original = capture.body.GetFaces
    sidewall = _cylinder_face('rounded-corner', .006, angle=radians(90))
    sidewall.GetSurface().CylinderParams = (0., 0., 0., 0., 0., 1., .006)
    skins = [NS(GetSurface=lambda z=z: NS(IsPlane=lambda: True, PlaneParams=(0., 0., 1., 0., 0., z))) for z in (0., -.002)]
    sidewall.GetEdges = lambda: (NS(GetTwoAdjacentFaces2=lambda: tuple(skins)),)
    capture.body.GetFaces = lambda: original()+(sidewall,)
    assert len(sw.read_active(session_factory=capture.session).bends) == 1
    skins[1] = NS(GetSurface=lambda: NS(IsPlane=lambda: True, PlaneParams=(0., 0., 1., 0., 0., -.005)))
    with pytest.raises(ApiError, match='atlanmadı'):
        sw.read_active(session_factory=capture.session)


def test_unsupported_multibody_and_restore_failure_are_not_success(capture):
    capture.model.GetBodies2 = lambda *args: (capture.body, capture.body)
    with pytest.raises(ApiError, match='2 gövde'):
        sw.read_active(session_factory=capture.session)
    capture.model.GetBodies2 = lambda *args: (capture.body,)
    original = capture.flat.SetSuppression2
    capture.flat.SetSuppression2 = lambda mode, *args: False if mode == 0 else original(mode, *args)
    with pytest.raises(RestoreError, match='Flat-Pattern'):
        sw.read_active(session_factory=capture.session)


def test_sketched_bend_definitions_are_read_like_one_bends(capture):
    session = capture.session
    class Sketched(session):
        def features(self, model, stop):
            yield capture.bend, 'SketchBend'; yield capture.flat, 'FlatPattern'
    part = sw.read_active(session_factory=Sketched)
    assert part.bends[0].inside_angle == pytest.approx(120) and part.bends[0].title == 'Bend-60'


def test_missing_bends_name_the_sheet_features_that_were_found(capture):
    session = capture.session
    base = Feature('Base-Flange1', NS()); hidden = Feature('Bend7', NS(), True)
    class Unknown(session):
        def features(self, model, stop):
            yield base, 'SMBaseFlange'; yield hidden, 'SM3dBend'; yield Feature('Cut-Extrude2', NS()), 'Cut'
            yield capture.flat, 'FlatPattern'
    with pytest.raises(ApiError) as error:
        sw.read_active(session_factory=Unknown)
    text = str(error.value)
    assert 'Gövde «Sheet-body»' in text and 'Base-Flange1 (SMBaseFlange)' in text
    assert 'Bend7 (SM3dBend, bastırılmış)' in text and 'Flat-Pattern (FlatPattern, bastırılmış)' in text
    assert 'Cut-Extrude2' not in text


def _bend_cylinder(ref, radius_mm, axis_origin=(0, 30, 0), span=60):
    surface = NS(IsPlane=lambda: False, IsCylinder=lambda: True,
                 CylinderParams=(*[v/1000 for v in axis_origin], 1, 0, 0, radius_mm/1000))
    return NS(ref=ref, GetSurface=lambda: surface, GetUVBounds=lambda: (0, radians(span), 0, 1),
              GetEdges=lambda: (), GetFeature=lambda: None)


def _base_flange_part(capture, cylinders):
    """Base-flange bends: no OneBend; the bend is a UiBend under a suppressed Flat-Pattern."""
    folded = capture.body.GetFaces()
    capture.body.GetFaces = lambda: tuple(folded)+tuple(cylinders)
    flat = capture.flat
    class FlatBend(Feature):
        @property
        def suppressed(self):                       # follows its Flat-Pattern, as in SOLIDWORKS
            return flat.suppressed
        @suppressed.setter
        def suppressed(self, value):
            pass
    uibend = FlatBend('Bend1', capture.bend.definition)
    session = capture.session
    class BaseFlange(session):
        def features(self, model, stop):
            yield Feature('Base-Flange1', NS()), 'SMBaseFlange'; yield flat, 'FlatPattern'; yield uibend, 'UiBend'
    return BaseFlange


def test_base_flange_bends_are_read_from_the_unfolded_flat_pattern(capture):
    reader = _base_flange_part(capture, [_bend_cylinder('inner', 2), _bend_cylinder('outer', 4)])
    part = sw.read_active(session_factory=reader)
    assert len(part.bends) == 1 and part.bends[0].title == 'Bend1'
    assert part.bends[0].inside_angle == pytest.approx(120) and part.bends[0].radius == 2
    assert capture.flat.suppressed                                         # restored after reading


def test_base_flange_bend_without_matching_faces_or_an_extra_cylinder_is_not_guessed(capture):
    with pytest.raises(ApiError, match='büküm yüzü bulunamadı'):
        sw.read_active(session_factory=_base_flange_part(capture, []))
    assert capture.flat.suppressed


def test_unrelated_cylinder_next_to_a_base_flange_bend_is_refused(capture):
    extra = _bend_cylinder('stray', 2, axis_origin=(0, -30, 0), span=45)
    reader = _base_flange_part(capture, [_bend_cylinder('inner', 2), extra])
    with pytest.raises(ApiError, match='eşleştirilemedi'):
        sw.read_active(session_factory=reader)


def _merged_flat(capture, enabled=True):
    """Feature data is a fresh copy; failed commits may still change the model."""
    state = NS(merged=enabled, edits=[], access=0, released=0, rolled_back=False,
               reject=False, reject_after_write=False, reject_restore=False)
    fixed = capture.flat.definition.FixedFace2
    split = capture.body.GetFaces()
    merged = _face(Region.from_polygon(unary_union([f.region.polygon() for f in load_demo('L120').part.flanges]
                         +[b.region.polygon() for b in load_demo('L120').part.bends])), 'merged-face')
    capture.body.GetFaces = lambda: (merged,) if not capture.flat.suppressed and state.merged else split
    def definition():
        def access(model, component):
            assert model is capture.model and component.varianttype == 9
            state.access += 1; state.rolled_back = True; return True
        def release():
            state.released += 1; state.rolled_back = False
        return NS(FixedFace2=fixed, MergeFace=state.merged, AccessSelections=access, ReleaseSelectionAccess=release)
    capture.flat.GetDefinition = definition
    def modify(data, model, component):
        assert model is capture.model and component.varianttype == 9 and state.rolled_back
        state.edits.append(data.MergeFace)
        if state.reject_restore and data.MergeFace:
            return False
        if state.reject:
            if state.reject_after_write:
                state.merged = data.MergeFace
            state.reject = False
            return False
        state.merged = data.MergeFace; state.rolled_back = False
        return True
    capture.flat.ModifyDefinition = modify
    # Real flat-pattern APIs can return only the centreline, and UiBend's faces
    # need not own the newly exposed flat band. Its measured face still exists.
    original_line = capture.bend.definition.FlatPatternSketchSegments2[0]
    start, end = original_line.GetStartPoint2(), original_line.GetEndPoint2()
    width = load_demo('L120').part.bends[0].width/1000
    centre = NS(GetType=original_line.GetType, GetSketch=original_line.GetSketch,
                GetStartPoint2=lambda: NS(X=start.X, Y=start.Y+width/2, Z=0.),
                GetEndPoint2=lambda: NS(X=end.X, Y=end.Y+width/2, Z=0.))
    capture.bend.definition.FlatPatternSketchSegments2 = (centre,)
    return state


def test_merged_flat_pattern_reads_actual_band_and_restores_setting(capture):
    state = _merged_flat(capture)
    before = capture.path.read_bytes()
    part = sw.read_active(session_factory=capture.session)
    assert part.bends[0].width == pytest.approx(load_demo('L120').part.bends[0].width)
    assert state.edits == [False, True] and state.merged is True
    assert not state.rolled_back and state.access == 2 and state.released == 0
    assert capture.flat.suppressed and capture.manager.suspended == 0
    assert capture.path.read_bytes() == before


def test_already_split_faces_need_no_definition_edit(capture):
    state = _merged_flat(capture, False)
    part = sw.read_active(session_factory=capture.session)
    assert len(part.bends) == 1 and state.edits == [] and state.merged is False
    assert state.access == 0 and capture.flat.suppressed


@pytest.mark.parametrize('failure', ['geometry', 'cancel'])
def test_merge_faces_restored_after_capture_error_or_cancel(capture, failure):
    state = _merged_flat(capture); stop = threading.Event()
    original = capture.body.GetFaces
    def faces():
        if not capture.flat.suppressed and not state.merged:
            if failure == 'cancel':
                stop.set(); raise Cancelled()
            raise RuntimeError('flat geometry unavailable')
        return original()
    capture.body.GetFaces = faces
    with pytest.raises(Cancelled if failure == 'cancel' else RuntimeError):
        sw.read_active(stop, session_factory=capture.session)
    assert state.merged and state.edits == [False, True] and not state.rolled_back
    assert capture.flat.suppressed and capture.manager.suspended == 0


@pytest.mark.parametrize('changed', [False, True])
def test_failed_merge_edit_releases_rollback_and_repairs_partial_change(capture, changed):
    state = _merged_flat(capture); state.reject = True; state.reject_after_write = changed
    with pytest.raises(ApiError, match='kabul edilmedi'):
        sw.read_active(session_factory=capture.session)
    assert state.merged and not state.rolled_back and state.released == 1
    assert capture.flat.suppressed and capture.manager.suspended == 0
    assert state.edits == ([False, True] if changed else [False])


def test_merge_restore_failure_is_explicit_even_if_suppression_restores(capture):
    state = _merged_flat(capture); state.reject_restore = True
    with pytest.raises(RestoreError, match='yüz birleştirme'):
        sw.read_active(session_factory=capture.session)
    assert capture.flat.suppressed and capture.manager.suspended == 0
    assert not state.rolled_back and state.released == 1


def test_unowned_band_needs_unique_real_geometry_and_centreline_overlap():
    from shapely.geometry import box
    row = dict(id='measured', label='Bend1', turn=60, radius=2)
    width = 3*radians(60); line = [((-40,width/2),(40,width/2))]
    zone = box(-40,0,40,width)
    band = sw._band(row,line,[],2,candidates=[box(-40,-40,40,0),zone,box(-40,width,40,40)])
    assert band['width'] == pytest.approx(width)
    with pytest.raises(ApiError, match='birden fazla'):
        sw._band(row,line,[],2,candidates=[zone,box(-40,.1,40,width+.1)])
    with pytest.raises(ApiError, match='ölçülmüş'):
        sw._band(row,line,[],2,candidates=[box(100,0,180,width)])


def test_merge_face_property_write_uses_raw_dispatch_without_type_info():
    class Dispatch:
        def GetIDsOfNames(self, locale, name):
            assert locale == 0 and name == 'MergeFace'; return 77
        def Invoke(self, member, locale, flags, want_result, value):
            assert (member,locale,flags,want_result,value) == (77,0,4,False,False)
    sw._put_merge_faces(Dispatch(), False)


def test_base_flange_uibend_reads_centreline_with_merged_flat_faces(capture):
    reader = _base_flange_part(capture, [_bend_cylinder('inner', 2), _bend_cylinder('outer', 4)])
    state = _merged_flat(capture)
    part = sw.read_active(session_factory=reader)
    assert part.bends[0].title == 'Bend1' and part.bends[0].width == pytest.approx(load_demo('L120').part.bends[0].width)
    assert state.merged and state.edits == [False, True] and capture.flat.suppressed


def test_bend_features_are_resolved_again_after_the_flat_rebuild(capture):
    state = _merged_flat(capture)
    original = capture.bend
    session = capture.session
    class Reader(session):
        def features(self, model, stop):
            fresh = Feature(original.Name, original.definition)
            fresh.ref = original.ref
            revision = len(state.edits)
            def definition():
                if revision != len(state.edits):
                    raise RuntimeError('stale feature proxy after rebuild')
                return original.definition
            fresh.GetDefinition = definition
            yield fresh, 'OneBend'; yield capture.flat, 'FlatPattern'
    part = sw.read_active(session_factory=Reader)
    assert part.bends[0].width == pytest.approx(load_demo('L120').part.bends[0].width)
    assert state.merged and capture.flat.suppressed


def test_unowned_measured_band_preserves_a_hole_crossing_the_centreline():
    from shapely.geometry import Point, box
    row = dict(id='B1', turn=90, radius=2)
    width = 3*radians(90)
    zone = box(0,0,80,width).difference(Point(40,width/2).buffer(1))
    band = sw._band(row,[((0,width/2),(80,width/2))],[],2,candidates=[zone])
    assert band['width'] == pytest.approx(width)
    p = load_demo('L120').part
    outline = Region.from_polygon(box(0,-30,80,width+30).difference(Point(40,width/2).buffer(1)))
    part = sw.partition(p.name,p.configuration,p.material,2,outline,[dict(band,direction=1)],(10,-20),'root','source')
    assert len(part.bends[0].region.holes) == 1
