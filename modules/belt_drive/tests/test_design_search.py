"""Search tests use finite declared SKU sets, not fabricated manufacturer stock."""

from dataclasses import FrozenInstanceError, replace
import math
from threading import Event

import pytest

from modules.belt_drive.design_search import search_drives
from .design_fixtures import timing_catalog, v_catalog, request, with_rating


def test_1450_to_700_uses_only_exact_catalog_teeth_and_nominal_ratio():
    report = search_drives(request(rpm_error_max_percent=0), timing_catalog())
    assert report.search_complete and report.target_ratio == pytest.approx(1450/700)
    candidate, = report.unverified
    assert (candidate.driver.teeth, candidate.driven.teeth) == (28, 58)
    assert candidate.result.nominal_output_rpm == pytest.approx(700, abs=1e-10)
    assert candidate.rpm_error_percent < 1e-10
    assert candidate.result.length_exact_mm == pytest.approx(800., abs=1e-9)
    assert not candidate.engineering_approved and not candidate.result.production_approved
    assert not report.capacity_verified and candidate.capacity.status == 'NOT_EVALUATED'


def test_mathematically_perfect_but_absent_pulley_is_not_invented():
    report = search_drives(request(), timing_catalog(teeth=(28, 56)))
    assert report.search_complete and not report.unverified
    assert dict(report.rejection_counts)['RPM_TOLERANCE'] == 4


def test_fixed_center_and_single_length_inverse_against_independent_reference():
    req = request(family='v', target_rpm=725., mode='fixed', center_target_mm=400., center_tolerance_mm=0,
                  rpm_error_max_percent=0.)
    report = search_drives(req, v_catalog())
    candidate, = report.unverified
    assert candidate.result.center_mm == pytest.approx(400., abs=1e-9)
    assert candidate.theoretical_length_at_target_mm == pytest.approx(1277.4970744746527, abs=2e-12)
    assert candidate.center_deviation_mm == pytest.approx(0., abs=1e-9)
    assert report.lengths_evaluated == report.geometry_solved == 1
    assert any(x.code == 'SLIP' and x.severity == 'NOT_EVALUATED' for x in candidate.checks)


def test_fixed_center_tolerance_is_not_mistaken_for_installation_allowance():
    req = request(family='v', target_rpm=725., mode='fixed', center_target_mm=400., center_tolerance_mm=0)
    candidate, = search_drives(req, v_catalog(rated=True)).unverified
    assert candidate.capacity.installation_allowance_mm == 5.
    assert not candidate.engineering_approved
    assert not search_drives(replace(req, available_installation_travel_mm=4.), v_catalog(rated=True)).unverified


@pytest.mark.parametrize('low,high,expected', [(300., 500., True), (401., 500., False), (300., 399., False), (400., 400., True)])
def test_center_range_boundaries(low, high, expected):
    req = request(family='v', target_rpm=725., mode='range', center_min_mm=low, center_max_mm=high)
    assert bool(search_drives(req, v_catalog()).unverified) is expected


def test_multiple_alternatives_sorted_deterministically_independent_of_catalog_order():
    cat = timing_catalog(teeth=(28, 56, 58, 60), counts=(160, 170), widths=(10., 20.))
    req = request(rpm_error_max_percent=10.)
    one = search_drives(req, cat)
    two = search_drives(req, replace(cat, belts=tuple(reversed(cat.belts)), pulleys=tuple(reversed(cat.pulleys))))
    assert len(one.unverified) > 4
    assert [x.identifier for x in one.unverified] == [x.identifier for x in two.unverified]
    assert [x.rpm_error_percent for x in one.unverified] == sorted(x.rpm_error_percent for x in one.unverified)


def test_filtering_and_empty_catalog_never_returns_a_suitable_result():
    cat = timing_catalog()
    for req in (request(manufacturer='Gates'), request(series_id='absent'), request(diameter_max_mm=40),
                request(teeth_max=30), request(system_width_max_mm=29)):
        report = search_drives(req, cat)
        assert not report.unverified and not report.capacity_verified and report.search_complete
    assert not search_drives(request(), replace(cat, belts=())).unverified


