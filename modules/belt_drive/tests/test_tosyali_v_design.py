"""Manufacturer-reference examples and real stock groove decisions."""
from collections import Counter
from dataclasses import replace
import json
import math
import threading

import pytest

from modules.belt_drive.calculation import calculate
from modules.belt_drive.catalog.tosyali_v import catalog, parse_layout
from modules.belt_drive.design_models import DesignRequest
from modules.belt_drive.design_serialization import DesignProject, project_dumps, project_loads, recalculate_project, report_to_dict
from modules.belt_drive.engineering.optibelt_sk import rate, reference_data
from modules.belt_drive.models import BeltDriveSpecification, BeltSpecification, PulleySpecification, LoadSpecification, CenterSpecification
from modules.belt_drive.nominal_design import NominalSizingOptions, size_drive
from modules.belt_drive.tosyali_design import chart_sections, TosyaliCandidate

OPTIONS=NominalSizingOptions(pulley_source='tosyali_v_sk2018')


def req(**kwargs):
    return DesignRequest(**dict(dict(power_kw=22.,input_rpm=1450.,target_rpm=725.,family='v',service_factor=1.3,
                                    rpm_error_max_percent=1.),**kwargs))


def result(profile='SPB', d1=280., d2=500., rpm=1485., power=132., service=1.3, length=4000.):
    return calculate(BeltDriveSpecification(BeltSpecification('v',profile),PulleySpecification(d1),PulleySpecification(d2),
        LoadSpecification(rpm,power,service_factor=service),CenterSpecification('length',None,length)))


def test_published_optibelt_example_printed_p87_requires_eight_spb_belts():
    r=result();p=rate('SPB',r)
    # The book rounds centre/PN/c1. The engine keeps exact tangency and table
    # interpolation: 1450/1500 rpm, 20.30/20.78 kW, increment 1.20/1.24.
    assert p.base_power_kw==pytest.approx(20.30+.7*(20.78-20.30))
    assert p.additional_power_kw==pytest.approx(1.20+.7*(1.24-1.20))
    assert p.length_factor==pytest.approx(1.02)
    assert p.design_power_kw==pytest.approx(171.6)
    assert p.required_belts==8
    assert p.per_belt_power_kw==pytest.approx(22.2608119861)
    assert not p.manufacturer_verified


@pytest.mark.parametrize('profile,d,base,add,length',[
    ('SPZ',80,1.62,.23,1600),('SPA',125,4.53,.54,2500),
    ('SPB',200,12.53,1.20,3550),('SPC',315,33.30,3.25,5600)])
def test_transcribed_reference_table_points(profile,d,base,add,length):
    p=rate(profile,result(profile,d,2*d,1450,5,1.2,length))
    assert p.base_power_kw==pytest.approx(base)
    assert p.additional_power_kw==pytest.approx(add)
    assert p.length_factor==pytest.approx(1.)


def test_faster_driven_pulley_uses_its_own_rpm_not_input_rpm():
    normal=rate('SPB',result())
    reverse=rate('SPB',result(d1=500,d2=280,rpm=1485*280/500))
    assert reverse.small_rpm==pytest.approx(1485.)
    assert reverse.per_belt_power_kw==pytest.approx(normal.per_belt_power_kw)
    equal=rate('SPB',result(d1=280,d2=280))
    assert equal.additional_power_kw==0.


@pytest.mark.parametrize('changes',[dict(rpm=99),dict(d1=139),dict(length=11000),dict(d1=400,d2=400,rpm=3000)])
def test_no_rating_extrapolation_or_interpolation_through_blank_cells(changes):
    with pytest.raises(ValueError):rate('SPB',result(**changes))


def test_pulley_catalogue_facts_and_quarantine_are_preserved():
    rows=catalog()
    assert len(rows)==708
    assert Counter(r.profile for r in rows)==dict(SPZ=181,SPA=189,SPB=198,SPC=140)
    assert sorted({r.grooves for r in rows})==[1,2,3,4,5,6,8,10]
    assert not any(r.code=='T SPB 565-2' for r in rows)
    accepted,problems=parse_layout('T SPB 565-2 2 560 567 4\nT SPA 250-4 4 250 255,5 6\nT SPA 250-4 4 250 255.5 6')
    assert len(accepted)==1 and len(problems)==2
    assert accepted[0].datum_mm==250 and accepted[0].grooves==4


