"""Production controls use real engine DTOs and the existing background job manager."""
from modules.sheet_unfolding.tests.test_unfold_gui import window,page,settle  # noqa: F401


def test_forming_panel_changes_real_calculation_and_saved_request(page,qtbot):
    page.choose_shape('bent_profile','single')
    page.forming.enabled.setChecked(True);page.forming.edits['k_factor'].setText('0,4')
    settle(qtbot,page)
    assert page.result['forming_report']['all_compensated']
    assert 'Telafili açınım' in page.forming_results.toPlainText()
    assert any(e['layer']=='nominal' for e in page.result['parts'][0]['geometry_2d']['entities'])
    request=page.build_request();page.load_request(request)
    assert page.build_request()['forming_options']==request['forming_options']
    page.export_development.setCurrentIndex(page.export_development.findData('compensated'))
    assert page.export_buttons['dxf'].isEnabled() is False  # reloading correctly marks results stale
    settle(qtbot,page)
    assert page.export_buttons['dxf'].isEnabled()
    assert not page.export_buttons['step'].isEnabled()


def test_invalid_mechanical_data_blocks_request_and_preserves_visible_result(page,qtbot):
    page.forming.enabled.setChecked(True);page.forming.edits['k_factor'].setText('nan')
    assert page.build_request() is None
    assert 'Üretim verisi' in page.forming.error.text()
    assert not page.export_buttons['dxf'].isEnabled()
    page.forming.enabled.setChecked(False);settle(qtbot,page)
    assert not page.result['forming_report']


def test_material_grade_does_not_guess_physical_constants(page):
    page.forming.enabled.setChecked(True);page.forming.grade.setCurrentText('DC01');page.forming.edits['k_factor'].setText('.4')
    o=page.forming.options()
    assert o['material']['grade']=='DC01' and o['material']['young_modulus_mpa'] is None
    assert o['material']['yield_strength_mpa'] is None


def test_advanced_json_rejects_duplicate_fields_and_shadowing_visible_controls(page):
    import pytest
    page.forming.enabled.setChecked(True);page.forming.edits['k_factor'].setText('.4')
    for data in ('{"relax_mesh":false,"relax_mesh":true}','{"process":"coining"}','{"material":{"grade":"DC01"}}'):
        page.forming.extra.setPlainText(data)
        with pytest.raises(ValueError):page.forming.options()
