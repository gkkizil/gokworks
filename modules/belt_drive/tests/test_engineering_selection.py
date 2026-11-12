"""Independent geometry and published arithmetic; no SKU/brand approval."""
from dataclasses import replace
import json
import math

import pytest

from modules.belt_drive.design_models import DesignRequest
from modules.belt_drive.design_search import search_drives
from modules.belt_drive.design_pairs import search_pulley_pairs
from modules.belt_drive.design_serialization import request_to_dict, request_from_dict
from modules.belt_drive.nominal_design import size_drive
from modules.belt_drive.catalog.rating_models import CorrectionTable
from .design_fixtures import v_catalog, timing_catalog, request


def test_different_commercial_series_can_share_explicit_compatibility():
    cat = v_catalog(rated=True)
    cat = replace(cat, pulleys=tuple(replace(p, series_id='PULLEYS') for p in cat.pulleys))
    req = request(family='v', target_rpm=725.)
    candidate, = search_drives(req, cat).unverified
    assert candidate.capacity.per_belt_power_kw == 2.5
    assert candidate.series_id == cat.belts[0].series_id
    assert candidate.driver.series_id == 'PULLEYS'
    assert not search_drives(replace(req, power_kw=10.), cat).unverified
    pair, = search_pulley_pairs(req, cat).alternatives
    assert pair.ratio == 2


def test_driver_and_driven_pulley_series_may_differ_but_explicit_profile_must_match():
    cat = v_catalog()
    cat = replace(cat, pulleys=(cat.pulleys[0], replace(cat.pulleys[1], series_id='LARGE-PULLEY')))
    assert search_drives(request(family='v', target_rpm=725.), cat).unverified
    assert search_pulley_pairs(request(family='v', target_rpm=725.), cat).alternatives
    bad = replace(cat, pulleys=(cat.pulleys[0], replace(cat.pulleys[1], compatibility_id='OTHER')))
    assert not search_drives(request(family='v', target_rpm=725.), bad).unverified


def test_same_profile_and_compatibility_never_mix_manufacturers():
    cat = v_catalog()
    other = replace(cat.sources[0], identifier='other', manufacturer='OTHER')
    cat = replace(cat, sources=(*cat.sources, other),
                  pulleys=tuple(replace(p, source_id='other', series_id='OTHER') for p in cat.pulleys))
    assert not search_drives(request(family='v', target_rpm=725.), cat).unverified


def test_product_codes_repeated_in_separate_series_keep_unique_candidate_ids():
    cat = v_catalog()
    cat = replace(cat, pulleys=(*cat.pulleys, *(replace(p, series_id='OTHER') for p in cat.pulleys)))
    candidates = search_drives(request(family='v', target_rpm=725.), cat).unverified
    assert len(candidates) == len({c.identifier for c in candidates}) == 4
    legacy = next(c for c in candidates if c.driver.series_id == c.driven.series_id == 'test:v')
    assert json.loads(legacy.identifier) == [['synthetic only', 'test:v', 'A', 'test:A'],
                                            'TEST-V-100.0', 'TEST-V-200.0', 'TEST-V-LD']


def test_an_evaluated_sufficient_capacity_precedes_unknown_capacity():
    cat = v_catalog(rated=True)
    unknown = replace(cat.belts[0], code='AAA-UNKNOWN', series_id='AAA-UNRATED')
    report = search_drives(request(family='v', target_rpm=725.), replace(cat, belts=(unknown, *cat.belts)))
    assert len(report.unverified) == 2
    assert report.unverified[0].capacity.meets_declared_demand is True
    assert report.unverified[1].capacity.meets_declared_demand is None
    assert not report.capacity_verified


def test_fixed_center_tolerance_retains_valid_region_when_target_overlaps():
    req = DesignRequest(3., 1450., 1450., profile='A', diameter_min_mm=630., diameter_max_mm=630.,
                        mode='fixed', center_target_mm=600., center_tolerance_mm=100., rpm_error_max_percent=0.)
    candidate, = size_drive(req).candidates
    assert candidate.length_kind == 'preferred_r40'
    # Equal pulleys: L = 2C + pi*D, independent of the inverse solver.
    assert candidate.result.center_mm == pytest.approx((3350.-630.*math.pi)/2, abs=1e-8)
    assert 630 < candidate.result.center_mm <= 700
    assert candidate.center_deviation_mm == pytest.approx(candidate.result.center_mm-600)
    assert any(c.code == 'TARGET_CENTER_ADJUSTED' for c in candidate.checks)


