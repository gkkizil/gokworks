"""The practical form keeps the unit circuit visible, current and interactive."""
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from gui_qt.components import Disclosure

from .test_practical import edit, page as page


def assert_directly_visible(schematic, view):
    assert schematic.isVisible()
    parent = schematic.parentWidget()
    while parent is not view:
        assert parent is not None
        assert not isinstance(parent, Disclosure)
        parent = parent.parentWidget()


def assert_cleared(schematic):
    assert schematic.empty_text
    assert all(node.value == '—' and node.state is None for node in schematic.nodes.values())


def test_practical_circuit_is_visible_before_calculation_and_matches_the_result(page):
    q = page.quick
    assert_directly_visible(q.schematic, q)
    assert_cleared(q.schematic)

    edit(page, bore=80, rod=45, stroke=400, force=5, extend_time=4, return_time=4)
    q.calculate()

    assert q.ready and not q.schematic.empty_text
    assert_directly_visible(q.schematic, q)
    assert q.schematic.nodes == page.simple.schematic.nodes
    assert q.schematic.nodes['motor'].value == q.cards['motor'].value.text()
    assert q.schematic.nodes['pump'].value == q.cards['pump'].value.text()
    assert q.schematic.nodes['cooler'].state == 'error'
    assert not q.schematic.nodes['accumulator'].present
    assert q.schematic.accessibleDescription() == page.simple.schematic.accessibleDescription()


def test_original_movement_plan_shows_its_circuit_without_an_extra_action(page, qtbot):
    page.quick.calculate()
    page.view_mode.setCurrentIndex(0)
    page.simple.go_to_step(2)
    qtbot.wait(10)

    assert_directly_visible(page.simple.schematic, page.simple)
    assert page.simple.schematic.nodes['motor'].value != '—'


def test_pending_edits_and_errors_clear_practical_values_without_mutating_shared_nodes(page):
    q = page.quick
    q.calculate()
    original_nodes = deepcopy(page.simple.schematic.nodes)
    original_presence = {key: node.present for key, node in original_nodes.items()}

    edit(page, bore='invalid')

    assert_cleared(q.schematic)
    assert_directly_visible(q.schematic, q)
    assert page.simple.schematic.nodes == original_nodes
    assert {key: node.present for key, node in q.schematic.nodes.items()} == original_presence

    q.calculate()

    assert q.error.isVisible() and not q.ready and page.result is None
    assert_cleared(q.schematic)
    assert_directly_visible(q.schematic, q)
    assert {key: node.present for key, node in q.schematic.nodes.items()} == original_presence


def test_mouse_activation_opens_the_practical_cylinder_and_detailed_cooling_settings(page, qtbot):
    q = page.quick
    q.calculate()
    q.workspace.ensureWidgetVisible(q.schematic)
    qtbot.wait(10)

    QTest.mouseClick(q.schematic, Qt.LeftButton, Qt.NoModifier, q.schematic.node_center('cylinder'))

    assert page.input_stack.currentIndex() == 2
    assert q.inputs['bore'].hasFocus()

    q.workspace.ensureWidgetVisible(q.schematic)
    QTest.mouseClick(q.schematic, Qt.LeftButton, Qt.NoModifier, q.schematic.node_center('cooler'))

    assert page.input_stack.currentIndex() == 1 and page.tabs.currentIndex() == 4


def test_keyboard_activation_opens_the_pump_settings(page, qtbot):
    q = page.quick
    q.calculate()
    opened = []
    q.schematic.nodeClicked.connect(opened.append)
    q.workspace.ensureWidgetVisible(q.schematic)
    q.schematic.setFocus()
    qtbot.wait(10)
    assert q.schematic.hover == 'cylinder'

    QTest.keyClick(q.schematic, Qt.Key_Right)
    QTest.keyClick(q.schematic, Qt.Key_Return)

    assert opened == ['pump']
    assert page.input_stack.currentIndex() == 1 and page.tabs.currentIndex() == 2


def test_theme_changes_update_both_circuits_without_changing_their_results(page):
    page.quick.calculate()
    original_nodes = deepcopy(page.quick.schematic.nodes)
    page.context.appearance = 'light'

    page.theme_changed()

    assert page.quick.schematic.appearance == page.simple.schematic.appearance == 'light'
    assert page.quick.schematic.nodes == page.simple.schematic.nodes == original_nodes


def test_existing_special_plan_keeps_its_live_circuit_and_cylinder_route(page, tmp_path):
    from modules.hydraulic_unit.core.models import Project
    from modules.hydraulic_unit.serialization import save
    original = Project(); path = tmp_path / 'original.gwhyd'; save(original, path)
    page.load_path(path)
    assert not page.quick.allowed and page.project == original
    assert_directly_visible(page.quick.schematic, page.quick)
    assert page.quick.schematic.nodes == page.simple.schematic.nodes
    assert page.quick.schematic.nodes['motor'].value != '—'
    page.quick.schematic.nodeClicked.emit('cylinder')
    assert page.input_stack.currentIndex() == 1 and page.tabs.currentIndex() == 0
    assert page.project == original