def test_speed_tolerance_boundary_and_diameter_inclusivity():
    # 28/56 yields exactly 725 rpm, 25/700 * 100 percent error.
    req = request(rpm_error_max_percent=100*25/700.)
    assert search_drives(req, timing_catalog(teeth=(28,56))).unverified
    assert not search_drives(replace(req, rpm_error_max_percent=3.5), timing_catalog(teeth=(28,56))).unverified
    diameter = 58*5/math.pi
    assert search_drives(request(diameter_max_mm=diameter), timing_catalog()).unverified
    assert not search_drives(request(diameter_max_mm=diameter-1e-5), timing_catalog()).unverified


def test_driving_larger_and_equal_pulleys():
    report = search_drives(request(target_rpm=1450*58/28, rpm_error_max_percent=0.), timing_catalog(rated=True))
    candidate, = report.unverified
    assert candidate.driver.teeth == 58 and candidate.driven.teeth == 28
    # Synthetic base law is independently specified: z/10 + rpm/1000 - 1.
    expected = 28/10 + (1450*58/28)/1000 - 1
    assert candidate.capacity.per_belt_power_kw == pytest.approx(expected)
    report = search_drives(request(target_rpm=1450., rpm_error_max_percent=0.), timing_catalog(teeth=(28,)))
    equal, = report.unverified
    assert equal.result.center_mm == pytest.approx((800 - 28*5)/2., abs=1e-9)
    assert equal.result.driver_wrap_deg == 180.


def test_same_pitch_different_profile_or_compatibility_id_not_automatically_compatible():
    cat = timing_catalog()
    for belts in ((replace(cat.belts[0], profile='T5'),),
                  (replace(cat.belts[0], compatibility_id='other'),)):
        report = search_drives(request(), replace(cat, belts=belts))
        assert not report.unverified and report.excluded_products > 0


def test_unverified_requires_opt_in_and_sources_cannot_self_approve():
    cat = timing_catalog(rated=True)
    cat = replace(cat, sources=(replace(cat.sources[0], verification_status='OFFICIAL_VERIFIED', manufacturer='Gates'),))
    report = search_drives(request(include_unverified=False), cat)
    assert report.unverified_count == 1 and not report.unverified and not report.capacity_verified
    candidate, = search_drives(request(), cat).unverified
    assert candidate.source_statuses == ('USER_SUPPLIED',)
    assert candidate.capacity.status == 'PROVISIONAL' and not candidate.capacity.manufacturer_verified


def test_count_width_capacity_constraints_precede_preference_ranking():
    cat = v_catalog(rated=True, grooves=4)
    req = request(family='v', target_rpm=725., power_kw=5., service_factor=1.5, priority='capacity')
    candidate, = search_drives(req, cat).unverified
    assert candidate.capacity.required_belts == 3 and candidate.capacity.total_power_kw == 10.
    assert candidate.capacity.capacity_margin == pytest.approx(10/7.5)
    assert not search_drives(replace(req, max_belts=3), cat).unverified
    assert not search_drives(replace(req, system_width_max_mm=99), cat).unverified
    assert not search_drives(req, v_catalog(rated=True, grooves=2)).unverified


def test_source_limits_and_width_compatibility_are_hard_filters():
    req, cat = request(), timing_catalog(rated=True)
    assert not search_drives(req, with_rating(cat, minimum_pulley=29)).unverified
    assert not search_drives(req, with_rating(cat, maximum_speed_m_s=1.)).unverified
    assert not search_drives(req, timing_catalog(widths=(26.,))).unverified


def test_result_limit_does_not_falsely_truncate_the_search_scope():
    report = search_drives(request(result_limit=1, rpm_error_max_percent=10.), timing_catalog(teeth=(28, 56, 58, 60), counts=(160, 170)))
    assert len(report.unverified) == 1 and report.unverified_count > 1
    assert report.search_complete and report.results_limited
    bounded = search_drives(request(work_limit=1), timing_catalog())
    assert not bounded.search_complete and bounded.stop_reason and bounded.pairs_visited == 1


def test_cancellation_before_and_during_search_and_progress_on_rejected_pairs():
    event = Event(); event.set()
    for cat in (timing_catalog(), replace(timing_catalog(), belts=(), pulleys=())):
        report = search_drives(request(), cat, stop=event)
        assert report.cancelled and not report.search_complete and not report.unverified
    event.clear()
    def progress(pairs, lengths):
        event.set()
    cat = timing_catalog(teeth=tuple(range(20,40)), counts=(160, 170))
    report = search_drives(request(target_rpm=1.), cat, stop=event, progress=progress)
    assert report.cancelled and report.pairs_visited < 400 and report.lengths_evaluated == 0


