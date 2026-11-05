"""Kayış–Kasnak page: inputs, invalid inputs, stale results, search, cancel, catalogues, projects."""

import json
import math
import threading

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QFileDialog

from gui_qt.app import MainWindow, create_application, MODULES
from modules.belt_drive import controller
from modules.belt_drive.catalog.importers import catalog_to_csv, load_catalog
from modules.belt_drive.design_search import search_drives
from modules.belt_drive.design_serialization import project_loads
from modules.belt_drive.ui_support import BUNDLED_CATALOGS

SYNTHETIC = next(path for key, _, path in BUNDLED_CATALOGS if key == 'synthetic')


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([]); w = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(w)
    w.resize(1600, 950); w.show(); yield w
    if w.jobs.busy:
        w.jobs.cancel(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=8000)
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.fixture
def page(window):
    window.navigate('belt_drive')
    return window.pages['belt_drive']


def wait(qtbot, page):
    qtbot.waitUntil(lambda: not page.jobs.busy and page.running is None, timeout=20000)


def use_synthetic(page):
    page.catalog_picker.setCurrentIndex(page.catalog_picker.findData('synthetic'))
    page.a_unverified.setChecked(True)
    page.a_service.setValue(1.2)        # without it, capacity stays NOT_EVALUATED (no automatic 1.0)


def test_menu_entry_and_reference_v_design(page):
    assert ('belt_drive', 'Kayış–Kasnak Tasarımı', 'MAKİNE ELEMANLARI') in MODULES
    r = page.manual_result
    assert r is not None and r.ratio == pytest.approx(2.) and r.length_exact_mm == pytest.approx(1277.4970744746527)
    values = {page.result_table.item(i, 0).text(): page.result_table.item(i, 1).text() for i in range(page.result_table.rowCount())}
    assert values['İdeal çıkış devri n₂ (kayma hariç)'] == '725'
    assert values['Etkin kuvvet farkı Ft = F₁ − F₂'] == '658,57'
    assert values['Tasarım gücü P·K'] == 'değerlendirilmedi'          # no service factor: no hidden 1.0
    assert values['Mil bileşke kuvveti'].startswith('değerlendirilmedi')
    assert ('POWER_CAPACITY', 'NOT_EVALUATED') in page.check_codes
    assert 'Değerlendirilmedi' in page.check_table.toPlainText() and 'Başarılı' not in page.check_table.toPlainText()


def test_timing_torque_length_mode_and_optional_factors(page, qtbot):
    page.family.setCurrentIndex(page.family.findData('timing'))
    page.profile.setCurrentIndex(page.profile.findData('HTD_5M'))
    page.z1.setValue(20); page.z2.setValue(40)
    page.load_mode.setCurrentIndex(1); page.torque.setValue(10.)
    page.center_mode.setCurrentIndex(1); page.belt_teeth.setValue(110)
    page.efficiency.setValue(.95); page.service.setValue(1.4)
    page.calculate_manual()
    spec = page.manual_result.specification
    assert spec.driver.datum_diameter_mm is None and spec.driver.teeth == 20     # timing never sends a datum diameter
    assert spec.load.power_kw is None and spec.load.torque_nm == 10.            # only one primary load
    assert page.manual_result.selected_length_mm == pytest.approx(550.)
    assert page.manual_result.design_power_kw == pytest.approx(page.manual_result.input_power_kw * 1.4)
    assert page.manual_result.efficiency_output_power_kw == pytest.approx(page.manual_result.input_power_kw * .95)
    assert not page.length.isVisible() and page.belt_teeth.isVisible()


def test_invalid_input_and_stale_results_are_cleared_immediately(page):
    assert page.manual_result is not None
    page.distance.setValue(100.)                       # 100 mm < (100+200)/2 → discs overlap
    assert page.manual_result is None and page.canvas.result is None   # invalidated before recomputation
    assert page.manual_status.text().startswith('Girdiler değişti')
    page.calculate_manual()
    assert page.manual_result is None and ('GEOMETRY_OR_LOAD', 'ERROR') in page.check_codes
    page.distance.setValue(400.); page.calculate_manual()
    assert page.manual_result is not None


