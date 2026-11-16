from dataclasses import replace
import math

import pytest

from modules.automatic_drawing.models import (Box, FaceEvidence, ModelInfo, Node, Options, Source,
                                             to_m, to_mm, degrees)
from modules.automatic_drawing.rules import (DimensionCandidate, classify, plan_views,
    quantities, score_views, unique_dimensions, unique_sources)
from modules.automatic_drawing.layout import arrange, plan_sheet, plan_sheets, place_texts, text_box
from modules.automatic_drawing.validation import validate_annotations, validate_views


def plate(size=(100., 50., 10.)):
    info = ModelInfo(Source('C:/parts/Plate.SLDPRT', 'Default'), 'part', 'Plate', size, body_count=1)
    info.faces = [FaceEvidence('plane', 5000., (0, 0, sign)) for sign in (-1, 1)]
    info.feature_types = {'Boss': 1}
    info.classification, info.classification_reason = classify(info)
    return info


@pytest.mark.parametrize('value', (0., .001, .1, 1., 25.4, -5.))
def test_si_boundary_round_trip(value):
    assert to_mm(to_m(value)) == pytest.approx(value)
    assert degrees(math.pi/2) == pytest.approx(90.)


@pytest.mark.parametrize('value', (float('nan'), float('inf'), -float('inf'), True))
def test_invalid_units_and_layout_numbers_rejected(value):
    with pytest.raises(ValueError): to_m(value)
    with pytest.raises(ValueError): Box(0, 0, value, 5)


def test_plate_uses_face_and_feature_evidence_not_just_bbox():
    info = plate()
    assert info.classification == 'plate'
    assert score_views(info)[0].name == 'front'
    info.faces.clear()
    assert classify(info)[0] == 'general'
    info.sheet_body_count = 1
    assert classify(info)[0] != 'sheet'
    info.feature_types['SheetMetal'] = 1
    assert classify(info)[0] == 'sheet'


def test_turning_feature_and_axis_choose_longitudinal_main_view():
    info = ModelInfo(Source('shaft.sldprt', 'A'), 'part', 'Shaft', (200., 30., 30.),
        body_count=1, feature_types={'Revolution': 1},
        faces=[FaceEvidence('cylinder', 2000., (1, 0, 0), 15.)])
    info.classification, _ = classify(info)
    assert info.classification == 'shaft'
    assert score_views(info)[0].name in ('front', 'back', 'top', 'bottom')


@pytest.mark.parametrize('projection', ('first', 'third'))
@pytest.mark.parametrize('size', ((100., 50., 10.), (150., 100., 8.), (2000., 300., 200.)))
def test_paper_fit_has_real_margins_title_clearance_and_projected_alignment(projection, size):
    options = Options(projection=projection)
    plan = plan_sheet(plan_views(plate(size), options), options)
    boxes = {v.role: Box(v.center[0]-v.footprint[0]*k/2, v.center[1]-v.footprint[1]*k/2,
                        v.footprint[0]*k, v.footprint[1]*k)
             for v in plan.views for k in (plan.view_scales.get(v.role, plan.scale),)}
    assert all(plan.usable.contains(box) for box in boxes.values())
    assert all(not a.overlaps(b) for i, a in enumerate(boxes.values()) for b in list(boxes.values())[i+1:])
    main, top, side = (next(v for v in plan.views if v.role == r) for r in ('main', 'top', 'side'))
    assert top.center[0] == main.center[0]
    assert side.center[1] == main.center[1]
    assert (top.center[1] < main.center[1]) is (projection == 'first')
    assert (side.center[0] < main.center[0]) is (projection == 'first')


def test_auto_paper_and_custom_scale_do_not_silently_replace_user_choices():
    info = plate((600., 400., 20.))
    options = Options(paper='auto', manual_scale=1.)
    plans = plan_sheets(plan_views(info, options), options)
    # The user's 1:1 holds for every orthographic view; only the isometric may take its own
    # smaller scale (at most 5x) or its own sheet.
    assert all(plan.scale == 1. for plan in plans)
    assert all(plan.paper in ('A1', 'A0') for plan in plans)
    assert all(1/5 <= scale < 1. for plan in plans for scale in plan.view_scales.values())
    with pytest.raises(ValueError, match='sığmıyor'):
        plan_sheet(plan_views(info, options), replace(options, paper='A4'))
    custom = replace(options, paper='custom', custom_width_mm=2000., custom_height_mm=1500.)
    assert plan_sheet(plan_views(info, custom), custom).width_mm == 2000.


def test_measured_outline_replaces_bbox_estimate():
    options = Options()
    views = plan_views(plate(), options)
    impossible = {v.role: Box(0, 0, 1000., 1000.) for v in views}
    assert arrange(views, 1., Box(10, 50, 400, 237), options, measured=impossible) is None


def test_equal_hole_diameters_are_not_duplicate_dimensions():
    one = DimensionCandidate('p.sldprt', 'A', 'D1@Hole1', 'diameter', 10., ('hole1',))
    two = DimensionCandidate('p.sldprt', 'A', 'D1@Hole2', 'diameter', 10., ('hole2',))
    different_config = replace(one, configuration='B')
    unknown = replace(one, name='')
    assert unique_dimensions([one, two, one, different_config, unknown, unknown]) == [
        one, two, different_config, unknown, unknown]


