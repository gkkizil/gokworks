"""General sizing must work without a catalogue; stock/capacity is never invented."""

import math
from queue import Queue
from threading import Event
import json
import subprocess
import sys
from pathlib import Path

import pytest

from modules.belt_drive.design_models import DesignRequest
from modules.belt_drive.nominal_design import size_drive,NominalSizingOptions,report_to_dict
from modules.belt_drive.preferred_sizes import preferred_sizes
from modules.belt_drive.design_serialization import (DesignProject,project_dumps,project_loads,
    project_to_dict,project_from_dict,recalculate_project)
from modules.belt_drive.controller import nominal_design_job


def spec(**changes):
    return DesignRequest(**(dict(power_kw=3.,input_rpm=1450.,target_rpm=725.,family='v',profile='A',
        diameter_min_mm=100.,diameter_max_mm=200.,rpm_error_max_percent=0.)|changes))


def independent_length(d1,d2,c):
    a=math.acos(abs(d2-d1)/(2*c))
    small,large=sorted((d1/2,d2/2))
    return 2*math.sqrt(c*c-(large-small)**2)+2*small*a+2*large*(math.pi-a)


def test_r40_nominal_series_and_decades_are_exact_not_stock_products():
    assert preferred_sizes(100,200)==(100.,106.,112.,118.,125.,132.,140.,150.,160.,170.,180.,190.,200.)
    assert preferred_sizes(1000,1120)==(1000.,1060.,1120.)
    assert preferred_sizes(.1,.125)==(.1,.106,.112,.118,.125)
    for low,high in ((0,1),(100,10),(.00001,1),(1,1e8)):
        with pytest.raises(ValueError):preferred_sizes(low,high)


def test_c_empty_still_sizes_an_open_v_drive_without_any_catalogue():
    report=size_drive(spec(),NominalSizingOptions(length_policy='required'))
    c,=report.candidates
    assert report.search_complete and c.result.center_mm==300.  # explicit D1+D2 starting rule.
    assert c.result.length_exact_mm==pytest.approx(independent_length(100,200,300),abs=2e-12)
    assert c.result.nominal_output_rpm==725. and c.result.input_power_kw==3.
    assert not c.catalog_product and not c.engineering_approved and not c.result.power_capacity_verified
    assert c.result.design_power_kw is None and c.result.shaft_forces is None
    assert any(i.code=='SECTION_AND_COUNT' and i.severity=='NOT_EVALUATED' for i in c.checks)


def test_screenshot_motor_case_returns_candidates_without_c_or_products():
    req=DesignRequest(3.,1450.,400.,family='v',profile='A',rpm_error_max_percent=1.)
    report=size_drive(req)
    assert report.candidates and report.search_complete
    for c in report.candidates:
        r=c.result
        assert abs(r.nominal_output_rpm-400)/400*100<=1.
        assert c.required_length_mm>0 and r.length_exact_mm>0 and r.center_mm>0
        assert r.ratio==pytest.approx(r.driven_reference_diameter_mm/r.driver_reference_diameter_mm)
        assert r.length_exact_mm==pytest.approx(independent_length(r.driver_reference_diameter_mm,r.driven_reference_diameter_mm,r.center_mm),abs=1e-8)


def test_fixed_exact_c_keeps_required_length_when_preferred_length_cannot_fit():
    c,=size_drive(spec(mode='fixed',center_target_mm=400.,center_tolerance_mm=0.)).candidates
    assert c.length_kind=='required' and c.result.center_mm==400.
    assert c.required_length_mm==pytest.approx(1277.4970744746527,abs=2e-12)
    assert c.result.length_exact_mm==c.required_length_mm


def test_preferred_length_resolves_c_instead_of_rounding_length_only():
    c,=size_drive(spec(mode='fixed',center_target_mm=400.,center_tolerance_mm=20.)).candidates
    assert c.length_kind=='preferred_r40' and c.result.selected_length_mm==1250.
    assert 380<=c.result.center_mm<=420 and c.result.center_mm!=400.
    assert c.required_length_mm==pytest.approx(1277.4970744746527)
    assert independent_length(100,200,c.result.center_mm)==pytest.approx(1250.,abs=1e-8)


