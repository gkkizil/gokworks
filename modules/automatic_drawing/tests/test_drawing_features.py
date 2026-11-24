"""Offline rule and dispatch-boundary tests. No CAD geometry is produced here."""

from dataclasses import replace
import math
from types import SimpleNamespace

import pytest

from modules.automatic_drawing.hole_annotations import hole_groups, hole_table_tags, rim_match, wizard_text
from modules.automatic_drawing.layout import crosses_box, plan_drawing, place_texts
from modules.automatic_drawing.models import Box, DerivedView, Detail, Hole, ModelInfo, Options, Source, ViewPlan
from modules.automatic_drawing.part_features import apply_wizard_data, cylinder_hole, wizard_definition
from modules.automatic_drawing.rules import derived_views, plan_views
from modules.automatic_drawing.validation import validate_annotation_obstacles, validate_views

from .test_native_boundary import RawDispatch, case


def model(**evidence):
    return ModelInfo(Source('C:/fixture.SLDPRT', 'Default'), 'part', 'fixture', (120., 80., 35.), **evidence)


def test_wizard_read_uses_properties_allowed_for_the_native_type_only():
    fake = RawDispatch('IWizardHoleFeatureData2', properties={
        'Type': 25, 'EndCondition': 1, 'ThruHoleDiameter': .0085, 'ThruHoleDepth': .01,
        'CounterBoreDiameter': .05, 'FastenerSize': 'M99', 'ThreadDiameter': .1,
    })
    feature = RawDispatch('IFeature', methods={'GetDefinition': lambda: fake})
    session = SimpleNamespace(named_interface=lambda obj, iid: obj, constants={'swEndCondThroughAll': 1})
    assert wizard_definition(session, feature) == ('25', 'through', (
        ('ThruHoleDiameter', 8.5), ('ThruHoleDepth', 10.)))
    assert not {'CounterBoreDiameter', 'ThreadDiameter', 'FastenerSize'} & {name for name, _, _ in fake.calls}


def test_wizard_keeps_actual_thread_designation_and_same_spec_is_grouped():
    axis = (0., 0., 1.)
    first = Hole(axis, ((0., 0., 0.), (0., 0., 12.)), 6.8, 'HoleWzd1')
    second = replace(first, rims_mm=((25., 0., 0.), (25., 0., 12.)))
    bore = replace(first, diameter_mm=10., rims_mm=((0., 0., -3.), (0., 0., 0.)))
    properties = (('ThruTapDrillDiameter', 6.8), ('ThreadDiameter', 8.), ('FastenerSize', 'M8×1,25'))
    observed = apply_wizard_data([first, second, bore], {'HoleWzd1': ('33', 'through', properties)})
    assert len(observed) == 2
    assert all(h.wizard_type == '33' for h in observed)
    through = tuple(replace(h, diameter_mm=6.8) for h in observed)
    assert len(hole_groups(through)) == 1
    assert wizard_text(through) == '2× Ø6,8 BOYDAN\nDiş M8×1,25'
    assert not rim_match(((0., 0., 0.), (1., 0., 0.), 3.4), first)
    assert rim_match(((0., 0., 0.), axis, 3.4), first)


def test_cylinder_evidence_requires_inner_face_full_circumference_and_two_rims():
    axis, radius = (0., 0., 1.), 4.

    def edge(height):
        curve = RawDispatch('ICurve', methods={'IsCircle': lambda: True},
                            properties={'CircleParams': (0., 0., height, *axis, radius/1000)})
        return RawDispatch('IEdge', methods={'GetCurve': lambda: curve})

    inward = RawDispatch('IFace2', methods={
        'FaceInSurfaceSense': lambda: True, 'GetEdges': lambda: (edge(0.), edge(.012))})
    area = 2*math.pi*radius*12.
    assert cylinder_hole(inward, area, axis, radius).diameter_mm == 8.
    assert cylinder_hole(inward, area/2, axis, radius) is None
    inward.methods['FaceInSurfaceSense'] = lambda: False
    assert cylinder_hole(inward, area, axis, radius) is None


def test_native_hole_table_readback_counts_unique_non_header_tags_only():
    tag_values = {1: 'A1', 2: 'A2', 3: 'B1'}
    hole_table = RawDispatch('IHoleTable', properties={'CombineTags': False, 'HoleTag': tag_values.get})
    generic = RawDispatch('ITableAnnotation/IHoleTableAnnotation',
                         methods={'GetHeaderStyle': lambda: 1, 'GetHeaderCount': lambda: 1},
                         properties={'HoleTable': hole_table, 'RowCount': 4})
    session = SimpleNamespace(named_interface=lambda obj, iid: obj, constants={'swTableHeader_Bottom': 2})
    assert hole_table_tags(session, generic) == ('A1', 'A2', 'B1')
    tag_values[3] = 'A2'
    assert not hole_table_tags(session, generic)


def test_blind_and_stepped_holes_select_sections_but_adjacent_parallel_holes_do_not():
    axis = (1., 0., 0.)
    first = Hole(axis, ((0., 0., 0.), (20., 0., 0.)), 12.)
    step = Hole(axis, ((20., 0., 0.), (40., 0., 0.)), 8.)
    offset = replace(step, rims_mm=((20., 5., 0.), (40., 5., 0.)))
    options = Options(main_view='front')
    info = model(holes=[first, step])
    base = plan_views(info, options)[0]
    cut, = derived_views(info, base, 1.)
    assert cut.derived.direction == axis and cut.derived.offset_axis == 1 and cut.derived.label == 'A'
    assert derived_views(model(holes=[first, offset]), base, 1.) == []
    end_on = Hole((0., 0., 1.), ((10., 11., 0.), (10., 11., 5.)), 4., end_condition='blind')
    cut, = derived_views(model(holes=[end_on]), base, 1.)
    assert cut.derived.point_mm == end_on.rims_mm[0] and cut.derived.direction == axis


