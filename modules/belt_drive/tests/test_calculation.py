from dataclasses import FrozenInstanceError, replace
import math
from threading import Event

import pytest

from modules.belt_drive import (calculate, BeltDriveSpecification, BeltSpecification, PulleySpecification,
                                LoadSpecification, CenterSpecification, SpecificationError)
from modules.belt_drive.catalog.profiles import get_profile, PROFILES
from modules.belt_drive.engineering.belt_length import length_metrics, solve_center_distance
from modules.belt_drive.engineering.kinematics import power_kw, torque_nm
from modules.belt_drive.validation import CalculationCancelled


def timing(profile='HTD_5M'):
    return BeltDriveSpecification(belt=BeltSpecification('timing', profile),
        driver=PulleySpecification(None, 20), driven=PulleySpecification(None, 40),
        load=LoadSpecification(input_rpm=1500., power_kw=1.5), center=CenterSpecification(distance_mm=200.))


def test_reference_scenario_against_independent_60_digit_decimal_oracle():
    # Values were obtained separately with Decimal sqrt/asin Taylor expansion,
    # not by using the engine under test as its own reference.
    result = calculate(BeltDriveSpecification())
    assert result.ratio == 2. and result.nominal_output_rpm == 725.
    assert result.speed_m_s == pytest.approx(7.5921822461753336596180548429254653, rel=1e-14)
    assert result.effective_force_delta_n == pytest.approx(658.57217831129104456089833119661115, rel=1e-14)
    assert result.input_torque_nm == pytest.approx(32.92860891556455222804491655983056, rel=1e-14)
    assert result.length_exact_mm == pytest.approx(1277.497074474652702607337932219412, abs=2e-12)
    assert result.length_approximate_mm == pytest.approx(1277.488898038468985769396507491925, abs=2e-12)
    assert result.driver_wrap_deg == pytest.approx(165.63848843708343735392200874770, abs=1e-12)
    assert result.approximation_minus_exact_mm < 0
    assert result.reference_line == 'datum'


@pytest.mark.parametrize('power,rpm', [(5., 1450.), (.001, 3.), (125., 30000.)])
def test_power_and_torque_conversion_preserves_angular_power(power, rpm):
    torque = torque_nm(power, rpm)
    assert torque * (rpm * 2 * math.pi / 60) == pytest.approx(power * 1000, rel=2e-15)
    assert power_kw(torque, rpm) == pytest.approx(power, rel=2e-15)
    spec = BeltDriveSpecification(load=LoadSpecification(input_rpm=rpm, power_kw=None, torque_nm=torque))
    assert calculate(spec).input_power_kw == pytest.approx(power)


def test_missing_information_does_not_become_zero_or_approval():
    result = calculate(BeltDriveSpecification())
    assert result.shaft_forces is result.efficiency_output_torque_nm is result.design_power_kw is None
    assert result.geometry_valid and not result.production_approved and not result.power_capacity_verified
    assert not result.cad_available
    missing = {issue.code for issue in result.checks if issue.severity == 'NOT_EVALUATED'}
    assert {'POWER_CAPACITY', 'SHAFT_FORCE', 'BEARING_REACTIONS', 'BELT_COUNT_SIZING', 'EFFICIENCY', 'ACTUAL_OUTPUT_SPEED'} <= missing


def test_explicit_efficiency_and_service_factor_are_separate_from_nominal_force():
    base = calculate(BeltDriveSpecification())
    result = calculate(BeltDriveSpecification(load=LoadSpecification(efficiency=.9, service_factor=1.5)))
    assert result.efficiency_output_power_kw == 4.5 and result.design_power_kw == 7.5
    assert result.efficiency_output_torque_nm == pytest.approx(base.ideal_output_torque_nm * .9)
    assert result.effective_force_delta_n == base.effective_force_delta_n
    assert result.design_force_delta_n == pytest.approx(base.effective_force_delta_n * 1.5)
    assert not result.power_capacity_verified


@pytest.mark.parametrize('profile,pitch', [('HTD_3M', 3.), ('HTD_5M', 5.), ('HTD_8M', 8.), ('T5', 5.),
                                          ('T10', 10.), ('AT5', 5.), ('AT10', 10.)])
def test_timing_pitch_identity_and_fractional_mesh_are_preserved(profile, pitch):
    result = calculate(timing(profile))
    assert result.driver_reference_diameter_mm == pytest.approx(20 * pitch / math.pi)
    assert result.ratio == 2 and result.nominal_output_rpm == 750.
    assert result.reference_line == 'pitch' and result.pitch_mm == pitch
    expected = 20 * result.driver_wrap_deg / 360.
    assert result.engaged_driver_teeth_estimate == pytest.approx(expected)
    assert result.engaged_driver_teeth_estimate != math.floor(result.engaged_driver_teeth_estimate)


@pytest.mark.parametrize('profile', ['Z', 'A', 'B', 'C', 'D', 'SPZ', 'SPA', 'SPB', 'SPC'])
def test_v_profiles_support_nominal_datum_calculation_without_rating_claim(profile):
    result = calculate(BeltDriveSpecification(belt=BeltSpecification(profile=profile)))
    assert result.reference_line == 'datum' and result.pitch_mm is None
    assert not result.production_approved


