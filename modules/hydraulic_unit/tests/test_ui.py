"""Hidrolik ünite arayüzü: çekirdek sonuçlarını gösterir, hatalı girdiyi işaretler, rapor işlerini yönetir."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from gui_qt.app import create_application
from gui_qt.settings import SettingsStore
from gui_qt.workers import JobManager
from modules.hydraulic_unit import serialization
from modules.hydraulic_unit.core.catalogs import DEBOUNCE_MS
from modules.hydraulic_unit.service import calculate_project
from modules.hydraulic_unit.ui import CYL_COLUMNS, HydraulicPage

EXAMPLE = Path(__file__).resolve().parents[3] / 'examples' / 'ornek_pres_unitesi.gwhyd'


@pytest.fixture
def page(qtbot, tmp_path):
    create_application([])
    context = SimpleNamespace(settings=SettingsStore(tmp_path / 'settings.json'), jobs=JobManager(), appearance='dark')
    page = HydraulicPage(context); qtbot.addWidget(page); page.resize(1400, 900); page.show(); qtbot.wait(10)
    page.open_detailed()  # mevcut ayrıntılı ekran regresyonları; kolay giriş ayrı test edilir
    yield page
    page.cancel_pdf(); page.settings.flush()


@pytest.fixture
def example(page):
    page.load_path(EXAMPLE)
    assert page.result is not None
    return page


def test_seven_tabs_and_default_project_is_calculated(page):
    assert [page.tabs.tabText(i) for i in range(page.tabs.count())] == [
        'Silindirler', 'Çevrim', 'Pompa / motor', 'Hat / yağ', 'Tank / ısı',
        'Akümülatör', 'Rapor']
    assert page.result is not None and page.summary_table.rowCount() > 0
    assert page.excel_button.isEnabled() and page.json_button.isEnabled() and page.pdf_button.isEnabled()


def test_example_matches_core_result_and_keeps_core_flags(example):
    expected = calculate_project(serialization.load(EXAMPLE))
    assert example.result.input_fingerprint == expected.input_fingerprint
    assert example.result.cycle['max_pressure'] == expected.cycle['max_pressure']
    assert example.rows_table.rowCount() > 10
    assert any(example.rows_table.item(r, 0).toolTip() for r in range(example.rows_table.rowCount()))   # formulas
    assert example.phase_results.rowCount() == len(example.project.phases)
    assert example.issue_list.count() == len(expected.issues)
    assert example.assumptions.text()


def test_charts_are_step_series_over_the_cycle(example):
    phases = example.result.cycle['phases']
    for key, chart in example.charts.items():
        assert len(chart.points) == len(phases), key
    assert sum(d for d, _ in example.charts['pressure'].points) == pytest.approx(example.result.cycle['duration'], rel=1e-6)


def test_invalid_field_is_marked_and_results_and_reports_are_cleared(page, qtbot):
    widget = page.fields['pump.displacement'][0]
    widget.setText('abc'); widget.textEdited.emit('abc')
    assert page.timer.isActive() and page.timer.interval() == DEBOUNCE_MS
    assert page.result is None and not page.pdf_button.isEnabled()  # debounce sırasında eski sonuç yayımlanmaz
    qtbot.waitUntil(lambda: widget.property('invalid') is True, timeout=2000)
    assert widget.property('invalid') is True and widget.toolTip()
    assert page.summary_table.rowCount() == 0 and page.rows_table.rowCount() == 0 and page.issue_list.count() == 0
    assert not page.excel_button.isEnabled() and not page.json_button.isEnabled() and not page.pdf_button.isEnabled()
    assert not page.save_button.isEnabled()
    widget.setText('20'); page.recalculate()
    assert page.result is not None and not widget.property('invalid') and page.pdf_button.isEnabled()


def test_cylinder_error_marks_its_row(page):
    names = [c[0] for c in CYL_COLUMNS]; column, bore = names.index('rod'), names.index('bore')
    page.cylinder_table.item(0, column).setText(page.cylinder_table.item(0, bore).text())   # rod == bore
    page.recalculate()
    assert page.result is None
    assert any(page.cylinder_table.item(0, c) and page.cylinder_table.item(0, c).toolTip()
               for c in range(page.cylinder_table.columnCount()))


def test_debounce_coalesces_edits(page, qtbot, monkeypatch):
    calls = []; original = page.recalculate
    monkeypatch.setattr(page, 'recalculate', lambda: (calls.append(1), original()))
    page.timer.timeout.disconnect(); page.timer.timeout.connect(page.recalculate)
    for text in ('Pres', 'Pres 1', 'Pres 12'):
        page.name.setText(text); page.name.textEdited.emit(text)
    qtbot.wait(DEBOUNCE_MS + 150)
    assert len(calls) == 1 and page.project.name == 'Pres 12'


def test_phase_add_copy_move_and_remove(example):
    count = len(example.project.phases)
    example.phase_table.selectRow(0); example.add_phase(copy=True)
    assert len(example.project.phases) == count + 1 and example.project.phases[1].name.endswith('(kopya)')
    example.phase_table.selectRow(1); example.move_phase(1)
    assert example.project.phases[2].name.endswith('(kopya)')
    example.phase_table.selectRow(2); example.remove_phase()
    assert len(example.project.phases) == count and example.result is not None
    assert example.phase_table.rowCount() == count


def test_cylinder_add_and_remove(example):
    count = len(example.project.cylinders)
    example.add_cylinder()
    assert len(example.project.cylinders) == count + 1 and example.cylinder_table.rowCount() == count + 1
    example.cylinder_table.selectRow(count); example.remove_cylinder()
    assert len(example.project.cylinders) == count


def test_save_and_load_roundtrip(example, tmp_path, monkeypatch):
    target = tmp_path / 'kayit'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    example.save_project()
    saved = tmp_path / 'kayit.gwhyd'
    assert saved.is_file() and serialization.load(saved) == example.project
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(saved), ''))
    example.open_project()
    assert example.project == serialization.load(saved) and example.result is not None


def test_json_export_runs_as_a_job(example, tmp_path, monkeypatch, qtbot):
    target = tmp_path / 'rapor.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    example.export('json')
    qtbot.waitUntil(lambda: not example.jobs.busy and target.is_file(), timeout=5000)
    assert json.loads(target.read_text(encoding='utf-8'))


def test_pdf_job_can_be_cancelled_and_leaves_no_file(example, tmp_path, monkeypatch, qtbot):
    target = tmp_path / 'rapor.pdf'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    example.export_pdf()
    assert example.pdf_job is not None and not example.pdf_button.isEnabled()
    example.cancel_pdf()
    assert example.pdf_job is None and example.pdf_button.isEnabled() and not target.exists()


def test_pdf_job_finishes(example, tmp_path, monkeypatch, qtbot):
    target = tmp_path / 'rapor.pdf'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    example.export_pdf()
    qtbot.waitUntil(lambda: example.pdf_job is None, timeout=30000)
    assert target.is_file() and target.stat().st_size > 0


def test_display_units_change_only_the_result_table(example):
    metric = [example.rows_table.item(r, 2).text() for r in range(example.rows_table.rowCount())]
    pressure = example.result.cycle['max_pressure']
    example.units.setCurrentIndex(example.units.findData('us')); example.recalculate()
    us = [example.rows_table.item(r, 2).text() for r in range(example.rows_table.rowCount())]
    assert metric != us and example.result.cycle['max_pressure'] == pressure


def test_theme_change_redraws_without_losing_result(example):
    example.context.appearance = 'light'; example.theme_changed()
    assert all(chart.appearance == 'light' for chart in example.charts.values()) and example.result is not None


def test_project_is_restored_from_settings(page, qtbot, tmp_path):
    page.load_path(EXAMPLE); page.settings.flush()
    again = HydraulicPage(page.context); qtbot.addWidget(again)
    assert again.project == page.project


def test_page_opens_from_main_window(qtbot, tmp_path, monkeypatch):
    from gui_qt.app import MainWindow, PAGE_TYPES
    assert PAGE_TYPES['hydraulic_unit'] == ('modules.hydraulic_unit.ui', 'HydraulicPage')
    create_application([])
    window = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(window)
    window.navigate('hydraulic_unit')
    assert isinstance(window.pages['hydraulic_unit'], HydraulicPage)


def test_step_help_and_next_previous_buttons(page,qtbot):
    from PySide6.QtCore import Qt
    assert '1/7' in page.step_title.text() and 'Piston' in page.step_help.text()
    assert not page.previous_button.isEnabled()
    qtbot.mouseClick(page.next_button,Qt.LeftButton)
    assert page.tabs.currentIndex() == 1 and '2/7' in page.step_title.text()
    assert 'Her satır' in page.step_help.text()
    page.tabs.setCurrentIndex(6)
    assert not page.next_button.isEnabled() and 'PDF' in page.step_help.text()


def test_advanced_settings_preserve_values_and_reveal_invalid_field(page):
    original = page.project
    assert not page.advanced_sections['pump'].is_expanded()
    assert page.cylinder_table.isColumnHidden(5)
    page.cylinder_advanced.setChecked(True)
    assert not page.cylinder_table.isColumnHidden(5)
    page.fields['pump.volumetric_efficiency'][0].setText('2')
    page.recalculate()
    assert page.result is None and page.advanced_sections['pump'].is_expanded()
    page.fields['pump.volumetric_efficiency'][0].setText('0,95'); page.recalculate()
    assert page.project == original


def test_optional_accumulator_fields_are_disabled_and_ignored_until_enabled(page):
    enabled = page.fields['accumulator.enabled'][0]
    field = page.fields['accumulator.minimum_pressure'][0]
    assert not field.isEnabled()
    field.setText(''); page.recalculate()
    assert page.result is not None
    enabled.setChecked(True); page.recalculate()
    assert field.isEnabled() and page.result is None and field.property('invalid')


def test_unused_pump_control_fields_do_not_block_a_fixed_pump(page):
    for key in ('pump.compensator_pressure','pump.power_limit'):
        widget = page.fields[key][0]
        assert not widget.isEnabled()
        widget.setText('')
    page.recalculate()
    assert page.result is not None


def test_accumulator_results_are_named_in_turkish_and_converted_to_litres_and_bar(page):
    page.fields['accumulator.enabled'][0].setChecked(True); page.recalculate()
    actual = page.result.accumulator
    assert page.accumulator_table.item(0,0).text() == 'Gerekli gaz hacmi · L'
    assert float(page.accumulator_table.item(0,1).text().replace(',','.')) == pytest.approx(actual['required_volume']*1000,abs=.001)
    assert float(page.accumulator_table.item(3,1).text().replace(',','.')) == pytest.approx(100.)


def test_warning_navigation_does_not_mark_valid_inputs_as_invalid(page):
    from PySide6.QtCore import Qt
    item = next(page.issue_list.item(i) for i in range(page.issue_list.count())
                if page.issue_list.item(i).data(Qt.UserRole) == 'thermal')
    assert '→' in item.text()
    page.focus_issue(item)
    assert page.tabs.currentIndex() == 4 and not page.invalid_widgets


def test_fix_button_takes_user_to_invalid_input(page):
    widget = page.fields['pump.displacement'][0]
    widget.setText('bad'); page.recalculate()
    assert page.fix_button.isVisible()
    page.focus_first_problem()
    assert page.tabs.currentIndex() == 2 and widget.hasFocus()


def test_phase_time_mode_clears_speed_and_uses_core_inverse_time_calculation(page):
    from modules.hydraulic_unit.ui import PHASE_COLUMNS
    names = [c[0] for c in PHASE_COLUMNS]
    page.phase_table.selectRow(0)
    page.phase_input_method.setCurrentIndex(page.phase_input_method.findData('duration'))
    assert page.phase_table.item(0,names.index('speed')).text() == ''
    page.phase_table.item(0,names.index('duration')).setText('5')
    page.recalculate()
    assert page.result is not None
    assert page.result.cycle['phases'][0].speed == pytest.approx(.25/5)


def test_switching_to_hold_removes_hidden_speed_requirement(page):
    from modules.hydraulic_unit.ui import PHASE_COLUMNS
    names = [c[0] for c in PHASE_COLUMNS]
    page.phase_table.selectRow(0)
    combo = page.phase_table.cellWidget(0,names.index('kind'))
    combo.setCurrentIndex(combo.findData('hold'))
    assert not page.phase_input_method.isEnabled()
    assert page.phase_table.item(0,names.index('speed')).text() == ''
    assert not page.phase_table.item(0,names.index('stroke')).flags() & Qt.ItemIsEditable


def test_table_commands_never_discard_unfinished_invalid_input(page):
    from modules.hydraulic_unit.ui import PHASE_COLUMNS
    col = [c[0] for c in PHASE_COLUMNS].index('force')
    page.phase_table.item(0,col).setText('yanlış')
    count = page.phase_table.rowCount()
    page.add_phase()
    assert page.phase_table.rowCount() == count
    assert page.phase_table.item(0,col).text() == 'yanlış'
    assert page.result is None


def test_narrow_window_stacks_forms_without_cutting_numeric_inputs(page,qtbot):
    from PySide6.QtWidgets import QBoxLayout
    page.resize(800,700); page.tabs.setCurrentIndex(2)
    qtbot.waitUntil(lambda: page.tabs.widget(2).widget().columns.direction() == QBoxLayout.TopToBottom)
    assert page.fields['pump.angular_speed'][0].width() >= 100
    assert page.fields['pump.angular_speed'][0].text() == '1450'


def test_unused_hold_stroke_does_not_block_calculation(page):
    from dataclasses import replace
    from modules.hydraulic_unit.core.models import Phase
    from modules.hydraulic_unit.ui import PHASE_COLUMNS
    page.project = replace(page.project,phases=(Phase(kind='hold',speed=None,duration=3.),))
    page.populate()
    page.phase_table.item(0,[c[0] for c in PHASE_COLUMNS].index('stroke')).setText('kullanılmıyor')
    page.recalculate()
    assert page.result is not None
