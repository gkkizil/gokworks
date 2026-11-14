"""Pratik hesap görünümü: kompakt alanlar, çevrim şeridi, kaydırmadan görünen gösterge kutuları."""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint

from gui_qt.app import create_application
from gui_qt.settings import SettingsStore
from gui_qt.workers import JobManager
from modules.hydraulic_unit.presentation import result_rows
from modules.hydraulic_unit.beginner_view import show
from modules.hydraulic_unit.ui import HydraulicPage


@pytest.fixture
def page(qtbot, tmp_path):
    create_application([])
    context = SimpleNamespace(settings=SettingsStore(tmp_path / 'settings.json'), jobs=JobManager(), appearance='dark')
    page = HydraulicPage(context); qtbot.addWidget(page); page.resize(1130, 700); page.show(); qtbot.wait(20)
    yield page
    page.cancel_pdf(); page.settings.flush()


def edit(page, **values):
    for key, value in values.items():
        w = page.quick.inputs[key]; w.setText(str(value)); w.textEdited.emit(str(value))


def test_units_sit_inside_the_inputs_and_headings_stay_buddies(page):
    q = page.quick
    for key, edit_widget in q.inputs.items():
        frame = edit_widget.parentWidget()
        assert frame.property('unitField') and edit_widget._unit_label.parentWidget() is frame, key
    assert q.inputs['force']._unit_label.text() == 'tonf' and q.inputs['bore']._unit_label.text() == 'mm'


def test_cycle_strip_follows_the_times_as_they_are_typed(page):
    q = page.quick
    edit(page, extend_time='4', hold_time='2', return_time='6')
    assert q.strip.parts == [('İleri', 4.), ('Bekle', 2.), ('Geri', 6.)]
    assert 'toplam 12 s' in q.strip.accessibleDescription()
    edit(page, hold_time='0')
    assert [name for name, _ in q.strip.parts] == ['İleri', 'Geri']
    edit(page, return_time='abc')                                         # unfinished typing: no crash, unknown part
    assert q.strip.parts[-1] == ('Geri', None)


def test_four_metrics_show_core_values_and_states_side_by_side_with_the_form(page, qtbot):
    q = page.quick
    edit(page, bore='80', rod='40', stroke='200', force='2', extend_time='10', return_time='15', hold_time='2')
    q.calculate(); qtbot.wait(30)
    rows = {name: show(value, unit) for name, value, unit, _ in result_rows(page.project, page.result)}
    assert q.cards['pressure'].value.text() == rows['Maksimum gerekli basınç']
    assert q.cards['tank'].value.text() == rows['Gerekli kullanılabilir tank']
    assert all(card.isVisible() and card.property('state') in ('success', 'warning', 'error') for card in q.cards.values())
    assert q.chip.text() in ('Uygun',) or q.chip.text().endswith(('kritik', 'kontrol'))
    # A 1366 px window (page ~1130 px): form and results side by side, metrics in 2 x 2, titles not cut.
    assert q.form.mapTo(q, QPoint()).y() == q.output_panel.mapTo(q, QPoint()).y()
    assert q.metrics.columns == 2
    for card in q.cards.values():
        assert card.title.width() >= card.title.sizeHint().width() - 1, card.title.text()
        assert card.value.width() >= card.value.sizeHint().width() - 1, card.value.text()


def test_editing_after_a_result_turns_the_chip_back_to_a_draft(page, qtbot):
    q = page.quick
    q.calculate(); qtbot.wait(20)
    assert q.chip.property('role') in ('success', 'warning', 'error')
    edit(page, stroke='250')
    assert q.chip.property('role') == 'muted' and 'hesaplayın' in q.chip.text()
    assert all(not card.isVisible() for card in q.cards.values())
    edit(page, rod='90'); q.calculate(); qtbot.wait(20)
    assert q.chip.property('role') == 'error' and q.chip.text() == 'Girdi hatası'
