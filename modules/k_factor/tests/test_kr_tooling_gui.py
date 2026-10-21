"""Live tooling dimensions, independent calculations and responsive Qt layout."""

import gc
from itertools import product

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QGraphicsTextItem

from gui_qt.app import MainWindow, create_application
from modules.k_factor.tooling_diagram import PUNCH_TYPES, DIE_TYPES


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([])
    w = MainWindow(tmp_path / 'settings.json')
    qtbot.addWidget(w)
    w.resize(1680, 960)
    w.show()
    w.navigate('k_factor')
    w.pages['k_factor'].tabs.setCurrentIndex(1)
    yield w
    assert not w.jobs.busy
    assert w.settings.flush()
    w.close()
    w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


def text(page, tag):
    return page.tool_diagram.vector.tagged[tag][0].toPlainText()


def contour(page, tag):
    return page.tool_diagram.vector.tagged[tag][0].polygon()


def test_selected_tool_families_change_profiles_without_changing_calculations(window, qtbot):
    page = window.pages['k_factor']
    initial = page.helper_result
    profiles = {}
    for punch, die in product(PUNCH_TYPES, DIE_TYPES):
        page.helper.set_value('punch_type', punch)
        page.helper.set_value('die_type', die)
        qtbot.waitUntil(lambda: text(page, 'punch_type') == punch and text(page, 'die_type') == die)
        assert page.helper_result == initial
        profiles[punch, die] = (contour(page, 'punch_profile'), contour(page, 'die_profile'))
    assert profiles[PUNCH_TYPES[0], DIE_TYPES[0]][0] != profiles[PUNCH_TYPES[1], DIE_TYPES[0]][0]
    assert profiles[PUNCH_TYPES[0], DIE_TYPES[0]][1] != profiles[PUNCH_TYPES[0], DIE_TYPES[1]][1]


def test_live_dimensions_follow_inputs_auto_v_and_measured_radius(window, qtbot):
    page = window.pages['k_factor']
    page.rows_model.replace([dict(thickness='2', k='0,274', r='1,5')])
    assignment = page.recipe()
    initial_punch = contour(page, 'punch_profile')
    initial_die = contour(page, 'die_profile')
    page.helper.set_value('thickness', '3')
    qtbot.waitUntil(lambda: text(page, 'thickness') == 't = 3 mm')
    assert text(page, 'die_opening') == 'V = 24 mm'
    for key, value in dict(punch='2,5', die='24', punch_angle='60', die_angle='60', angle='110', radius='4,5').items():
        page.helper.set_value(key, value)
    qtbot.waitUntil(lambda: text(page, 'part_radius') == 'İç R = 4,5 mm')
    assert text(page, 'punch_radius') == 'Rp = 2,5 mm'
    assert text(page, 'punch_angle') == 'αp = 60°'
    assert text(page, 'die_angle') == 'αv = 60°'
    assert text(page, 'bend_angle') == 'β = 110°'
    assert text(page, 'radius_source') == 'Ölçülmüş iç R'
    assert initial_punch != contour(page, 'punch_profile')
    assert initial_die != contour(page, 'die_profile')
    assert page.recipe() == assignment
    assert '4.5' in page.tool_diagram.accessibleDescription()


def test_invalid_geometry_clears_previous_preview_and_recovers(window, qtbot):
    page = window.pages['k_factor']
    page.helper.set_value('punch', '8')  # V=16: punch radius must be below V/2.
    qtbot.waitUntil(lambda: page.helper_result is None)
    assert 'yarısından küçük' in page.calculation_text.text()
    assert not page.tool_diagram.vector.tagged.get('punch_profile')
    assert not page.calculation_notes.text()
    assert 'geçerli ölçüler' in text(page, 'tooling_empty')
    page.helper.set_value('punch', '1')
    qtbot.waitUntil(lambda: page.helper_result is not None)
    assert text(page, 'punch_radius') == 'Rp = 1 mm'


def test_ba_calibration_remains_available_and_uses_measured_part_radius(window, qtbot):
    page = window.pages['k_factor']
    page.helper.set_value('method', 'BA ölçümü')
    page.helper.set_value('radius', '2')
    page.helper.set_value('ba', '4,39822971502571')
    qtbot.waitUntil(lambda: page.helper_result is not None and page.helper_result.calibrated)
    assert page.helper_result.k_factor == pytest.approx(.4)
    assert text(page, 'part_radius') == 'İç R = 2 mm'
    assert page.helper.fields['ba'].isVisible()
    assert page.helper.fields['flat'].isVisible()
    page.helper.set_value('method', 'Tablo')
    qtbot.waitUntil(lambda: not page.helper.fields['ba'].isVisible())
    assert page.helper.value('ba') == '4,39822971502571'


def test_tool_choices_and_custom_dimensions_survive_restart(window, qtbot, tmp_path):
    page = window.pages['k_factor']
    for key, value in dict(punch_type='Kaz boynu', die_type='Çift V kalıp', punch='1,5', die='17').items():
        page.helper.set_value(key, value)
    qtbot.waitUntil(lambda: text(page, 'die_opening') == 'V = 17 mm')
    assert window.settings.flush()
    other = MainWindow(tmp_path / 'settings.json')
    qtbot.addWidget(other)
    restored = other.pages['k_factor']
    assert text(restored, 'punch_type') == 'Kaz boynu'
    assert text(restored, 'die_type') == 'Çift V kalıp'
    assert text(restored, 'punch_radius') == 'Rp = 1,5 mm'
    assert text(restored, 'die_opening') == 'V = 17 mm'
    other.close()


@pytest.mark.parametrize('theme', ('dark', 'light'))
def test_responsive_preview_keeps_dimensions_in_scene_and_returns_to_columns(window, qtbot, theme):
    window.set_theme(theme)
    page = window.pages['k_factor']
    original = page.tool_diagram
    for size in ((1680, 960), (1024, 700), (820, 620), (1366, 768), (1680, 960)):
        window.resize(*size)
        qtbot.waitUntil(lambda: page.helper_workspace.compact == (page.helper_workspace.width() < 940))
        qtbot.wait(20)
        assert page.tool_diagram is original
        assert page.helper.isVisible() and original.isVisible()
        assert page.helper_workspace.input_scroll.widget() is (None if page.helper_workspace.compact else page.helper_workspace.inputs)
        for item in original.vector.items():
            if isinstance(item, QGraphicsTextItem):
                assert original.sceneRect().contains(item.sceneBoundingRect())
                assert original.viewport().rect().contains(original.mapFromScene(item.sceneBoundingRect()).boundingRect())
        assert not window.grab().isNull()