@pytest.mark.parametrize('profile',['SPZ','SPA','SPB','SPC'])
def test_each_narrow_section_has_rated_catalogue_pairs(profile):
    report=size_drive(req(profile=profile,power_kw=5.),OPTIONS)
    assert report.candidates and report.search_complete
    for c in report.candidates:
        assert isinstance(c,TosyaliCandidate)
        p=c.rating
        assert c.belt_count>=p.required_belts==math.ceil(p.design_power_kw/p.per_belt_power_kw)
        assert c.driver_pulley.grooves==c.driven_pulley.grooves==c.belt_count==c.result.specification.belt.count
        assert c.result.speed_m_s<=35.
        assert c.result.center_mm>(c.driver_pulley.outside_mm+c.driven_pulley.outside_mm)/2
        assert c.result.selected_length_mm in reference_data()['profiles'][profile]['listed_lengths_mm']
        assert not c.engineering_approved


def test_required_seven_belts_selects_eight_actual_catalogue_grooves():
    options=replace(OPTIONS,length_policy='required')
    report=size_drive(req(profile='SPB',power_kw=100.,input_rpm=1485.,target_rpm=831.6,
                          mode='fixed',center_target_mm=1383.01261386,center_tolerance_mm=0.,
                          diameter_min_mm=280.,diameter_max_mm=500.,rpm_error_max_percent=.00001),options)
    c=next(c for c in report.candidates if c.driver_pulley.datum_mm==280 and c.driven_pulley.datum_mm==500)
    assert c.rating.required_belts==6  # 130 / 22.2608 = 5.84
    report=size_drive(replace(report.request,power_kw=110.),options)
    c=next(c for c in report.candidates if c.driver_pulley.datum_mm==280 and c.driven_pulley.datum_mm==500)
    assert c.rating.required_belts==7 and c.belt_count==8
    assert c.driver_pulley.code.endswith('-8') and c.driven_pulley.code.endswith('-8')
    limited=size_drive(replace(report.request,max_belts=7),options)
    assert not any(c.driver_pulley.datum_mm==280 and c.driven_pulley.datum_mm==500 for c in limited.candidates)


@pytest.mark.parametrize('changes',[dict(service_factor=None),dict(family='timing',profile='HTD_5M'),
    dict(profile='A'),dict(system_width_max_mm=50),dict(available_tensioning_travel_mm=10)])
def test_missing_service_or_unsupported_constraints_fail_explicitly(changes):
    with pytest.raises(ValueError):size_drive(req(**changes),OPTIONS)


def test_limits_budget_and_cancellation_are_honoured():
    report=size_drive(req(maximum_belt_speed_m_s=5.,max_belts=2),OPTIONS)
    assert all(c.result.speed_m_s<=5 and c.belt_count<=2 for c in report.candidates)
    limited=size_drive(req(work_limit=10),OPTIONS)
    assert not limited.search_complete
    stop=threading.Event();stop.set()
    cancelled=size_drive(req(),OPTIONS,stop=stop)
    assert cancelled.cancelled and not cancelled.candidates


def test_approximate_chart_advice_cannot_replace_power_calculation():
    assert chart_sections(22,1450)==('SPB',)
    assert chart_sections(3,1450)==('SPA',)
    assert chart_sections(100,1000)==('SPC',)
    assert chart_sections(1000,1450)==()
    assert {c.result.specification.belt.profile for c in size_drive(req(power_kw=5),OPTIONS).candidates}=={'SPZ','SPA','SPB','SPC'}


def test_reference_method_project_and_report_roundtrip():
    report=size_drive(req(profile='SPA',power_kw=3.),OPTIONS)
    chosen=(report.candidates[0].identifier,)
    project=DesignProject(request=report.request,nominal_options=OPTIONS,selected_ids=chosen)
    restored=project_loads(project_dumps(project));recomputed,selected=recalculate_project(restored)
    assert recomputed==report and selected==chosen
    exported=report_to_dict(report,selected_ids=chosen)
    assert exported['candidates'][0]['rating']['required_belts']>=1
    assert exported['candidates'][0]['driver_pulley']['code'].startswith('T SPA')
    json.dumps(exported,allow_nan=False)
