"""Independent shop-reference lengths, input rejection and measured-coupon recovery."""
from dataclasses import FrozenInstanceError
import math
import pytest
from core.unfolding.bend_profiles import BendInput, calibrate_k, develop_profile


def test_u_channel_independent_reference_and_bend_centres():
    r = develop_profile((20., 50., 20.), (BendInput(90., 2., .4), BendInput(-90., 2., .4)),
                        2., dimension_reference='outside')
    assert r.straight_lengths_mm == pytest.approx((16., 42., 16.))
    assert r.flat_length_mm == pytest.approx(82.79645943005141, abs=1e-11)
    assert tuple(v.line_at_mm for v in r.bends) == pytest.approx((18.199114857512853, 64.59734457253856))
    assert r.bends[1].angle_deg == -90.
    assert r.production_process_verified is False
    with pytest.raises(FrozenInstanceError):
        r.flat_length_mm = 1.


@pytest.mark.parametrize('reference,expected', [('outside', 76.39822971502571),
                                              ('inside', 80.39822971502571),
                                              ('tangent', 84.39822971502571)])
def test_dimension_reference_is_explicit(reference, expected):
    r = develop_profile((30., 50.), (BendInput(90., 2., .4),), 2., dimension_reference=reference)
    assert r.flat_length_mm == pytest.approx(expected, abs=1e-11)


def test_measured_coupon_recovers_k_from_fixed_independent_measurement():
    # Outside 40+60; R=3, t=1.5, 90 degrees; measured blank 96.67842872136355.
    assert calibrate_k(40., 60., 96.67842872136355, 90., 3., 1.5) == pytest.approx(.41, abs=1e-12)
    assert calibrate_k(40., 60., 96.67842872136355, -90., 3., 1.5) == pytest.approx(.41, abs=1e-12)


def test_per_bend_values_and_unit_scaling():
    bends = (BendInput(45., 3., .3), BendInput(-120., 1., .45))
    r = develop_profile((40., 80., 50.), bends, 2., dimension_reference='outside')
    expected = 170-2*5*math.tan(math.pi/8)-2*3*math.sqrt(3)+math.pi/4*3.6+2*math.pi/3*1.9
    assert r.flat_length_mm == pytest.approx(expected, abs=1e-11)
    scale = 25.4
    scaled = develop_profile(tuple(v*scale for v in (40., 80., 50.)),
        tuple(BendInput(v.angle_deg, v.inside_radius_mm*scale, v.k_factor) for v in bends),
        2*scale, dimension_reference='outside')
    assert scaled.flat_length_mm == pytest.approx(scale*r.flat_length_mm, rel=1e-12)


@pytest.mark.parametrize('lengths,bends,t,ref', [
    ((3., 50.), (BendInput(90., 2., .4),), 2., 'outside'),
    ((50., 3., 50.), (BendInput(90., 2., .4),)*2, 2., 'outside'),
    ((), (), 2., 'outside'), ((50.,), (BendInput(90., 2., .4),), 2., 'outside'),
    ((50., 50.), (BendInput(180., 2., .4),), 2., 'outside'),
    ((50., 50.), (BendInput(0., 2., .4),), 2., 'outside'),
    ((50., 50.), (BendInput(90., -1., .4),), 2., 'outside'),
    ((50., 50.), (BendInput(90., 2., 1.1),), 2., 'outside'),
    ((50., 50.), (BendInput(90., 2., True),), 2., 'outside'),
    ((50.,), (), 0., 'outside'), ((50.,), (), 2., 'mid'),
    ((float('nan'),), (), 2., 'outside'), ((True,), (), 2., 'outside'),
])
def test_invalid_or_impossible_profiles_fail_closed(lengths, bends, t, ref):
    with pytest.raises(ValueError):
        develop_profile(lengths, bends, t, dimension_reference=ref)


@pytest.mark.parametrize('flat', [0., 1., 120., float('inf'), True])
def test_invalid_coupon_is_not_clamped_to_a_plausible_k(flat):
    with pytest.raises(ValueError):
        calibrate_k(40., 60., flat, 90., 3., 1.5)


def test_unbent_profile():
    assert develop_profile((75.,), (), 2., dimension_reference='tangent').flat_length_mm == 75.