def test_detail_uses_smallest_readable_magnification_and_only_when_under_three_mm():
    info = model(details=[Detail('Radyüs', (7., 8., 0.), .7, 2)])
    base = plan_views(info, Options(main_view='front'))[0]
    detail, = derived_views(info, base, 1.)
    assert detail.role == 'detail' and detail.derived.scale == 5.
    assert derived_views(info, base, 5.) == []
    assert derived_views(model(details=[Detail('Pah', (0., 0., 0.), .1, 2)]), base, 1.) == []


@pytest.mark.parametrize('projection,sign', [('first', -1), ('third', 1)])
def test_a4_spills_section_and_preserves_parent_and_projection(projection, sign):
    info = model(holes=[Hole((0., 1., 0.), ((0., 0., 0.), (0., 40., 0.)), 10., end_condition='blind')])
    options = Options(main_view='front', paper='A4', manual_scale=1., projection=projection,
                      top=False, side=True, isometric=False, annotation_padding_mm=22., gap_mm=14.)
    pages, deferred = plan_drawing(info, options)
    assert len(pages) == 2 and not deferred
    parent, cut = pages[1].views
    assert cut.role == 'section' and parent.role == cut.parent
    assert cut.center[1] == parent.center[1] and sign*(cut.center[0]-parent.center[0]) > 0


def test_annotation_lanes_avoid_text_and_leaders_and_detect_saved_collisions():
    area = Box(0., 0., 150., 100.)
    outline = Box(30., 30., 70., 35.)
    original = Box(48., 61., 22., 5.)
    leader = ((15., 78.), (130., 78.))
    note = Box(42., 68., 36., 8.)
    moves, unresolved = place_texts([('d', 'main', original)], {'main': outline}, area,
                                    obstacle_boxes=[note], obstacle_leaders=[leader])
    assert not unresolved
    placed = original.shifted(*moves['d'])
    assert not placed.overlaps(note) and not crosses_box(*leader, placed)
    dimensions = [dict(name='Ø', box=Box(55., 74., 25., 8.), leaders=[])]
    extras = [dict(name='Balon', kind='balloon', annotation_kind='balloon', box=note, leaders=[leader])]
    findings = validate_annotation_obstacles(dimensions, extras, {'main': outline}, area, 'Pafta')
    assert {f.code for f in findings} == {'annotation_collision', 'annotation_leader_collision'}


@pytest.mark.parametrize('role,method', [
    ('section', 'CreateSectionViewAt5'), ('detail', 'CreateDetailViewAt4')])
def test_derived_view_native_calls_use_selected_sketch_and_official_dispatch_signature(case, role, method):
    plan = plan_drawing(case.info, case.options)[0][0]
    case.native.create('fake.drwdot', plan)
    case.native.create_views(plan)
    parent = case.views['View1']
    x, y = parent.properties['Position']
    parent.properties.update(ScaleRatio=(1., 1.), ModelToViewTransform='view')
    parent.methods['GetSketch'] = lambda: RawDispatch('ISketch', properties={'ModelToSketchTransform': 'sketch'})
    case.native.transform_point = lambda point, transforms: (
        (point[0]+x, point[1]+y, point[2]) if transforms == 'view' else (point[0]-x, point[1]-y, 0.))
    segment = RawDispatch('ISketchSegment', methods={'Select4': lambda *args: True})
    sketch = RawDispatch('ISketchManager', methods={'CreateLine': lambda *args: segment,
                                                   'CreateCircle': lambda *args: segment},
                         properties={'AddToDB': False})
    case.model.properties['SketchManager'] = sketch
    label = 'A' if role == 'section' else 'B'
    native = RawDispatch('IDrSection', methods={'SetLabel2': lambda value: 0, 'GetLabel': lambda: label})
    derived = RawDispatch('IView', methods={'GetSection': lambda: native, 'GetDetail': lambda: native})
    case.drawing.methods[method] = lambda *args: derived
    case.constants.update(swCreateSectionView_ScaleWithModel=8, swDetViewSTANDARD=0, swDetCircleCIRCLE=0)
    planned = ViewPlan(role, '', (5., 5.), parent='main',
                       derived=DerivedView(label, (0., 0., 0.), (1., 0., 0.), 2., 5.))
    assert case.native.create_derived_view(parent, planned, .150, .100) is derived
    assert segment.calls[0][0] == 'Select4' and sketch.properties['AddToDB'] is False
    args = next(args for api, _, args in case.drawing.calls if api == method)
    if role == 'section':
        assert len(args) == 7 and args[3:5] == ('A', 8) and args[5].varianttype == 0
        assert any(name == 'SetLabel2' and values == ('A',) for name, _, values in native.calls)
    else:
        assert len(args) == 12 and args[4:7] == (5., 1., 'B')


def test_wrong_saved_detail_scale_and_parent_are_errors():
    info = model()
    view = dict(role='detail', name='Detay B', outline=Box(20., 20., 20., 20.), path=info.source.path,
                configuration='Default', label='B', expected_label='B', expected_scale=5., view_scale=2.,
                parent='Other', main_name='Main')
    sheet = dict(name='Pafta', width_mm=100., height_mm=100., expected=['detail'])
    assert {f.code for f in validate_views(sheet, [view], info.source)} == {'detail_scale', 'projection_link'}