def test_bom_counts_instances_but_generation_deduplicates_only_file_and_case_sensitive_config():
    screw = Source('C:/parts/Screw.SLDPRT', 'M8')
    children = [Node(f'Screw-{i}', screw) for i in range(12)]
    root = Node('Assembly', Source('C:/asm.sldasm', 'A'), 'assembly', children=children)
    assert quantities(root)[screw.key] == 12
    assert unique_sources(root.children) == (screw,)
    root.children += [Node('Suppressed', screw, state='suppressed'),
                      Node('Excluded', screw, excluded_bom=True),
                      Node('Variant', replace(screw, configuration='m8'))]
    assert quantities(root)[screw.key] == 12
    assert len(unique_sources(root.children)) == 2
    assert screw.key == Source(r'c:\PARTS\screw.sldprt', 'M8').key
    assert screw.key != Source(screw.path, 'm8').key


def test_two_level_assemblies_keep_occurrence_quantities():
    part = Source('C:/p.sldprt', 'Default')
    sub = Source('C:/sub.sldasm', 'A')
    children = [Node('sub1', sub, 'assembly', children=[Node('part1', part), Node('part2', part)]),
                Node('sub2', sub, 'assembly', children=[Node('part1', part), Node('part2', part)])]
    root = Node('top', Source('C:/top.sldasm', 'A'), 'assembly', children=children)
    assert quantities(root)[part.key] == 4
    assert quantities(root, 'top')[sub.key] == 2
    assert len(unique_sources(children, 'all')) == 2
    assert len(unique_sources(children, 'parts')) == 1


def test_rotated_text_and_greedy_placement_are_within_paper_and_keep_dimensions():
    vertical = text_box(100., 100., 20., 3., math.pi/2)
    assert vertical.width == pytest.approx(3.)
    assert vertical.height == pytest.approx(20.)
    area, view = Box(10, 50, 400, 237), Box(100, 100, 80, 40)
    records = [('d1', 'main', Box(120, 110, 20, 4)), ('d2', 'main', Box(120, 110, 20, 4))]
    moves, unresolved = place_texts(records, {'main': view}, area)
    assert not unresolved and set(moves) == {'d1', 'd2'}
    boxes = [box.shifted(*moves[key]) for key, owner, box in records]
    assert all(area.contains(box) and not box.overlaps(view) for box in boxes)
    assert not boxes[0].overlaps(boxes[1])


def test_validator_catches_wrong_model_configuration_and_broken_projection():
    source = Source('C:/p.sldprt', 'Default')
    sheet = dict(name='S1', width_mm=420., height_mm=297., expected=['main', 'side'],
                 projection='first', usable=Box(10, 50, 400, 237))
    actual = [dict(role='main', name='Front', outline=Box(100, 100, 50, 40),
                   path=source.path, configuration='Default'),
              dict(role='side', name='Side', outline=Box(50, 100, 20, 40),
                   path='C:/other.sldprt', configuration='Other', parent='', main_name='Front')]
    assert {f.code for f in validate_views(sheet, actual, source, projection='first')} == {
        'source_link', 'configuration', 'projection_link'}
    actual[1]['outline'] = Box(105, 105, 10, 10)
    assert 'view_collision' in {f.code for f in validate_views(sheet, actual, source)}


def test_missing_bounds_and_dangling_or_zero_dimensions_cannot_pass_silently():
    records = [dict(name='D1', dangling=True, value=0., box=None, model_identity='same'),
               dict(name='D2', dangling=False, value=10., box=Box(0, 0, 20, 5), model_identity='same')]
    codes = {f.code for f in validate_annotations(records, {}, Box(10, 50, 400, 237))}
    assert {'dangling_dimension', 'zero_dimension', 'dimension_bounds', 'dimension_outside',
            'duplicate_dimension'} <= codes



def info_of(size, kind='part'):
    from modules.automatic_drawing.models import ModelInfo, Source
    return ModelInfo(Source('C:/x.SLDPRT', 'Default'), kind, 'x', size)


def test_isometric_bound_is_the_projected_bounding_box_not_the_diagonal_square():
    import math
    iso = next(v for v in plan_views(info_of((420., 30., 30.)), Options()) if v.role == 'isometric')
    assert iso.footprint == pytest.approx((450/math.sqrt(2), 510/math.sqrt(6)))
    # Any point of the box projects inside it (view along (1, 1, 1), Y up).
    u = lambda x, y, z: (x-z)/math.sqrt(2); v = lambda x, y, z: (-x+2*y-z)/math.sqrt(6)
    corners = [(x, y, z) for x in (0, 420) for y in (0, 30) for z in (0, 30)]
    assert max(u(*c) for c in corners)-min(u(*c) for c in corners) == pytest.approx(iso.footprint[0])
    assert max(v(*c) for c in corners)-min(v(*c) for c in corners) == pytest.approx(iso.footprint[1])


def test_the_isometric_no_longer_shrinks_the_orthographic_views():
    options = Options()
    plan = plan_sheet(plan_views(info_of((420., 30., 30.)), options), options)
    assert plan.scale == .5 and plan.view_scales == {'isometric': .2}     # was 1:5 for every view
    alone = plan_sheet(plan_views(info_of((420., 30., 30.)), replace(options, isometric=False)), options)
    assert alone.scale == plan.scale                                       # same as without an isometric


def test_automatic_paper_picks_a_sheet_the_main_view_fills_and_never_enlarges_onto_a_big_sheet():
    from modules.automatic_drawing.layout import FILL, fill
    auto = Options(paper='auto')
    plate_plan = plan_sheet(plan_views(info_of((600., 400., 20.)), auto), auto)
    assert fill(plate_plan) >= FILL and plate_plan.paper == 'A2' and plate_plan.scale == .5
    pin = plan_sheet(plan_views(info_of((12., 12., 30.)), auto), auto)
    assert pin.paper in ('A4', 'A3') and pin.scale >= 1.
