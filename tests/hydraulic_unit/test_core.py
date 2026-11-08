"""Bağımsız sayısal referanslar, fiziksel sınırlar ve çevrim enerji testleri."""
import math
import subprocess
import sys
from dataclasses import replace

import pytest

from modules.hydraulic_unit.core.models import (Project, Cylinder, CylinderOperatingPoint, Phase,
                                               Pump, Pipe, Oil, Thermal, Accumulator)
from modules.hydraulic_unit.core.units import convert
from modules.hydraulic_unit.core.cylinder import (areas, force_at_pressure, required_pressure,
                                                bore_for_force, buckling, calculate_cylinder)
from modules.hydraulic_unit.core.pump_motor import (pump_flow, pump_torque, shaft_power,
                                                  select_motor, pump_for_type, available_flow)
from modules.hydraulic_unit.core.piping import diameter_for_flow, viscosity, pipe_result
from modules.hydraulic_unit.core.tank_thermal import thermal_result
from modules.hydraulic_unit.core.accumulator import accumulator_result
from modules.hydraulic_unit.core.service import calculate_project
from modules.hydraulic_unit.core.validation import InputError


def test_task_references():
    assert convert(pump_flow(Pump()), 'm3/s','L/min') == pytest.approx(22.04)
    power = shaft_power(160e5,22e-3/60,.85)
    assert power == pytest.approx(6901.960784313726)
    assert select_motor(power,power)['nominal'] == 7500
    assert diameter_for_flow(22e-3/60,4) == pytest.approx(.010803408024047624)
    assert force_at_pressure(Cylinder(efficiency=1),160e5) == pytest.approx(49875.924968391555)


@pytest.mark.parametrize('unit,si,factor', [('bar','Pa',1e5),('psi','Pa',6894.757293168),
    ('MPa','Pa',1e6),('mm','m',.001),('L/min','m3/s',1/60000),
    ('gpm','m3/s',.003785411784/60),('rpm','rad/s',math.pi/30),('cSt','m2/s',1e-6)])
def test_exact_unit_scaling_and_roundtrip(unit,si,factor):
    assert convert(123.45,unit,si) == pytest.approx(123.45*factor)
    assert convert(convert(123.45,unit,si),si,unit) == pytest.approx(123.45)


def test_temperature_and_incompatible_dimensions():
    assert convert(40,'°C','K') == 313.15
    assert convert(313.15,'K','°C') == 40
    with pytest.raises(InputError): convert(1,'bar','mm')


@pytest.mark.parametrize('kind', ['extend','retract','regenerate'])
def test_cylinder_reciprocity_and_volume_conservation(kind):
    c = Cylinder(); a1,a2,ratio = areas(c)
    assert ratio == pytest.approx(c.bore**2/(c.bore**2-c.rod**2))
    r = calculate_cylinder(c,CylinderOperatingPoint(kind=kind))
    area = a1 if kind == 'extend' else a2 if kind == 'retract' else math.pi*c.rod**2/4
    assert r['flow'] == pytest.approx(area*.04)
    assert required_pressure(c,r['force'],kind) == pytest.approx(160e5)
    assert r['duration'] == pytest.approx(7.5)
    if kind == 'regenerate':
        assert r['return_flow'] == 0
        assert r['nominal_bore'] is None
        assert r['nominal_regenerative_rod'] >= r['required_regenerative_rod']


@pytest.mark.parametrize('kind',['extend','retract'])
def test_inverse_bore_includes_back_pressure_and_rounds_up(kind):
    nominal,theoretical = bore_for_force(30000,160e5,rod=.036,back_pressure=10e5,kind=kind)
    c = Cylinder(bore=theoretical,rod=.036)
    assert force_at_pressure(c,160e5,kind,10e5) == pytest.approx(30000)
    assert nominal >= theoretical and force_at_pressure(replace(c,bore=nominal),160e5,kind,10e5) >= 30000


def test_outside_nominal_series_does_not_invent_a_product():
    assert bore_for_force(1e8,100e5)[0] is None
    assert select_motor(200000,200000)['nominal'] is None


@pytest.mark.parametrize('mount,k',[('fixed_free',2),('pinned_pinned',1),('fixed_pinned',.699),('fixed_fixed',.5)])
def test_euler_matches_independent_column_equation(mount,k):
    c = Cylinder(mounting=mount)
    r = buckling(c,50000)
    expected = math.pi**3 * 210e9 * .036**4 / (64*(k*.8)**2)
    assert r['critical_force'] == pytest.approx(expected)
    assert r['safety'] == pytest.approx(expected/50000)
    assert buckling(c,0)['safety'] is None


