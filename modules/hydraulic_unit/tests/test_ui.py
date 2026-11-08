"""Hidrolik ünite arayüzü: çekirdek sonuçlarını gösterir, hatalı girdiyi işaretler, rapor işlerini yönetir."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
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
    yield page
    page.cancel_pdf(); page.settings.flush()


@pytest.fixture
def example(page):
    page.load_path(EXAMPLE)
    assert page.result is not None
    return page


def test_seven_tabs_and_default_project_is_calculated(page):
    assert [page.tabs.tabText(i) for i in range(page.tabs.count())] == [
        '1 · Silindirler', '2 · Çevrim', '3 · Pompa ve motor', '4 · Hat ve yağ', '5 · Tank ve ısı',
        '6 · Akümülatör', '7 · Sonuçlar ve rapor']
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
    qtbot.waitUntil(lambda: page.result is None, timeout=2000)
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