@pytest.mark.parametrize('profile,family', [('GT2', 'timing'), ('GT3', 'timing'), ('PJ', 'poly_v'), ('PK', 'poly_v'), ('PL', 'poly_v')])
def test_deferred_profiles_are_reported_but_not_silently_calculated(profile, family):
    assert not get_profile(profile).nominal_supported
    with pytest.raises(SpecificationError):
        calculate(replace(timing(), belt=BeltSpecification(family, profile)))


def test_integer_timing_length_solves_center_without_rounding():
    spec = replace(timing(), center=CenterSpecification(mode='length', distance_mm=None, belt_teeth=110))
    result = calculate(spec)
    assert result.selected_belt_teeth == 110 and result.selected_length_mm == 550.
    assert result.center_mm != round(result.center_mm, 1)
    assert result.length_exact_mm == pytest.approx(550., abs=1e-9)
    assert abs(result.inverse_residual_mm) < 1e-9


@pytest.mark.parametrize('diameters', [(100., 200.), (200., 100.), (100., 100.), (10., 700.)])
def test_inverse_against_independent_circle_tangent_formula(diameters):
    d1, d2 = diameters
    center = (d1 + d2) * 1.75
    r1, r2 = d1 / 2, d2 / 2
    # Independent construction from two tangent spans and absolute small/big arcs.
    angle = math.acos(abs(r2 - r1) / center)
    expected_length = 2 * math.sqrt(center**2 - (r2-r1)**2) + 2*min(r1,r2)*angle + 2*max(r1,r2)*(math.pi-angle)
    inverse = solve_center_distance(d1, d2, expected_length)
    assert inverse.center_mm == pytest.approx(center, abs=2e-9)
    assert abs(inverse.residual_mm) < 2e-9


def test_geometry_and_physical_bounds_are_distinct():
    with pytest.raises(ValueError, match='ortak teğet'):
        length_metrics(100., 200., 50.)
    assert length_metrics(100., 200., 60.).exact_mm > 0  # mathematical route only
    with pytest.raises(SpecificationError, match='kesişmemeli'):
        calculate(BeltDriveSpecification(center=CenterSpecification(distance_mm=60.)))
    minimum = length_metrics(100., 200., 150.).exact_mm
    with pytest.raises(ValueError, match='büyük olmalı'):
        solve_center_distance(100., 200., minimum)


@pytest.mark.parametrize('bad', [0, -1., True, None, '1450', float('nan'), float('inf')])
def test_invalid_rpm_never_produces_a_result(bad):
    with pytest.raises(SpecificationError):
        calculate(BeltDriveSpecification(load=LoadSpecification(input_rpm=bad)))


def test_conflicting_and_incompatible_inputs_are_rejected():
    for spec in (
        BeltDriveSpecification(load=LoadSpecification(power_kw=5., torque_nm=10.)),
        BeltDriveSpecification(load=LoadSpecification(power_kw=None)),
        BeltDriveSpecification(load=LoadSpecification(efficiency=1.01)),
        replace(timing(), belt=BeltSpecification('timing', 'HTD_5M', pitch_mm=3.)),
        replace(timing(), driver=PulleySpecification(None, 20.5)),
        replace(timing(), driver=PulleySpecification(40., 20)),
        BeltDriveSpecification(belt=BeltSpecification(pitch_mm=5.)),
        BeltDriveSpecification(center=CenterSpecification(length_mm=1000.)),
        BeltDriveSpecification(drive_type='crossed'),
        BeltDriveSpecification(rotation='unknown'),
    ):
        with pytest.raises(SpecificationError):
            calculate(spec)


@pytest.mark.parametrize('bad', [0, -1., True, float('nan'), float('inf')])
def test_nonpositive_or_nonfinite_dimensions_and_loads_are_rejected(bad):
    for spec in (
        BeltDriveSpecification(load=LoadSpecification(power_kw=bad)),
        BeltDriveSpecification(driver=PulleySpecification(datum_diameter_mm=bad)),
        BeltDriveSpecification(center=CenterSpecification(distance_mm=bad)),
        replace(timing(), driver=PulleySpecification(None, bad)),
        BeltDriveSpecification(load=LoadSpecification(power_kw=None, torque_nm=bad)),
        BeltDriveSpecification(pretension_per_belt_n=bad),
    ):
        with pytest.raises(SpecificationError):
            calculate(spec)


def test_inverse_convergence_limit_cancellation_and_numeric_overflow():
    with pytest.raises(ValueError, match='yakınsamadı'):
        solve_center_distance(100., 200., 1277.5, max_iterations=1)
    stop = Event(); stop.set()
    with pytest.raises(CalculationCancelled):
        solve_center_distance(100., 100., 1000., stop=stop)
    with pytest.raises(CalculationCancelled):
        calculate(BeltDriveSpecification(), stop=stop)
    with pytest.raises(SpecificationError):
        calculate(BeltDriveSpecification(load=LoadSpecification(power_kw=1e308, input_rpm=1e-308)))


def test_specs_and_capability_metadata_are_immutable():
    spec = BeltDriveSpecification()
    with pytest.raises(FrozenInstanceError):
        spec.driver.datum_diameter_mm = 10.
    with pytest.raises(FrozenInstanceError):
        PROFILES[0].nominal_supported = False
