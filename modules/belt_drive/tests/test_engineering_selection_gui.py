"""Engineering limits persist in the form and invalidate stale selections."""
from dataclasses import replace
import pytest

from .test_belt_gui import page as page, window as window
from .design_fixtures import request
from modules.belt_drive.nominal_design import NominalSizingOptions, size_drive


def test_operating_limits_roundtrip_through_the_form_and_invalidate_results(page):
    req = request(profile='HTD_5M', minimum_wrap_deg=150., maximum_belt_speed_m_s=20., minimum_engaged_teeth=6.)
    page.load_request(req, None, NominalSizingOptions(teeth_min=20, teeth_max=40))
    assert page.design_request() == req
    page.request = req
    page.report = size_drive(req, NominalSizingOptions(teeth_min=20, teeth_max=40))
    page.a_speed_limit.setValue(15.)
    assert page.report is None
    assert page.design_request() == replace(req, maximum_belt_speed_m_s=15.)


def test_hidden_timing_constraint_is_never_applied_to_a_v_belt(page):
    req = request(profile='HTD_5M', minimum_engaged_teeth=6.)
    page.load_request(req, None, NominalSizingOptions())
    page.a_family.setCurrentIndex(page.a_family.findData('v'))
    assert page.design_request().minimum_engaged_teeth is None
    page.a_family.setCurrentIndex(page.a_family.findData('timing'))
    assert page.design_request().minimum_engaged_teeth == 6.


@pytest.mark.parametrize('changes',[dict(minimum_wrap_deg=150.1234),dict(maximum_belt_speed_m_s=1001.)])
def test_loaded_limits_cannot_silently_change_precision_or_range(page,changes):
    req=request(profile='HTD_5M',**changes)
    assert page.load_request(req,None,NominalSizingOptions()) is False
    assert page.report is None and 'Sınırlar ekrana aktarılırken değişti' in page.status_text
