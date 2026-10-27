"""Independent shoulder edges must coexist without disabling genuine limits."""

import pytest

from modules.shaft_generator.models import Project, Stage, Groove, Keyway, Chamfer, Fillet
from modules.shaft_generator.validation import validate
from modules.shaft_generator.geometry import treated_profile, check_profile, operation_plan


def treatment(kind, stage, edge, size=1):
    return kind(stage.id, edge=edge, **({'distance': size} if kind is Chamfer else {'radius': size}))


def test_reported_six_operations_keep_their_edges_and_reach_the_native_plan():
    p = Project(stages=[Stage(30, 80), Stage(45, 65), Stage(35, 50), Stage(25, 35)])
    a, b = p.stages[:2]
    p.operations = [Groove(a.id), Chamfer(a.id, edge='left'), Chamfer(a.id, edge='right'),
                    Keyway(b.id, offset=10, length=25, width=14, depth=5.5),
                    Chamfer(b.id, edge='right'), Chamfer(b.id, edge='left')]
    snapshot = p.to_dict()
    assert not validate(p)
    check_profile(treated_profile(p))
    plan = operation_plan(p)
    assert len(plan) == 10
    assert [row['kind'] for row in plan[4:]] == ['chamfer']*4+['groove', 'keyway']
    assert {row['operation_id'] for row in plan[4:]} == {op.id for op in p.operations}
    assert p.to_dict() == snapshot


@pytest.mark.parametrize('diameters', [(30, 45), (45, 30)])
@pytest.mark.parametrize('inner_kind', [Chamfer, Fillet])
@pytest.mark.parametrize('outer_kind', [Chamfer, Fillet])
@pytest.mark.parametrize('reverse', [False, True])
def test_both_radial_edges_of_one_shoulder_can_be_treated(diameters, inner_kind, outer_kind, reverse):
    p = Project(stages=[Stage(d, 40) for d in diameters])
    a, b = p.stages
    kinds = (inner_kind, outer_kind) if diameters[0] < diameters[1] else (outer_kind, inner_kind)
    p.operations = [treatment(kinds[0], a, 'right'), treatment(kinds[1], b, 'left')]
    if reverse:
        p.operations.reverse()
    assert not validate(p)
    outline = treated_profile(p)
    check_profile(outline)
    # Both original sharp corners have actually been replaced in the preview.
    assert (40, diameters[0]/2) not in outline and (40, diameters[1]/2) not in outline


@pytest.mark.parametrize('kind', [Chamfer, Fillet])
def test_treatment_on_large_diameter_does_not_block_small_diameter_groove(kind):
    p = Project()
    a, b = p.stages[:2]
    p.operations = [treatment(kind, b, 'left'), Groove(a.id, offset=38, width=2)]
    assert not validate(p)


@pytest.mark.parametrize('diameters', [(30, 34), (34, 30)])
@pytest.mark.parametrize('kind', [Chamfer, Fillet])
def test_shared_shoulder_checks_combined_radial_space(diameters, kind):
    p = Project(stages=[Stage(d, 40) for d in diameters])
    a, b = p.stages
    p.operations = [treatment(kind, a, 'right', 1.25), treatment(kind, b, 'left', 1.25)]
    errors = '\n'.join(validate(p))
    assert 'omuz' in errors and '2,5' in errors and '2 mm' in errors
    p.operations.reverse()
    assert 'omuz' in '\n'.join(validate(p))


@pytest.mark.parametrize('diameters', [(30, 34), (34, 30)])
@pytest.mark.parametrize('kind', [Chamfer, Fillet])
def test_two_treatments_can_meet_without_a_zero_length_preview_segment(diameters, kind):
    p = Project(stages=[Stage(d, 40) for d in diameters])
    a, b = p.stages
    p.operations = [treatment(kind, a, 'right'), treatment(kind, b, 'left')]
    assert not validate(p)
    outline = treated_profile(p)
    assert all(a != b for a, b in zip(outline, outline[1:]))
    check_profile(outline)


@pytest.mark.parametrize('kind', [Chamfer, Fillet])
def test_true_channel_and_end_treatment_interference_stays_invalid(kind):
    p = Project(stages=[Stage(30, 80)])
    s = p.stages[0]
    p.operations = [Groove(s.id, offset=0, width=2), treatment(kind, s, 'left')]
    error = '\n'.join(validate(p))
    assert 'çakış' in error
    assert 'Segman kanalı' in error and ('Pah' in error or 'Radyüs' in error)
    p.operations[0].offset = 5
    p.operations.append(Keyway(s.id, offset=15))
    p.operations.append(treatment(kind, s, 'right'))
    assert not validate(p)  # Segman + kama + two end treatments on ONE stage.