def test_pump_mechanical_power_identity_and_constant_power_curve():
    p = Pump()
    assert pump_torque(p,160e5)*p.angular_speed == pytest.approx(shaft_power(160e5,pump_flow(p),.95*.9))
    p = pump_for_type('axial_variable',control='power',power_limit=3000.)
    q = available_flow(p,200e5)
    assert q == pytest.approx(3000*.96*.93/200e5)
    assert available_flow(p,p.max_pressure+1) == 0
    assert available_flow(replace(p,control='pressure',compensator_pressure=100e5),110e5) == 0


def test_motor_checks_peak_and_rms_without_multiplying_max_pressure_by_max_flow():
    assert select_motor(11000,4000,.1)['nominal'] == 11000
    assert select_motor(7000,6900,.1)['nominal'] == 7500


def test_walther_exact_endpoints_and_monotone_interpolation():
    oil = Oil()
    assert viscosity(oil) == pytest.approx(46e-6)
    assert viscosity(replace(oil,temperature=373.15)) == pytest.approx(6.8e-6)
    assert 6.8e-6 < viscosity(replace(oil,temperature=343.15)) < 46e-6


def test_laminar_loss_matches_hagen_poiseuille_and_hose_factor():
    pipe = Pipe(diameter=.02,length=3,zeta=())
    oil = Oil(); q = 1e-4
    result = pipe_result(pipe,q,oil)
    expected = 128*870*46e-6*3*q/(math.pi*.02**4)
    assert result['regime'] == 'laminar'
    assert result['pressure_drop'] == pytest.approx(expected)
    assert pipe_result(replace(pipe,hose_laminar=True),q,oil)['pressure_drop'] == pytest.approx(expected*75/64)


def test_zero_flow_and_nominal_pipe_selection():
    r = pipe_result(Pipe(),0,Oil())
    assert r['pressure_drop'] == 0 and r['reynolds'] == 0
    r = pipe_result(Pipe(),22e-3/60,Oil())
    assert r['diameter'] == .012
    assert r['velocity'] == pytest.approx(4*(22e-3/60)/(math.pi*.012**2))


@pytest.mark.parametrize('re,regime',[(3000,'transition'),(10000,'turbulent'),(200000,'outside_blasius')])
def test_flow_regime_boundaries(re,regime):
    q = re*46e-6/.02 * math.pi*.02**2/4
    assert pipe_result(Pipe(diameter=.02),q,Oil())['regime'] == regime


def test_thermal_independent_area_and_energy_balance():
    t = Thermal(); r = thermal_result(t,22e-3/60,1500)
    assert r['required_volume'] == pytest.approx(.088)
    assert r['exposed_area'] == pytest.approx(.8*.5+2*.5*(.8+.5))
    assert r['cooler_power'] == pytest.approx(1500-12*1.7*30)
    assert r['equilibrium_temperature'] == pytest.approx(293.15+1500/(12*1.7))


def test_accumulator_boyle_limit_with_absolute_pressures():
    a = Accumulator(enabled=True,exponent=1)
    r = accumulator_result(a)
    p1,p2 = 100e5+101325,160e5+101325
    p0 = .9*p1
    assert r['required_volume'] == pytest.approx(.001/(p0*(1/p1-1/p2)))
    assert r['nominal_volume'] >= r['required_volume']
    assert accumulator_result(Accumulator()) == {'status':'disabled'}


def test_cycle_independent_duration_work_rms_and_multi_cylinder_reference():
    c = Cylinder(); c2 = replace(c,id='C2',bore=.08,initial_position=.2)
    phases = (Phase(force=10000,speed=.02),Phase('İkinci','C2','retract',2000,.2,None,4.),
              Phase('Boşta',kind='idle',force=0,speed=None,duration=2.))
    p = Project(cylinders=(c,c2),phases=phases)
    r = calculate_project(p); results = r.cycle['phases']
    assert r.cycle['duration'] == pytest.approx(15+4+2)
    assert r.cycle['rms_power'] == pytest.approx(math.sqrt(sum(s.shaft_power**2*s.duration for s in results)/21))
    shaft_energy = sum(s.shaft_power*s.duration for s in results)
    assert r.cycle['loss_energy'] == pytest.approx(shaft_energy-10000*.3-2000*.2)
    assert results[1].flow == pytest.approx(math.pi*(.08**2-.036**2)/4*.05)
    assert results[2].pressure == 0 and results[2].supply_pressure == p.pump.idle_pressure


def test_infeasible_demand_retains_requested_speed_and_warns():
    p = replace(Project(),phases=(Phase(speed=2.),))
    r = calculate_project(p)
    assert not r.feasible
    assert r.cycle['phases'][0].speed == 2.
    assert not r.cycle['phases'][0].feasible
    assert any(i.code == 'CAPACITY' for i in r.issues)


