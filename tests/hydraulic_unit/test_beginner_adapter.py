"""Kolay giriş dönüştürücülerinin GUI'siz referansları."""
from dataclasses import replace
import pytest
from modules.hydraulic_unit.beginner import force_to_newtons,basic_cycle,simple_supported
from modules.hydraulic_unit.core.models import Project,Cylinder
from modules.hydraulic_unit.core.service import calculate_project


def test_force_conversion_is_standard_gravity_force_not_mass():
    assert force_to_newtons(1,'tonf')==pytest.approx(9806.65)
    assert force_to_newtons(2,'kN')==2000.
    with pytest.raises(ValueError):force_to_newtons(-1,'tonf')


def test_template_preserves_advanced_configuration_and_is_a_closed_cycle():
    p=replace(Project(),cylinders=(replace(Cylinder(),initial_position=.1),))
    candidate=basic_cycle(p)
    assert candidate.pump==p.pump and candidate.thermal==p.thermal and candidate.oil==p.oil
    assert candidate.phases[0].stroke==pytest.approx(.2)
    assert calculate_project(candidate).cycle['repeatable_geometry']
    assert not simple_supported(replace(p,cylinders=(Cylinder(),Cylinder(id='C2'))))
