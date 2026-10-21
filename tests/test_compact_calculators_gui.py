"""Compact calculator workspaces retain their editable data and engineering views."""

import gc
import json

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QGraphicsTextItem

from gui_qt.app import MainWindow, create_application
from modules.weight import rules as weight


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([])
    widget = MainWindow(tmp_path / 'settings.json')
    qtbot.addWidget(widget)
    widget.resize(1440, 900)
    widget.show()
    yield widget
    assert not widget.jobs.busy
    assert widget.settings.flush()
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


def test_manual_rows_stay_compact_and_keep_saved_assignments(window, qtbot):
    window.navigate('k_factor')
    page = window.pages['k_factor']
    page.tabs.setCurrentIndex(0)
    qtbot.waitUntil(lambda: page.rows.isVisible())
    assert page.rows.height() < 200
    first = {'thickness': '2', 'k': '0,274', 'r': '1,5'}
    for column, value in enumerate(first.values()):
        assert page.rows_model.setData(page.rows_model.index(0, column), value, Qt.EditRole)
    page.add_row.click()
    second = {'thickness': '3', 'k': '0,33', 'r': '2'}
    for column, value in enumerate(second.values()):
        assert page.rows_model.setData(page.rows_model.index(1, column), value, Qt.EditRole)
    assert len(page.recipe().rows) == 2
    assert page.settings.get('kr_manual_k') == first['k']
    assert json.loads(page.settings.get('kr_manual_rows')) == [second]
    page.rows.setCurrentIndex(page.rows_model.index(1, 0))
    page.remove_row.click()
    assert page.rows_model.rows == [first]
    assert json.loads(page.settings.get('kr_manual_rows')) == []
    # The helper is independent and still contains the live tooling drawing.
    assignment = page.recipe()
    page.tabs.setCurrentIndex(1)
    page.helper.set_value('thickness', '3')
    qtbot.waitUntil(lambda: page.helper_result.thickness_mm == 3)
    assert page.recipe() == assignment
    assert page.tool_diagram.vector.tagged['punch_profile']
    assert page.tool_diagram.vector.tagged['die_profile']


@pytest.mark.parametrize('mode', ('bolt', 'weight'))
def test_report_disclosure_retains_complete_copy_and_current_results(window, qtbot, mode):
    window.navigate(mode)
    page = window.pages[mode]
    expected = list(page.report)
    assert expected and not page.report_disclosure.is_expanded()
    assert not page.metrics.isVisible()
    page.report_disclosure.toggle.click()
    qtbot.waitUntil(lambda: page.metrics.isVisible())
    assert page.metric_model.rowCount() == len(expected)
    page.report_disclosure.toggle.click()
    assert not page.metrics.isVisible()
    page.copy_report()
    copied = QApplication.clipboard().text()
    assert all(f'{key}: {value}' in copied for key, value in expected)
    assert page.report == expected
    assert all(diagram.vector.items() for diagram in page.diagrams.values())


def test_weight_switches_units_material_and_catalogue_without_losing_dimensions(window, qtbot):
    window.navigate('weight')
    page = window.pages['weight']
    form = page.form
    form.set_value('b', '125')
    form.set_value('t', '6')
    form.set_value('length', '2000')
    qtbot.waitUntil(lambda: page.result.length_mm == 2000)
    mass = page.result.total_mass_kg
    for unit in ('cm', 'm', 'mm'):
        form.set_value('unit', unit)
        qtbot.waitUntil(lambda: page.result.unit == unit)
        assert page.result.total_mass_kg == pytest.approx(mass)
        assert page.result.dimensions_mm['b'] == pytest.approx(125)
        assert page.result.dimensions_mm['t'] == pytest.approx(6)
    form.set_value('method', 'Katalog alanından')
    form.set_value('area_cm2', '12')
    qtbot.waitUntil(lambda: page.result.area_mm2 == 1200)
    assert form.fields['area_cm2'].isVisible()
    assert not form.fields['b'].isVisible()
    form.set_value('material_group', 'Paslanmaz')
    box = form.fields['material']
    box.setCurrentIndex(box.findData('316L'))
    qtbot.waitUntil(lambda: page.result.material == '316L')
    assert page.result.density == weight.MATERIALS['316L']
    assert str(weight.MATERIALS['316L']) in page.density_label.text()
    assert page.settings.get('weight_material') == '316L'
    form.set_value('method', 'Ölçülerden')
    qtbot.waitUntil(lambda: page.result.method == 'Ölçülerden')
    assert form.fields['b'].isVisible()
    assert form.value('b') == '125' and form.value('t') == '6'
    assert page.result.area_mm2 == 750


@pytest.mark.parametrize('theme', ('dark', 'light'))
def test_minimum_and_wide_calculators_keep_fields_and_vector_views(window, qtbot, theme):
    window.set_theme(theme)
    for size in ((820, 560), (1024, 700), (1440, 900)):
        window.resize(*size)
        for mode in ('bolt', 'bolt_torque', 'weight'):
            window.navigate(mode)
            page = window.pages[mode]
            qtbot.wait(20)
            assert page.result is not None
            assert window.stack.geometry().right() < window.width()
            for field in page.form.fields.values():
                if field.isVisible():
                    assert field.width() >= 100, (size, mode, field.objectName(), field.width())
            diagrams = ([page.section_diagram] if mode == 'bolt_torque'
                        else list(page.diagrams.values()))
            for diagram in diagrams:
                assert diagram.vector.items()
                for item in diagram.vector.items():
                    if isinstance(item, QGraphicsTextItem):
                        assert diagram.sceneRect().contains(item.sceneBoundingRect())
            assert not window.grab().isNull()
