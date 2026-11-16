"""Published manufacturer examples, independent of the application's own tables."""

import pytest

from modules.hydraulic_unit.core.pump_motor import shaft_power
from modules.hydraulic_unit.core.units import convert
from modules.iso_fits.rules import limits

# SKF Cooper 2022, table 4 (shaft deviations, µm), within our 1–400 mm scope.
# https://www.cooperbearings.com/ebrochure/UK_2022/14/
SKF_SHAFT_DEVIATIONS = (
    (50, -16, -25, -62),
    (80, -19, -30, -74),
    (120, -22, -35, -87),
    (180, -25, -40, -100),
    (250, -29, -46, -115),
    (315, -32, -52, -130),
    (400, -36, -57, -140),
)


@pytest.mark.parametrize('diameter,h6,h7,h9', SKF_SHAFT_DEVIATIONS)
@pytest.mark.parametrize('grade', (6, 7, 9))
def test_shaft_limits_match_skf_published_micrometres(diameter, h6, h7, h9, grade):
    expected = {6: h6, 7: h7, 9: h9}[grade]
    band = limits(str(diameter), f'h{grade}', 'shaft')
    assert band.lower_nm == expected*1000
    assert band.upper_nm == 0


def test_parker_published_hydraulic_power_example_in_us_units():
    # Parker MSG10-1700/US, Basic Hydraulic Formulas, p. 41: dissipating 300 psi
    # at 10 US gpm generates approximately 1.75 hp / 1305 W of heat.
    # Manufacturer PDF URL is recorded in docs/verification-2026-11-16/formula-audit.md.
    pressure = convert(300., 'psi', 'Pa')
    flow = convert(10., 'gpm', 'm3/s')
    assert shaft_power(pressure, flow, 1.) == pytest.approx(1305., abs=1.)
