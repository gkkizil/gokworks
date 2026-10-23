"""Independent engineering examples, with literal expected values and units."""

from decimal import Decimal
from math import sqrt

import pytest

from modules.bolt_torque.rules import calculate as torque
from modules.weight.rules import calculate as weight
from modules.k_factor.rules import bend_allowance, bend_deduction
from modules.iso_fits.rules import limits, mm
from modules.nesting.accounting import mass
from modules.tolerance_stack.models import Project, manual_dimension, Term
from modules.tolerance_stack.calculator import calculate


def test_independent_m10_88_torque_example_and_surface_ratio():
    # M10x1.5 As≈58 mm², ReL=640 MPa, 70% =>25.984 kN, T≈51.968 Nm.
    dry = torque(metric='M10'); oily = torque(metric='M10', condition='Hafif yağlı')
    assert dry.tensile_area_mm2 == pytest.approx(58, abs=.02)
    assert dry.preload_kn == pytest.approx(25.984, abs=.01)
    assert dry.torque_nm == pytest.approx(51.968, abs=.02)
    assert oily.torque_nm == pytest.approx(dry.torque_nm*.75)


@pytest.mark.parametrize('unit,dimensions', [('mm', (100, 2, 1000)), ('cm', (10, .2, 100)), ('m', (.1, .002, 1))])
def test_plate_weight_unit_invariance_and_nesting_mass_agree(unit, dimensions):
    b, t, length = dimensions
    result = weight(kind='Sac levha', unit=unit, b=b, t=t, length=length)
    assert result.mass_kg == pytest.approx(1.57)
    assert mass(100*1000, 2, 7850) == pytest.approx(1.57)


def test_iso50_h7_h6_and_bend_example_from_independent_limits():
    hole = limits('50','H7','hole'); shaft = limits('50','h6','shaft')
    assert (mm(hole.lower_nm),mm(hole.upper_nm)) == (Decimal('0'),Decimal('.025'))
    assert (mm(shaft.lower_nm),mm(shaft.upper_nm)) == (Decimal('-.016'),Decimal('0'))
    assert bend_allowance(2,2,.4) == pytest.approx(4.39822971502571, abs=1e-12)
    assert bend_deduction(2,2,.4) == pytest.approx(3.60177028497429, abs=1e-12)


def test_signed_three_term_limits_and_untruncated_rss_are_distinct():
    dimensions = [manual_dimension('A',50,-.1,.1),manual_dimension('B',20,-.05,.05),
                  manual_dimension('C',29.8,-.03,.03)]
    p = Project(dimensions=dimensions, method='rss', truncate_normal=False, end='P3')
    p.terms = [Term(d.id, 1 if i==0 else -1, f'P{i}', f'P{i+1}', datum='A') for i,d in enumerate(dimensions)]
    p.confirm(); r = calculate(p)
    assert (r.nominal,r.minimum,r.maximum) == (Decimal('.2'),Decimal('.02'),Decimal('.38'))
    # Independent: (three-sigma) RSS half-band sqrt(0.01+0.0025+0.0009).
    assert r.rss_minimum == pytest.approx(.2-sqrt(.0134))
    assert r.rss_maximum == pytest.approx(.2+sqrt(.0134))
