"""Kolay kullanım tasarımı: adım akışı, ölçü çizimi, sonuç kartları, hata yönlendirmesi."""
from types import SimpleNamespace
import time

import pytest
from PySide6.QtCore import QCoreApplication, Qt

from gui_qt.app import create_application
from gui_qt.settings import SettingsStore
from gui_qt.workers import JobManager
from modules.hydraulic_unit.beginner_view import show, text_number
from modules.hydraulic_unit.core.service import calculate_project
from modules.hydraulic_unit.ui import HydraulicPage


@pytest.fixture
def easy(qtbot, tmp_path):
    create_application([])
    context = SimpleNamespace(settings=SettingsStore(tmp_path / 'settings.json'), jobs=JobManager(), appearance='dark')
    page = HydraulicPage(context); qtbot.addWidget(page); page.resize(1366, 800); page.show(); qtbot.wait(10)
    yield page
    page.cancel_pdf(); page.settings.flush()


def edit(widget, text):
    widget.setText(text); widget.textEdited.emit(text)


def test_numbers_are_rounded_for_display_without_dropping_digits():
    assert text_number(300, 0) == '300' and text_number(2.0833333) == '2,083' and text_number(250., 1) == '250'
    assert show(250) == '250' and show(9.144, 'cm3/rev') == '9,14 cm³/dev' and show(None) == 'seri dışında'


def test_step_bar_says_where_the_user_is_and_what_comes_next(easy):
    s = easy.simple
    assert [b.isChecked() for b in s.step_buttons] == [True, False, False]
    assert 'Adım 1/3' in s.step_hint.text() and s.next_button.text() == 'Devam: Hareketler →'
    assert not s.back_button.isEnabled()
    s.next_button.click()
    assert s.steps.currentIndex() == 1 and s.step_buttons[1].isChecked() and 'Sonuç' in s.next_button.text()
    s.step_buttons[2].click()
    assert s.steps.currentIndex() == 2 and not s.next_button.isVisible() and s.back_button.isEnabled()


def test_measurement_fields_explain_where_the_value_comes_from(easy):
    s = easy.simple
    bore = s.inputs['cylinder.bore']
    assert bore.placeholderText() == 'örn. 63'
    texts = ' '.join(l.text() for l in s.steps.widget(0).findChildren(type(s.step_hint)))
    assert 'iç çapı' in texts and 'Gövdenin dışını ölçmeyin' in texts and 'teknik resim' in texts
    edit(bore, '80')
    assert s.diagram.values['bore'] == 80.
    assert 'İtme alanı' in s.auto_values.text()          # automatic values are labelled as such


def test_motion_table_has_plain_questions_units_and_explains_disabled_cells(easy):
    s = easy.simple
    texts = [h.text() for h in s.header_labels]
    assert texts[1].startswith('Ne kadar yol alsın?') and texts[2].startswith('Kaç saniye sürsün?')
    assert texts[3].startswith('Gerekli itme / çekme kuvveti')
    hold = [i for i, p in enumerate(easy.project.phases) if p.kind == 'hold'][0]
    assert 'stroke' not in s.phase_inputs[hold]
    derived = s.phase_inputs[0]['duration']
    assert derived.property('derived') and 'Hızdan hesaplandı' in derived.toolTip() and derived.text() == '2,083'
    edit(derived, '4')
    assert not derived.property('derived')
    easy.recalculate()
    assert easy.project.phases[0].duration == 4. and easy.project.phases[0].speed is None


def test_force_unit_switch_relabels_cells_and_keeps_newtons(easy):
    s = easy.simple; before = [p.force for p in easy.project.phases]
    s.force_unit.setCurrentIndex(s.force_unit.findData('tonf'))
    assert s.phase_inputs[1]['force']._unit_label.text() == 'tonf'
    easy.recalculate()
    assert [p.force for p in easy.project.phases] == before


