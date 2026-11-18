"""Automatic drawing and press brake name what they cover; PASS states what it means (Ö4)."""
import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from gui_qt.app import MainWindow, create_application
from gui_qt.coverage import LEVELS, PARTIAL, SUPPORTED, UNSUPPORTED, CoverageList
from modules.automatic_drawing import coverage as drawing
from modules.press_brake import coverage as brake


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([]); w = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(w)
    w.show(); yield w
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def levels(items):
    return {topic: level for topic, level, _ in items}


def test_drawing_coverage_names_every_requested_topic_honestly():
    table = levels(drawing.COVERAGE)
    assert table['Kesit görünüşü'] == UNSUPPORTED and table['Detay / yardımcı görünüş'] == UNSUPPORTED
    assert table['Diş / havşa açıklaması'] == UNSUPPORTED and table['PCD (bölüm dairesi)'] == UNSUPPORTED
    assert table['Delik ölçüleri'] == PARTIAL and table['Ölçülendirme'] == PARTIAL
    assert table['Büyük BOM’u paftalara bölme'] == UNSUPPORTED
    assert table['Çok gövdeli sac açınımı'] == PARTIAL
    assert table['Gerçek SolidWorks kabulü'] == UNSUPPORTED


def test_press_brake_coverage_separates_sampled_from_continuous_and_lists_machine_items():
    table = levels(brake.COVERAGE)
    assert table['Sac – takım çarpışması'] == PARTIAL
    for topic in ('Tezgâh gövdesi (üst kiriş, alt ray)', 'Arka dayama', 'Yeniden tutuş / parça çevirme',
                  'Büküm kuvveti (tonaj)', 'Geri yaylanma', 'CNC strok / eksen değerleri'):
        assert table[topic] == UNSUPPORTED, topic
    assert 'sürekli kanıtlanmaz' in brake.PASS_MEANING


@pytest.mark.parametrize('items', [drawing.COVERAGE, brake.COVERAGE])
def test_every_row_has_a_known_level_and_a_reason(items):
    assert all(level in LEVELS and note.strip() for _, level, note in items)
    assert any(level == SUPPORTED for _, level, _ in items)


def test_pages_show_coverage_and_pass_meaning(window):
    page = window.pages['automatic_drawing']
    titles = [page.tabs.tabText(i) for i in range(page.tabs.count())]
    assert 'Kapsam' in titles
    assert isinstance(page.coverage, CoverageList) and page.coverage.items == drawing.COVERAGE
    assert page.pass_meaning.text() == drawing.PASS_MEANING
    press = window.pages['press_brake']
    assert isinstance(press.coverage, CoverageList) and press.coverage.items == brake.COVERAGE
    assert press.result_badge.toolTip()                         # scope is visible before any check
    from types import SimpleNamespace
    press.result = SimpleNamespace(status='clear'); press.show_result_badge()
    assert press.result_badge.toolTip() == brake.PASS_MEANING
