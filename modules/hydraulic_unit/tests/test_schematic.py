"""Ünite şeması: sonuç değerleri eleman üzerinde, durum işaretli; tıklama ilgili ayarı açar."""
from types import SimpleNamespace
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from gui_qt.app import create_application
from gui_qt.settings import SettingsStore
from gui_qt.workers import JobManager
from modules.hydraulic_unit.schematic import NODES, ORDER, Node, UnitSchematic
from modules.hydraulic_unit.ui import HydraulicPage


@pytest.fixture
def page(qtbot, tmp_path):
    create_application([])
    context = SimpleNamespace(settings=SettingsStore(tmp_path / 'settings.json'), jobs=JobManager(), appearance='dark')
    page = HydraulicPage(context); qtbot.addWidget(page); page.resize(1366, 800); page.show()
    qtbot.waitUntil(lambda: page.result is not None, timeout=5000)
    page.simple.go_to_step(2); qtbot.wait(30)
    yield page
    page.cancel_pdf(); page.settings.flush()


def test_schematic_shows_the_same_values_and_states_as_the_result_cards(page):
    s = page.simple; nodes = s.schematic.nodes
    cards = s.results.cards
    assert nodes['motor'].value == cards['motor'].value.text() and nodes['pump'].value == cards['pump'].value.text()
    assert nodes['cooler'].value == cards['cooler'].value.text()
    assert nodes['pipe'].value.startswith('Ø') and cards['pipe'].value.text() in nodes['pipe'].value
    assert nodes['cooler'].state == 'error' and nodes['pipe'].state == 'warning'      # HOT_OIL critical, VELOCITY warning
    assert nodes['motor'].state == 'success' and nodes['tank'].state == 'success'
    assert not nodes['accumulator'].present                                           # no accumulator in the default project
    assert 'Soğutucu' in s.schematic.accessibleDescription() and 'kritik' in s.schematic.accessibleDescription()
    assert 'Yağ soğutucusuz çok ısınıyor.' in nodes['cooler'].tip                      # why it is red, in plain words


def test_clicking_an_element_opens_its_setting(page, qtbot):
    s = page.simple
    QTest.mouseClick(s.schematic, Qt.LeftButton, Qt.NoModifier, s.schematic.node_center('cylinder'))
    assert s.steps.currentIndex() == 0                                                # cylinder sizes: step 1
    s.go_to_step(2); qtbot.wait(20)
    QTest.mouseClick(s.schematic, Qt.LeftButton, Qt.NoModifier, s.schematic.node_center('cooler'))
    assert page.input_stack.currentIndex() == 1 and page.tabs.currentIndex() == 4           # detailed view, tank / heat tab


def test_keyboard_moves_between_elements_and_opens_one(page, qtbot):
    s = page.simple; opened = []
    s.schematic.nodeClicked.connect(opened.append)
    s.schematic.setFocus(); qtbot.wait(10)
    assert s.schematic.hover == 'cylinder'
    QTest.keyClick(s.schematic, Qt.Key_Right); QTest.keyClick(s.schematic, Qt.Key_Return)
    assert opened == ['pump']


def test_input_error_clears_numbers_but_keeps_the_circuit(page, qtbot):
    s = page.simple
    bore = s.inputs['cylinder.bore']; bore.setText('-5'); bore.textEdited.emit('-5')
    qtbot.waitUntil(lambda: page.result is None and bool(s.schematic.empty_text), timeout=5000)
    assert all(node.value == '—' and node.state is None for node in s.schematic.nodes.values())


def test_labels_do_not_overlap_each_other_or_leave_the_canvas(qtbot):
    create_application([])
    w = UnitSchematic('dark'); qtbot.addWidget(w)
    w.set_nodes({key: Node('123,4 kW', 'öneri', 'success') for key in NODES})        # accumulator included
    rects = {key: w.label_rect(key) for key in ORDER}
    for a in ORDER:
        assert rects[a].left() >= 0 and rects[a].right() <= 1000 and rects[a].bottom() <= 356
        for b in ORDER:
            assert a == b or not rects[a].intersects(rects[b]), (a, b)
    for width in (560, 760, 1100):
        w.resize(width, 10); w.show(); qtbot.wait(10)
        assert w.height() == w.heightForWidth(width) and w.grab().height() == w.height()