def test_canvas_draws_the_belt_path_and_nominal_kinematics(page):
    page.rotation.setCurrentIndex(page.rotation.findData('ccw')); page.calculate_manual()
    canvas = page.canvas; r = page.manual_result
    assert canvas.result is r and len(r.geometry.segments) == 4
    distance, a1, a2 = canvas.kinematic_state(1.)
    assert a1 > 0 and a2 > 0 and distance < 0                       # CCW driver: same direction, belt backwards
    assert a1 / a2 == pytest.approx(r.ratio)                         # ω₁/ω₂ = i
    assert -distance == pytest.approx(a1 * r.geometry.driver_radius_mm)
    page.animate.setChecked(True); assert canvas.animating
    canvas.grab()
    page.rotation.setCurrentIndex(page.rotation.findData('cw')); page.calculate_manual()
    assert canvas.kinematic_state(1.)[1] < 0


def test_automatic_search_select_transfer_and_compare(page, qtbot):
    use_synthetic(page)
    page.start_search(); wait(qtbot, page)
    assert page.report is not None and page.report.search_complete and page.candidates.rowCount() == 2
    assert 'Geçici' in page.candidates.item(0, 7).text()          # PROVISIONAL is never "verified"
    page.candidates.selectRow(0)
    c = page.selected_candidate()
    assert c is not None and page.auto_canvas.result is c.result
    assert 'mühendislik onayı yok' in page.candidate_details.toPlainText()
    assert 'emniyet katsayısı değildir' in page.candidate_details.toPlainText()
    page.add_to_compare(); assert page.compare.rowCount() == 1
    page.transfer_to_manual()
    assert page.tabs.currentIndex() == 0 and page.manual_result.center_mm == pytest.approx(c.result.center_mm)
    assert page.manual_result.specification == c.result.specification
    # Changing a request input voids the search, the selection and the comparison.
    page.a_target.setValue(710.)
    assert page.report is None and page.candidates.rowCount() == 0 and page.compare.rowCount() == 0
    assert not page.to_manual.isEnabled()


def test_unverified_candidates_are_hidden_by_default(page, qtbot):
    page.catalog_picker.setCurrentIndex(page.catalog_picker.findData('synthetic'))
    assert not page.a_unverified.isChecked()
    page.start_search(); wait(qtbot, page)
    assert page.candidates.rowCount() == 0 and page.report.unverified_count == 2
    assert 'gizli' in page.coverage.text()


def test_pulley_pairs_are_partial_and_show_no_belt_or_center(page, qtbot):
    page.catalog_picker.setCurrentIndex(page.catalog_picker.findData('tosyali'))
    page.a_rpm_error.setValue(2.)
    page.start_pairs(); wait(qtbot, page)
    assert page.pairs is not None and page.pairs.matching_count == 32
    assert page.pair_table.item(0, 0).text() == 'T 12-AT5-16F-AL' and page.pair_table.item(0, 1).text() == 'T 25-AT5-16F-AL'
    headers = [page.pair_table.horizontalHeaderItem(i).text() for i in range(page.pair_table.columnCount())]
    assert not any('Kayış' in h or 'C ·' in h or 'Kapasite' in h for h in headers)
    assert 'tam aktarım değildir' in page.coverage.text().casefold()
    assert page.auto_canvas.result is None and page.selected_candidate() is None
    # The full search on this catalogue finds no complete drive (no belts, no ratings).
    page.start_search(); wait(qtbot, page)
    assert page.report.unverified_count == 0 and page.report.capacity_verified_count == 0


def test_search_cancel_is_reported_as_incomplete(page, qtbot, monkeypatch):
    def slow_job(request, catalog):
        def run(events, stop):
            stop.wait(5)
            events.put(('belt_design_cancelled', search_drives(request, catalog, stop=stop)))
        return run
    monkeypatch.setattr(controller, 'automatic_design_job', slow_job)
    use_synthetic(page)
    page.start_search(); assert page.jobs.busy
    page.jobs.cancel(); wait(qtbot, page)
    assert page.report.cancelled and not page.report.search_complete
    assert 'iptal' in page.coverage.text()


def test_result_arriving_after_an_input_change_is_discarded(page, qtbot, monkeypatch):
    gate = threading.Event()
    def gated_job(request, catalog):
        def run(events, stop):
            gate.wait(5)
            events.put(('belt_design_result', search_drives(request, catalog)))
        return run
    monkeypatch.setattr(controller, 'automatic_design_job', gated_job)
    use_synthetic(page)
    page.start_search()
    page.search_token += 1          # simulates an input change while the worker runs (inputs are locked in the UI)
    gate.set(); wait(qtbot, page)
    assert page.report is None and 'sonuç gösterilmedi' in page.coverage.text()