def test_result_cards_separate_need_current_and_recommendation(easy):
    s = easy.simple; cards = s.results.cards
    assert s.results.rowCount() == 6
    assert cards['pump'].tag.text() == 'İHTİYAÇ' and 'Mevcut pompa' in cards['pump'].lines.text()
    assert 'Öneri (nominal seri)' in cards['pump'].lines.text()
    assert cards['motor'].tag.text() == 'ÖNERİ' and 'İhtiyaç' in cards['motor'].lines.text()
    assert cards['pipe'].tag.text() == 'ÖNERİ' and 'İÇ çapı' in cards['pipe'].note.text()
    assert 'kullanılabilir' in cards['tank'].note.text()
    assert cards['pressure'].toolTip()          # formula help from the core presentation rows
    nominal = easy.result.cycle['displacement']['nominal'] * 1e6
    assert show(nominal, 'cm3/rev') in cards['pump'].lines.text()


def test_charts_and_motion_strip_come_from_the_result(easy):
    s = easy.simple; phases = easy.result.cycle['phases']
    assert len(s.charts['pressure'].points) == len(phases) == len(s.motion_chart.segments)
    assert s.motion_chart.segments[-1][3] == pytest.approx(phases[-1].end_position * 1000)


def test_issues_explain_the_fix_and_lead_to_it(easy):
    s = easy.simple
    assert 'kritik' in s.verdict.text() and 'yağ soğutması' in s.verdict.text()
    rows = [s.issue_rows.itemAt(i).widget() for i in range(s.issue_rows.count())]
    assert rows and all(r.go is not None for r in rows)
    assert any('Ne yapabilirsiniz' in l.text() for r in rows for l in r.findChildren(type(s.step_hint)))
    rows[0].go.click()                           # thermal issue → detailed tank / heat settings
    assert easy.input_stack.currentIndex() == 1 and easy.tabs.currentIndex() == 4


def test_invalid_input_stops_reports_marks_step_and_fix_focuses_the_field(easy, qtbot):
    s = easy.simple; rod = s.inputs['cylinder.rod']
    edit(rod, '70'); easy.recalculate()
    assert easy.result is None and s.error_box.isVisible() and rod.property('invalid')
    assert s.state_pill.text().startswith('Girdi hatası') and 'düzeltin' in s.step_buttons[0].text()
    assert not s.pdf_button.isEnabled() and not s.excel_button.isEnabled() and s.results.rowCount() == 0
    assert 'İtme alanı' not in s.auto_values.text()             # no stale automatic values
    s.go_to_step(2); s.fix_button.click(); qtbot.wait(10)
    assert s.steps.currentIndex() == 0 and easy.focusWidget() is rod
    edit(rod, '36'); easy.recalculate()
    assert easy.result is not None and not s.error_box.isVisible() and 'düzeltin' not in s.step_buttons[0].text()


def test_invalid_input_does_not_recalculate_in_a_loop(easy):
    calls = []; original = easy.recalculate
    easy.timer.timeout.disconnect(); easy.timer.timeout.connect(lambda: (calls.append(1), original()))
    edit(easy.simple.inputs['cylinder.rod'], '70')
    end = time.monotonic() + 1.2
    while time.monotonic() < end:
        QCoreApplication.processEvents(); time.sleep(.01)
    assert len(calls) == 1 and easy.result is None


def test_editing_marks_results_stale_until_recalculated(easy):
    s = easy.simple
    edit(s.inputs['cylinder.bore'], '70')
    assert s.state_pill.text() == 'Hesaplanıyor…' and not s.pdf_button.isEnabled()
    assert not s.results.cards['motor'].isEnabled()
    easy.recalculate()
    assert s.state_pill.text().startswith('Hesap güncel') and s.pdf_button.isEnabled()
    assert easy.result.input_fingerprint != calculate_project(easy.project.__class__()).input_fingerprint


def test_theme_change_repaints_drawings(easy):
    easy.context.appearance = 'light'; easy.theme_changed()
    s = easy.simple
    assert s.motion_chart.appearance == 'light' and all(c.appearance == 'light' for c in s.charts.values())


@pytest.mark.parametrize('width', [790, 1130, 1690])     # page area at 1024, 1366 and 1920 px windows
def test_no_step_needs_horizontal_scrolling(easy, qtbot, width):
    easy.resize(width, 640); qtbot.wait(20)
    for index in range(3):
        easy.simple.go_to_step(index); qtbot.wait(20)
        assert easy.simple.steps.widget(index).horizontalScrollBar().maximum() == 0, index