def test_hold_on_fixed_pump_is_heat_not_useful_work():
    r = calculate_project(replace(Project(),phases=(Phase(kind='hold',speed=None,duration=3.),)))
    s = r.cycle['phases'][0]
    assert s.useful_power == 0 and s.heat_power == s.shaft_power
    assert r.cycle['max_flow'] == 0


def test_return_pipe_contains_relief_flow_during_hold():
    p = replace(Project(),pipe=Pipe(role='return'),phases=(Phase(kind='hold',speed=None,duration=3.),))
    r = calculate_project(p)
    assert r.pipe['flow'] == pytest.approx(pump_flow(p.pump))
    assert r.cycle['max_tank_return_flow'] == pytest.approx(pump_flow(p.pump))


def test_demand_failure_labels_thermal_result_as_scenario_only():
    r = calculate_project(replace(Project(),phases=(Phase(speed=10),)))
    assert not r.cycle['demand_met'] and r.thermal['status'] == 'scenario_only'


def test_pres_example_has_physical_positions_and_returns_home():
    r = calculate_project(Project())
    assert [(p.start_position,p.end_position) for p in r.cycle['phases']] == pytest.approx(
        [(0.,.25),(.25,.3),(.3,.3),(.3,0.)])
    assert r.cycle['repeatable_geometry']


def test_combined_forward_strokes_cannot_exceed_cylinder_travel():
    with pytest.raises(InputError,match='ardışık'):
        calculate_project(replace(Project(),phases=(Phase(stroke=.2),Phase(stroke=.2))))


def test_pressure_compensator_and_relief_settings_are_consistent():
    pump = pump_for_type('axial_variable',control='pressure',compensator_pressure=160e5)
    r = calculate_project(replace(Project(),pump=pump))
    assert r.cycle['relief_pressure'] == pytest.approx(176e5)
    assert r.cycle['demand_met']
    bad = calculate_project(replace(Project(),pump=pump,relief_pressure=140e5))
    assert not bad.cycle['demand_met']
    unsafe = calculate_project(replace(Project(),relief_pressure=300e5))
    assert any(i.code == 'RELIEF_LIMIT' and i.severity == 'critical' for i in unsafe.issues)


def test_oil_examples_and_high_pressure_speed_guidance():
    from modules.hydraulic_unit.core.piping import oil_for_grade, recommended_velocity
    assert viscosity(oil_for_grade('ISO VG 32')) == pytest.approx(32e-6)
    assert viscosity(oil_for_grade('ISO VG 68')) == pytest.approx(68e-6)
    assert recommended_velocity('pressure',210e5) == (5.,8.)
    with pytest.raises(InputError): viscosity(Oil(grade='ISO VG 32'))


@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf'),True])
def test_invalid_bores_rejected(value):
    with pytest.raises(InputError): areas(Cylinder(bore=value))


@pytest.mark.parametrize('c',[Cylinder(rod=.063),Cylinder(rod=.08),Cylinder(efficiency=1.1),Cylinder(efficiency=0)])
def test_invalid_cylinder_geometry_efficiency(c):
    with pytest.raises(InputError): areas(c)


@pytest.mark.parametrize('phase',[Phase(speed=0),Phase(speed=-1),Phase(speed=.1,duration=2),
    Phase(speed=None,duration=None),Phase(stroke=.4),Phase(cylinder_id='missing'),
    Phase(kind='hold',speed=None,duration=0),Phase(kind='idle',speed=None,duration=2),
    Phase(kind='regenerate',back_pressure=1e5)])
def test_invalid_phases_have_field_errors(phase):
    with pytest.raises(InputError): calculate_project(replace(Project(),phases=(phase,)))


def test_other_invalid_settings():
    invalid = [replace(Project(),cylinders=(Cylinder(),Cylinder())),
        replace(Project(),pump=Pump(control='pressure')),
        replace(Project(),overload=2),replace(Project(),relief_factor=.9),
        replace(Project(),pipe=Pipe(min_velocity=6,max_velocity=3)),
        replace(Project(),oil=Oil(nu100=50e-6)),
        replace(Project(),thermal=Thermal(target=280)),
        replace(Project(),accumulator=Accumulator(enabled=True,minimum_pressure=160e5,maximum_pressure=100e5))]
    for p in invalid:
        with pytest.raises(InputError): calculate_project(p)


def test_core_imports_without_qt_or_cad_in_fresh_process():
    code = '''import sys
from modules.hydraulic_unit.core import Project, calculate_project
from modules.hydraulic_unit.service import describe, calculate
calculate_project(Project()); describe(); calculate(Project())
assert not any(m in sys.modules for m in ('PySide6','pythoncom','OCP','tkinter'))
'''
    subprocess.run([sys.executable,'-c',code],check=True,timeout=20)