def test_job_error_shows_no_result(page, qtbot, monkeypatch):
    def broken(request, catalog):
        def run(events, stop):
            raise RuntimeError('deneme hatası')
        return run
    monkeypatch.setattr(controller, 'automatic_design_job', broken)
    use_synthetic(page); page.start_search(); wait(qtbot, page)
    assert page.report is None and 'deneme hatası' in page.status_text


def test_catalog_files_and_self_declared_official_status(page, tmp_path, monkeypatch):
    data = json.loads(SYNTHETIC.read_text(encoding='utf-8'))
    data['sources'][0]['verification_status'] = 'OFFICIAL_VERIFIED'
    path = tmp_path / 'claimed.json'; path.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(path), ''))
    page.open_catalog()
    assert page.catalog.identifier == 'synthetic-timing'
    assert page.sources.item(0, 4).text().startswith('Resmî') and page.sources.item(0, 5).text() == 'Kullanıcı tarafından sağlanan'
    csv_catalog = load_catalog(SYNTHETIC); csv_catalog = type(csv_catalog)(csv_catalog.identifier, csv_catalog.revision,
                                                                          csv_catalog.sources, csv_catalog.belts, csv_catalog.pulleys)
    csv_path = tmp_path / 'products.csv'; csv_path.write_text(catalog_to_csv(csv_catalog), encoding='utf-8')
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(csv_path), ''))
    page.open_catalog()
    assert len(page.catalog.pulleys) == 2 and page.products.rowCount() == 4
    bad = tmp_path / 'bad.json'; bad.write_text('{"schema": 1}', encoding='utf-8')
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(bad), ''))
    page.open_catalog()
    assert 'okunamadı' in page.status_text and page.catalog.identifier == 'products'


def test_tosyali_audit_counts_are_shown(page):
    page.catalog_picker.setCurrentIndex(page.catalog_picker.findData('tosyali'))
    assert len(page.catalog.pulleys) == 342 and page.quarantine.rowCount() == 146
    text = page.audit_summary.text()
    assert '342 kabul' in text and '146 karantina' in text and '34 burçlu' in text
    page.product_filter.setText('T 12-AT5-16F-AL')
    row = [page.products.item(0, c).text() for c in range(page.products.columnCount())]
    assert row[1] == 'T 12-AT5-16F-AL' and row[6] == '16'                 # nominal belt width separate from F/L/bore
    assert row[7] != row[8] and row[9] != row[6]


def test_project_save_open_recalculates_and_v1_projects_open(page, qtbot, tmp_path, monkeypatch):
    use_synthetic(page); page.start_search(); wait(qtbot, page)
    page.candidates.selectRow(1); page.add_to_compare()
    selected = list(page.compare_ids)
    target = tmp_path / 'project.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    page.save_project()
    project = project_loads(target.read_bytes())
    assert project.request is not None and project.manual is not None and project.selected_ids == tuple(selected)
    # Comparison export uses the backend's selected-candidate contract.
    comparison = tmp_path / 'compare.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(comparison), ''))
    page.save_comparison()
    data = json.loads(comparison.read_text(encoding='utf-8'))
    assert data['schema'] == 'gokworks.belt_drive.automatic_result' and [c['identifier'] for c in data['unverified']] == selected
    # Reopen: inputs come back, results are recomputed, not read from the file.
    page.a_target.setValue(650.)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(target), ''))
    page.open_project(); wait(qtbot, page)
    assert page.a_target.value() == pytest.approx(700.) and page.report is not None and page.compare_ids == selected
    # Old stage-1 v1 project.
    v1 = tmp_path / 'v1.json'
    v1.write_text((SYNTHETIC.parent / 'reference_v.json').read_text(encoding='utf-8'), encoding='utf-8')
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(v1), ''))
    page.family.setCurrentIndex(page.family.findData('timing'))
    page.open_project(); wait(qtbot, page)
    assert page.family.currentData() == 'v' and page.manual_result.length_exact_mm == pytest.approx(1277.4970744746527)
    broken = tmp_path / 'broken.json'; broken.write_text('{"version": 2}', encoding='utf-8')
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(broken), ''))
    page.open_project()
    assert 'açılamadı' in page.status_text


def test_invalid_request_is_reported_without_a_job(page):
    use_synthetic(page)
    page.a_mode.setCurrentIndex(page.a_mode.findData('range'))     # range without C min/max
    page.start_search()
    assert not page.jobs.busy and 'İstek geçersiz' in page.status_text


