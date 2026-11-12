"""The real-source method reaches the UI, saved project and manual count."""
from dataclasses import replace

from .test_belt_gui import page as page, window as window, wait
from .test_tosyali_v_design import req, OPTIONS
from modules.belt_drive.nominal_design import size_drive


def test_tosyali_method_lists_only_real_narrow_sections_and_requires_service(page,qtbot):
    page.a_basis.setCurrentIndex(page.a_basis.findData('tosyali'))
    assert not page.a_family.isEnabled() and page.a_family.currentData()=='v'
    assert {page.a_profile.itemData(i) for i in range(page.a_profile.count())}=={None,'SPZ','SPA','SPB','SPC'}
    assert '708' in page.auto_catalog_label.text()
    page.a_service.setValue(0.)
    page.start_search()
    assert 'servis faktör' in page.status_text.lower()
    assert not page.jobs.busy


def test_tosyali_job_results_count_formula_manual_transfer_and_stale_state(page,qtbot):
    request=req(profile='SPA',power_kw=3.,max_belts=2,outside_diameter_max_mm=500.)
    assert page.load_request(request,None,OPTIONS)
    assert page.tosyali_mode() and page.design_request()==request
    assert page.current_nominal_options()==OPTIONS
    page.start_search();wait(qtbot,page)
    assert page.report and page.report.candidates
    assert 'Tosyalı' in page.coverage.text() and 'Genel boyutlandırma' not in page.coverage.text()
    c=page.selected_candidate()
    assert c and page.candidates.item(0,0).text().startswith('T SPA')
    assert 'kanal' in page.amount(c)
    details=page.candidate_details.toPlainText()
    assert 'tavan(' in details and 'Optibelt SK' in details and 'seçilen' in details
    page.transfer_to_manual()
    assert page.manual_result.specification.belt.count==c.belt_count
    assert 'Adet/kapasite güçten seçilmedi' not in page.status_text
    page.tabs.setCurrentIndex(1);page.a_belts.setValue(1)
    assert page.report is None


def test_tosyali_fewest_belts_project_state_and_switch_back_to_generic(page):
    request=req(profile='SPB',priority='fewest_belts',max_belts=8)
    assert page.load_request(request,None,replace(OPTIONS,length_policy='required'))
    assert page.design_request()==request
    assert page.a_priority.currentData()=='fewest_belts'
    report=size_drive(request,page.current_nominal_options())
    page.show_nominal_report(report)
    assert page.report.candidates
    page.a_basis.setCurrentIndex(page.a_basis.findData('nominal'))
    assert page.report is None and page.a_priority.currentData() not in ('capacity','fewest_belts')
    assert page.current_nominal_options().pulley_source=='nominal'
    assert page.a_family.isEnabled()
