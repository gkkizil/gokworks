"""High-precision pVⁿ reference; close operating pressures must not cancel."""

import math
from decimal import Decimal, localcontext

import pytest

from modules.hydraulic_unit.core.accumulator import accumulator_result
from modules.hydraulic_unit.core.models import Accumulator


@pytest.mark.parametrize('exponent', (1., 1.1, 1.4))
@pytest.mark.parametrize('rise_pa', (1e5, 1., .001, math.ulp(1e7)))
def test_delivery_matches_70_digit_gas_state_reference(exponent, rise_pa):
    a = Accumulator(enabled=True, minimum_pressure=1e7,
                    maximum_pressure=1e7+rise_pa, precharge_pressure=8e6,
                    delivery_volume=.001, exponent=exponent)
    with localcontext() as context:
        context.prec = 70
        exact = Decimal.from_float
        # Start with a one-m³ gas volume at precharge. Independently solve the
        # two pVⁿ=C states, then scale their delivered-volume difference.
        constant = exact(a.precharge_pressure)+exact(a.atmospheric_pressure)
        minimum = exact(a.minimum_pressure)+exact(a.atmospheric_pressure)
        maximum = exact(a.maximum_pressure)+exact(a.atmospheric_pressure)
        inverse_n = Decimal(1)/exact(exponent)
        volume_at_minimum = constant**inverse_n/minimum**inverse_n
        volume_at_maximum = constant**inverse_n/maximum**inverse_n
        expected = exact(a.delivery_volume)/(volume_at_minimum-volume_at_maximum)
    result = accumulator_result(a)
    assert result['required_volume'] == pytest.approx(float(expected), rel=2e-14)
    assert result['minimum_absolute'] < result['maximum_absolute']
