"""Cylinder cross-section identities without subtracting nearly equal areas."""
from decimal import Decimal, localcontext
import math

import pytest

from modules.hydraulic_unit.core.models import Cylinder
from modules.hydraulic_unit.core.cylinder import areas,effective_area,force_at_pressure,required_pressure


@pytest.mark.parametrize('rod',[1e-6,1e-10,1e-20])
def test_regenerative_force_keeps_a_small_positive_rod_area(rod):
    c=Cylinder(rod=rod);pressure=160e5
    expected=math.pi*rod*rod/4
    assert effective_area(c,'regenerate')[0]==pytest.approx(expected,rel=1e-14,abs=0)
    force=force_at_pressure(c,pressure,'regenerate')
    assert force==pytest.approx(pressure*expected*c.efficiency,rel=1e-14,abs=0)
    assert required_pressure(c,force,'regenerate')==pytest.approx(pressure,rel=1e-14)


def test_nearly_equal_bore_and_rod_keep_the_real_annular_area():
    bore=.063;rod=math.nextafter(bore,0.)
    with localcontext() as context:
        context.prec=70
        reference=float((Decimal.from_float(bore)**2-Decimal.from_float(rod)**2)/4)*math.pi
    area=areas(Cylinder(bore=bore,rod=rod))[1]
    assert area>0 and area==pytest.approx(reference,rel=2e-15,abs=0)