def test_center_range_uses_midpoint_and_never_leaves_bounds():
    c,=size_drive(spec(mode='range',center_min_mm=350.,center_max_mm=450.)).candidates
    assert c.required_length_mm==pytest.approx(1277.4970744746527)
    assert 350<=c.result.center_mm<=450.
    with pytest.raises(ValueError,match='C üst sınırı 11 mm çok küçük'):
        size_drive(spec(mode='range',center_min_mm=1.,center_max_mm=11.))
    large=DesignRequest(3.,1450.,1450.,family='v',profile='A',diameter_min_mm=630.,diameter_max_mm=630.,
        mode='range',center_min_mm=300.,center_max_mm=700.,rpm_error_max_percent=0.)
    only,=size_drive(large).candidates
    assert 630.<only.result.center_mm<=700.  # skip the overlapping part of the requested interval.


@pytest.mark.parametrize('profile',['Z','A','B','C','D','SPZ','SPA','SPB','SPC'])
def test_every_supported_v_profile_can_be_sized_geometrically(profile):
    req=DesignRequest(3.,1450.,1450.,family='v',profile=profile,rpm_error_max_percent=0.,result_limit=3)
    report=size_drive(req)
    assert report.candidates and report.profile==profile
    assert all(c.result.driver_reference_diameter_mm==c.result.driven_reference_diameter_mm for c in report.candidates)
    assert all(not c.result.production_approved for c in report.candidates)


def test_timing_integer_pitch_length_is_not_claimed_as_a_stock_belt():
    req=DesignRequest(1.5,1500.,750.,family='timing',profile='HTD_5M',teeth_min=20,teeth_max=40,
        mode='fixed',center_target_mm=200.,center_tolerance_mm=5.,rpm_error_max_percent=0.)
    c,=size_drive(req).candidates
    assert c.length_kind=='integer_pitch' and c.result.selected_belt_teeth==110
    assert c.result.selected_length_mm==550. and c.result.ratio==2.
    assert c.result.center_mm==pytest.approx(199.3643856158,abs=1e-8)
    assert not c.catalog_product


def test_work_budget_cancel_and_impossible_ratio_report_their_scope():
    report=size_drive(spec(target_rpm=1.))
    assert report.search_complete and not report.candidates
    report=size_drive(spec(work_limit=1))
    assert not report.search_complete and report.pairs_visited==1
    stop=Event();stop.set()
    report=size_drive(spec(),stop=stop)
    assert report.cancelled and not report.search_complete and not report.candidates
    events=Queue();nominal_design_job(spec())(events,stop)
    kind,report=events.get_nowait()
    assert kind=='belt_nominal_cancelled' and report.cancelled


@pytest.mark.parametrize('changes',[dict(manufacturer='Gates'),dict(series_id='x'),dict(priority='capacity'),
    dict(priority='fewest_belts'),dict(system_width_max_mm=50.),dict(max_belts=2),
    dict(priority='balanced',weights=(('capacity',1.),))])
def test_unsupported_manufacturer_constraints_are_not_silently_approved(changes):
    with pytest.raises(ValueError):size_drive(spec(**changes))


def test_project_v3_without_catalogue_recalculates_and_preserves_selection():
    req=spec();options=NominalSizingOptions()
    report=size_drive(req,options);selected=(report.candidates[0].identifier,)
    project=DesignProject(req,None,None,selected,options)
    data=project_to_dict(project)
    assert data['version']==3 and data['catalog'] is None
    restored=project_loads(project_dumps(project))
    outcome,ids=recalculate_project(restored)
    assert outcome==report and ids==selected
    data['nominal_options']['extra']=True
    with pytest.raises(ValueError):project_from_dict(data)
    exported=report_to_dict(report,selected_ids=selected)
    assert len(exported['candidates'])==1 and exported['candidates'][0]['catalog_product'] is False
    json.dumps(exported,allow_nan=False)


def test_complete_nominal_api_is_still_stdlib_only():
    root=Path(__file__).resolve().parents[3]
    code='''
import sys
from modules.belt_drive.nominal_design import size_drive
from modules.belt_drive.design_models import DesignRequest
assert size_drive(DesignRequest(3,1450,400,family='v',rpm_error_max_percent=1)).candidates
assert not {'PySide6','OCP','win32com','numpy'} & sys.modules.keys()
'''
    result=subprocess.run([sys.executable,'-S','-c',code],cwd=root,capture_output=True,timeout=15)
    assert result.returncode==0,result.stderr
