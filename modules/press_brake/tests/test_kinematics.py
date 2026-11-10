from dataclasses import replace
from math import radians
import numpy as np
import pytest
from modules.press_brake.demo import load_demo
from modules.press_brake.kinematics import fold_transform, poses, step_angles, point


def test_l_120_inside_angle_is_60_turn_and_signed_thickness_normal_is_preserved():
    plan = load_demo('L120'); b = plan.part.bends[0]
    matrix = fold_transform(b, 2, radians(b.turn))
    assert b.inside_angle == 120 and b.turn == 60
    normal = matrix[:3, :3]@np.array([0, 0, 2.])
    assert np.linalg.norm(normal) == pytest.approx(2)
    assert normal[2] == pytest.approx(1)
    assert point(matrix, (0, 65+b.width, 0))[2] > 0
    inverted = fold_transform(b, 2, -radians(60))
    assert point(inverted, (0, 65+b.width, 0))[2] < 0


def test_u_orders_have_different_intermediate_and_identical_final_nominal_geometry():
    a = load_demo('U'); b = a.changed(steps=a.steps[::-1])
    first_a = poses(a.part, step_angles(a, 0, 1)); first_b = poses(b.part, step_angles(b, 0, 1))
    assert not np.allclose(first_a['F1'], first_b['F1'])
    final_a = poses(a.part, step_angles(a, 1, 1)); final_b = poses(b.part, step_angles(b, 1, 1))
    for id in final_a:
        np.testing.assert_allclose(final_a[id], final_b[id])


def test_child_flange_and_its_bend_follow_ancestor_rotation():
    plan = load_demo('U')
    # Pure tree test: second hinge is downstream of first rather than sibling.
    child = replace(plan.part.bends[1], parent='F1')
    part = replace(plan.part, bends=(plan.part.bends[0], child))
    first = poses(part, {'B01': radians(40)})
    np.testing.assert_allclose(first['F2'], first['F1'])
    both = poses(part, {'B01': radians(40), 'B02': radians(20)})
    np.testing.assert_allclose(both['F2'], first['F1']@fold_transform(child, 2, radians(20)))


@pytest.mark.parametrize('field,value', [('thickness', 0), ('thickness', float('nan')), ('root', 'missing')])
def test_invalid_part_is_rejected(field, value):
    with pytest.raises(ValueError):
        replace(load_demo().part, **{field: value}).validate()


def test_closed_graph_duplicate_and_missing_bends_are_rejected():
    plan = load_demo('U')
    with pytest.raises(ValueError):
        replace(plan.part, bends=plan.part.bends+(plan.part.bends[0],)).validate()
    with pytest.raises(ValueError):
        replace(plan, steps=plan.steps[:1]).validate()


def test_nonfinite_angle_and_developed_width_do_not_get_defaults():
    p = load_demo('L120').part
    for bend in (replace(p.bends[0], inside_angle=float('nan')), replace(p.bends[0], width=500)):
        with pytest.raises(ValueError):
            replace(p, bends=(bend,)).validate()
