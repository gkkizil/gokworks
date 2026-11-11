"""Forward physical bounds protect the inverse, including round-off at K=0/1."""
import math
import random

import pytest

from modules.k_factor.rules import bend_allowance,k_from_bend_allowance


@pytest.mark.parametrize('k',[0.,1.])
def test_valid_boundary_allowances_roundtrip_across_manufacturing_scales(k):
    rng=random.Random(10)
    for _ in range(300):
        thickness=10**rng.uniform(-3,2);radius=10**rng.uniform(-3,2)
        angle=rng.uniform(.1,179.9)
        ba=bend_allowance(thickness,radius,k,angle)
        recovered=k_from_bend_allowance(thickness,radius,ba,angle)
        assert recovered==pytest.approx(k,abs=2e-10)


def test_a_measurement_outside_the_forward_range_is_not_silently_clamped():
    thickness,radius,angle=.7194704700438556,.13945859110176612,104.04081594397778
    lower=bend_allowance(thickness,radius,0.,angle)
    upper=bend_allowance(thickness,radius,1.,angle)
    for ba in (math.nextafter(lower,0.),math.nextafter(upper,math.inf)):
        with pytest.raises(ValueError,match='dışında'):
            k_from_bend_allowance(thickness,radius,ba,angle)


def test_an_unresolvable_neutral_axis_cannot_be_reported_as_a_measured_k():
    with pytest.raises(ValueError,match='hassasiyeti'):
        k_from_bend_allowance(1e-12,1e12,bend_allowance(1e-12,1e12,.5))