@pytest.mark.parametrize('changes', [dict(power_kw=0), dict(input_rpm=True), dict(target_rpm=float('inf')),
    dict(mode='range'), dict(mode='fixed', center_target_mm=400.), dict(center_min_mm=500., center_max_mm=300.),
    dict(priority='center'), dict(max_belts=1.5), dict(include_unverified='yes'), dict(family='poly_v'),
    dict(profile='T5', family='v'), dict(daily_hours=25.), dict(rpm_error_max_percent=-1.),
    dict(priority='balanced', weights=(('price',1.),)), dict(priority='balanced', weights=(('area',-1.),))])
def test_invalid_requests_rejected(changes):
    with pytest.raises(ValueError):
        request(**changes)


def test_immutable_result_and_request():
    req = request()
    report = search_drives(req, timing_catalog())
    with pytest.raises(FrozenInstanceError):
        req.power_kw = 7
    with pytest.raises(FrozenInstanceError):
        report.unverified[0].belt.width_mm = 1


def test_known_width_violations_not_hidden_by_other_unknown_dimensions():
    cat=timing_catalog()
    cat=replace(cat,pulleys=(replace(cat.pulleys[0],overall_width_mm=100.),replace(cat.pulleys[1],overall_width_mm=None)))
    assert not search_drives(request(system_width_max_mm=50.),cat).unverified
    cat=timing_catalog()
    cat=replace(cat,pulleys=tuple(replace(p,face_width_mm=None,overall_width_mm=5.) for p in cat.pulleys))
    assert not search_drives(request(),cat).unverified


def test_real_outer_body_constraints_do_not_change_reference_line_math():
    cat=timing_catalog()
    big=replace(cat,pulleys=tuple(replace(p,outside_diameter_mm=1000.) for p in cat.pulleys))
    assert not search_drives(request(),big).unverified
    assert dict(search_drives(request(outside_diameter_max_mm=100.),big).rejection_counts)['OUTSIDE_DIAMETER']>0
    small=replace(cat,pulleys=tuple(replace(p,outside_diameter_mm=100.) for p in cat.pulleys))
    candidate,=search_drives(request(outside_diameter_max_mm=100.),small).unverified
    assert candidate.result.ratio==pytest.approx(58/28)


def test_ranking_preferences_and_balanced_missing_data_are_deterministic():
    cat=timing_catalog(rated=True,widths=(10.,20.),counts=(160,170))
    compact=search_drives(request(priority='compact'),cat).unverified
    assert [x.reference_area_mm2 for x in compact]==sorted(x.reference_area_mm2 for x in compact)
    centered=search_drives(request(priority='center',center_target_mm=300.),cat).unverified
    assert [abs(x.center_deviation_mm) for x in centered]==sorted(abs(x.center_deviation_mm) for x in centered)
    req=request(priority='balanced',weights=(('speed',3.),('area',1.),('capacity',2.)))
    one=search_drives(req,cat);two=search_drives(req,cat)
    assert one==two and all(not x.engineering_approved for x in one.unverified)


def test_one_unrepresentable_pair_does_not_abort_other_catalog_candidates():
    cat=v_catalog()
    extra=replace(cat.pulleys[0],code='HUGE',datum_diameter_mm=1e308)
    cat=replace(cat,pulleys=(*cat.pulleys,extra))
    report=search_drives(request(family='v',target_rpm=725.,rpm_error_max_percent=None),cat)
    assert report.search_complete and report.unverified
    assert any(key.startswith('PAIR_') for key,_ in report.rejection_counts)


def test_total_axial_envelope_requires_offsets_not_only_maximum_part_width():
    cat=timing_catalog()
    unknown,=search_drives(request(system_width_max_mm=35.),cat).unverified
    assert unknown.system_width_mm is None and unknown.system_width_lower_bound_mm==30.
    offset=replace(cat,pulleys=(replace(cat.pulleys[0],axial_min_mm=-10.,axial_max_mm=20.),
                               replace(cat.pulleys[1],axial_min_mm=-20.,axial_max_mm=10.)))
    candidate,=search_drives(request(system_width_max_mm=40.),offset).unverified
    assert candidate.system_width_mm==40. and candidate.system_width_lower_bound_mm==30.
    assert not search_drives(request(system_width_max_mm=35.),offset).unverified
    invalid=replace(cat,pulleys=tuple(replace(p,axial_min_mm=10.,axial_max_mm=40.) for p in cat.pulleys))
    assert not search_drives(request(),invalid).unverified