def test_discrete_timing_length_precedes_theoretical_fallback_in_preferred_mode():
    req = DesignRequest(1., 1500., 750., family='timing', profile='HTD_5M', teeth_min=20, teeth_max=40,
                        mode='fixed', center_target_mm=100., center_tolerance_mm=0., rpm_error_max_percent=100.,
                        result_limit=500)
    candidates = size_drive(req).candidates
    assert candidates[0].length_kind == 'integer_pitch'
    fallback = [c for c in candidates if c.length_kind == 'required']
    assert fallback and any(c.rpm_error_percent == 0 for c in fallback)
    assert all(any(i.code == 'TIMING_LENGTH_UNSELECTED' for i in c.checks) for c in fallback)


@pytest.mark.parametrize('limits,reason', [
    ({'minimum_wrap_deg': 170.}, 'MINIMUM_WRAP'),
    ({'maximum_belt_speed_m_s': 5.}, 'BELT_SPEED_LIMIT'),
])
def test_catalog_candidates_obey_declared_operating_limits(limits, reason):
    req = request(family='v', target_rpm=725., **limits)
    report = search_drives(req, v_catalog())
    assert not report.unverified and dict(report.rejection_counts)[reason]


def test_timing_catalog_uses_small_pulley_engagement():
    req = request(minimum_engaged_teeth=14.)
    report = search_drives(req, timing_catalog())
    assert not report.unverified and dict(report.rejection_counts)['MINIMUM_ENGAGED_TEETH']


@pytest.mark.parametrize('family,profile', [('v', 'A'), ('timing', 'HTD_5M')])
def test_nominal_wrap_constraint_solves_for_a_larger_feasible_center(family, profile):
    req = DesignRequest(1., 1500., 750., family=family, profile=profile,
                        diameter_min_mm=100. if family == 'v' else None,
                        diameter_max_mm=200. if family == 'v' else None,
                        teeth_min=20, teeth_max=40, rpm_error_max_percent=0., minimum_wrap_deg=170.)
    candidate, = size_drive(req).candidates
    r = candidate.result
    independent_wrap = 180-2*math.degrees(math.asin(abs(r.driven_reference_diameter_mm-r.driver_reference_diameter_mm)/(2*r.center_mm)))
    assert independent_wrap >= 170-1e-9
    assert candidate.length_kind != 'required'


def test_engagement_limit_can_make_a_center_interval_impossible():
    req = DesignRequest(1., 1500., 750., family='timing', profile='HTD_5M', teeth_min=20, teeth_max=40,
                        mode='range', center_min_mm=80., center_max_mm=100., rpm_error_max_percent=0.,
                        minimum_engaged_teeth=9.8)
    report = size_drive(req)
    assert not report.candidates and dict(report.rejection_counts)['OPERATING_CENTER_BOUNDS']


@pytest.mark.parametrize('changes', [dict(minimum_wrap_deg=181.), dict(minimum_wrap_deg=0.),
                                    dict(maximum_belt_speed_m_s=float('inf')), dict(minimum_engaged_teeth=6.)])
def test_invalid_operating_limits_are_rejected(changes):
    with pytest.raises(ValueError):
        DesignRequest(1., 1500., 750., **changes)


def test_operating_limits_survive_request_roundtrip_and_legacy_missing_fields():
    req = request(minimum_wrap_deg=150., maximum_belt_speed_m_s=20., minimum_engaged_teeth=6.)
    assert request_from_dict(request_to_dict(req)) == req
    legacy = request_to_dict(request())
    for name in ('minimum_wrap_deg', 'maximum_belt_speed_m_s', 'minimum_engaged_teeth'):legacy.pop(name)
    assert request_from_dict(legacy) == request()


def test_gates_published_worked_example_arithmetic_requires_two_belts():
    """Gates manual p.B6: 10hp*1.2 / ((7.01+.08)*1.1) -> 2 belts.

    Only the published arithmetic is transposed onto synthetic A geometry.
    This does not validate 3VX dimensions or supply a manufacturer catalogue.
    """
    hp_kw = 0.7456998715822702
    cat = v_catalog(rated=True, grooves=2)
    table = replace(cat.ratings[0], base_power_kw=((7.01*hp_kw,), (7.01*hp_kw,)),
                    additional_power_kw=.08*hp_kw,
                    corrections=(CorrectionTable('wrap_deg', (90.,180.), (1.,1.), 'linear_declared'),
                                 CorrectionTable('length_mm', (500.,2000.), (1.1,1.1), 'linear_declared')))
    cat = replace(cat, ratings=(table,))
    candidate, = search_drives(request(family='v', target_rpm=725., power_kw=10.*hp_kw, service_factor=1.2), cat).unverified
    cap = candidate.capacity
    assert cap.design_power_kw == pytest.approx(12.*hp_kw)
    assert cap.per_belt_power_kw == pytest.approx(7.799*hp_kw)
    assert cap.required_belts == 2 and cap.meets_declared_demand is True
    assert not cap.manufacturer_verified