def test_default_general_v_sizing_works_with_no_c_and_no_catalog(page,qtbot):
    assert page.nominal_mode() and page.a_family.currentData()=='v'
    page.catalog=None
    page.a_power.setValue(3.);page.a_rpm.setValue(1450.);page.a_target.setValue(400.)
    page.a_target_c.setValue(0.)
    page.start_search();wait(qtbot,page)
    assert page.report is not None and page.report.search_complete and page.candidates.rowCount()>0
    candidate=page.selected_candidate()
    assert candidate is not None and not candidate.catalog_product
    assert candidate.result.specification.belt.family=='v' and math.isfinite(candidate.result.length_exact_mm)
    assert candidate.result.length_exact_mm>0 and candidate.rpm_error_percent<=1.
    assert 'C belirtilmedi' in page.coverage.text() and 'ürün kodu aranmadı' in page.coverage.text()
    assert 'Ld' in page.candidates.item(0,2).text() and 'mm' in page.candidates.item(0,2).text()
    assert 'gerekli teorik boy' in page.candidate_details.toPlainText()
    assert page.auto_canvas.result is candidate.result
    page.add_to_compare();assert page.compare.rowCount()==1
    page.transfer_to_manual();assert page.manual_result is not None
    assert page.manual_result.length_exact_mm==pytest.approx(candidate.result.length_exact_mm,abs=1e-7)
    page.a_target.setValue(410.)
    assert page.report is None and page.compare.rowCount()==0 and not page.to_manual.isEnabled()


def test_impossible_c_range_has_visible_actionable_error(page,qtbot):
    page.a_mode.setCurrentIndex(page.a_mode.findData('range'))
    page.a_cmin.setValue(1.);page.a_cmax.setValue(11.)
    page.start_search();wait(qtbot,page)
    assert page.report is None and page.candidates.rowCount()==0
    assert 'C üst sınırı 11 mm çok küçük' in page.coverage.text()
    page.a_mode.setCurrentIndex(page.a_mode.findData('auto'));page.a_target_c.setValue(0.)
    page.start_search();wait(qtbot,page)
    assert page.report is not None and page.candidates.rowCount()>0


def test_general_sizing_never_depends_on_hidden_unverified_filter(page,qtbot):
    assert not page.a_unverified.isChecked() and not page.a_unverified.isEnabled()
    page.start_search();wait(qtbot,page)
    assert page.candidates.rowCount()>0 and 'gizli' not in page.coverage.text()
    page.a_family.setCurrentIndex(page.a_family.findData('timing'))
    page.start_search();wait(qtbot,page)
    assert page.report is not None and page.candidates.rowCount()>0
    assert all(c.result.specification.belt.family=='timing' for c in page.report.candidates)
    assert 'Lp' in page.candidates.item(0,2).text()


def test_nominal_project_v3_restores_general_method_without_a_catalog(page,qtbot,tmp_path,monkeypatch):
    page.a_target_c.setValue(0.)
    page.start_search();wait(qtbot,page)
    page.add_to_compare();selected=list(page.compare_ids)
    path=tmp_path/'general.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(path),''))
    page.save_project()
    data=json.loads(path.read_text(encoding='utf-8'))
    assert data['version']==3 and data['catalog'] is None and data['request']['center_target_mm'] is None
    page.use_catalog_mode()
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''))
    page.open_project();wait(qtbot,page)
    assert page.nominal_mode() and page.report is not None and page.compare_ids==selected
    assert page.a_family.currentData()=='v' and page.a_target_c.value()==0.
    comparison=tmp_path/'comparison.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(comparison),''))
    page.save_comparison()
    output=json.loads(comparison.read_text(encoding='utf-8'))
    assert output['schema']=='gokworks.belt_drive.nominal_result' and len(output['candidates'])==1


def test_numeric_formatter_preserves_integer_trailing_zeros():
    from modules.belt_drive.ui_support import number
    assert number(1450.,0)=='1450' and number(100000.,0)=='100000' and number(1.5,2)=='1,5'


@pytest.mark.parametrize('size', [(1024, 700), (1366, 768), (1920, 1080)])
@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_layouts_and_themes(window, page, size, theme):
    window.set_theme(theme); window.resize(*size)
    QCoreApplication.processEvents()
    assert page.width() >= 550
    for index in range(page.tabs.count()):
        page.tabs.setCurrentIndex(index); QCoreApplication.processEvents()
        assert not page.grab().isNull()
    compact = page.manual_workspace.compact_mode
    assert compact == (page.manual_workspace.width() < page.manual_workspace.threshold)
    assert page.canvas.appearance == theme
