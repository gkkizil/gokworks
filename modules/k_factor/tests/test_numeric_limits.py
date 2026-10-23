import pytest

from modules.k_factor.rules import bend_allowance, bend_deduction, k_from_bend_allowance, ba_from_outside_dimensions


@pytest.mark.parametrize('operation', [bend_allowance, bend_deduction])
def test_large_finite_inputs_cannot_produce_infinite_or_nan_bend_lengths(operation):
    with pytest.raises(ValueError, match='sınır'):
        operation(1e308, 1e308, .4)


def test_underflowing_angle_is_rejected_before_division():
    with pytest.raises(ValueError, match='küçük'):
        k_from_bend_allowance(2, 2, 1, 5e-324)


def test_outside_measurement_overflow_is_an_input_error():
    with pytest.raises(ValueError):
        ba_from_outside_dimensions(1e308, 1e308, 1e308, 1e308, 1e308)
