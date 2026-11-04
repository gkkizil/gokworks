"""DFM page: menu reachable, background analysis, finding selection, filters and reports."""

import json

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QFileDialog

from gui_qt.app import MainWindow, create_application, MODULES
from modules.dfm_analyzer import reporting

from .test_geometry_rules import dxf, rect


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([]); w = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(w)
    w.show(); yield w
    if w.jobs.busy:
        w.jobs.cancel(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=8000)
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def plate(tmp_path, units=4):
    def build(doc, msp):
        rect(msp, 0, 0, 100, 50)
        msp.add_circle((50, 25), .75)              # Ø1.5 < 2 mm limit at t = 2
        msp.add_circle((3, 25), 2)                 # 1 mm from the left edge
        msp.add_line((200, 0), (260, 0))           # open contour
    return dxf(tmp_path / 'plate.dxf', build, units=units)


def run(qtbot, page, path, thickness=2):
    page.path.setText(str(path)); page.thickness.setValue(thickness)
    page.start()
    qtbot.waitUntil(lambda: not page.jobs.busy, timeout=20000)


def test_page_is_in_the_menu_and_analysis_runs_in_the_background(qtbot, window, tmp_path, monkeypatch):
    assert any(key == 'dfm_analyzer' for key, *_ in MODULES)
    window.navigate('dfm_analyzer'); assert window.mode == 'dfm_analyzer'
    page = window.pages['dfm_analyzer']
    source = plate(tmp_path); before = source.read_bytes()
    run(qtbot, page, source)
    assert page.result is not None and source.read_bytes() == before
    ids = {f.rule_id for f in page.result.findings}
    assert {'DFM-LAS-001', 'DFM-LAS-003', 'DFM-GEO-001'} <= ids
    assert page.proxy.rowCount() == len(page.result.findings)
    assert page.proxy.index(0, 0).data() == 'Hata'                    # errors sort first

    # Selecting a row highlights that finding and zooms to it.
    row = next(r for r in range(page.proxy.rowCount()) if page.proxy.index(r, 1).data() == 'DFM-LAS-001')
    page.table.selectRow(row)
    index = page.proxy.index(row, 0).data(Qt.UserRole)
    assert page.view.selected == index and page.view.marker_items[index]
    assert 'Ø1,5' in page.details.toPlainText() or '1,5' in page.details.toPlainText()
    visible = page.view.mapToScene(page.view.viewport().rect()).boundingRect()
    assert visible.width() < 60                                        # zoomed in on the 1.5 mm hole

    # A click on the marker selects the row back.
    page.table.clearSelection(); page.view.findingClicked.emit(index)
    assert page.table.selectionModel().selectedRows()[0].data(Qt.UserRole) == index

    # Severity and text filters combine.
    page.severity.setCurrentIndex(page.severity.findData('ERROR'))
    assert page.proxy.rowCount() == sum(f.severity == 'ERROR' for f in page.result.findings) > 0
    page.search.setText('DFM-LAS')
    assert page.proxy.rowCount() == 0                                   # laser findings are warnings
    page.severity.setCurrentIndex(0)
    assert page.proxy.rowCount() == sum(f.rule_id.startswith('DFM-LAS') for f in page.result.findings)
    page.search.clear()

    # JSON and CSV reports.
    for kind in ('json', 'csv'):
        target = tmp_path / f'out.{kind}'
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, t=target: (str(t), ''))
        page.save_report(kind)
        assert target.is_file()
    assert reporting.read_json(tmp_path / 'out.json').summary() == page.result.summary()
    assert 'DFM-LAS-001' in (tmp_path / 'out.csv').read_text(encoding='utf-8-sig')


def test_missing_units_asks_for_a_unit_and_inch_scales(qtbot, window, tmp_path):
    page = window.pages['dfm_analyzer']
    path = dxf(tmp_path / 'nounits.dxf', lambda doc, msp: rect(msp, 0, 0, 4, 2), units=0)
    run(qtbot, page, path, thickness=0)
    assert page.result is None and 'birim' in page.status_text.casefold()
    page.unit.setCurrentIndex(page.unit.findData('inch'))
    run(qtbot, page, path, thickness=0)
    xs = [p[0] for p in page.result.parts[0]['outline']]
    assert max(xs) - min(xs) == pytest.approx(4 * 25.4)
    assert any('girilmedi' in o.reason.casefold() or 'kalınl' in o.reason for o in page.result.outcomes
               if o.status == 'NOT_EVALUATED')


def test_disabled_rules_are_not_run_and_theme_change_keeps_the_result(qtbot, window, tmp_path):
    page = window.pages['dfm_analyzer']
    for i in range(page.rule_list.count()):
        item = page.rule_list.item(i)
        if item.data(Qt.UserRole) != 'DFM-LAS-001':
            item.setCheckState(Qt.Unchecked)
    run(qtbot, page, plate(tmp_path))
    assert {f.rule_id for f in page.result.findings} == {'DFM-LAS-001'}
    window.set_theme('light')
    assert page.view.appearance == 'light' and page.proxy.rowCount() == 1
    for i in range(page.rule_list.count()):
        page.rule_list.item(i).setCheckState(Qt.Unchecked)
    page.start()
    assert 'en az bir kural' in page.status_text.casefold()
