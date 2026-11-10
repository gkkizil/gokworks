"""Press brake workbench layout: step cards, scene read-out, view cube interaction, tool cards, narrow windows."""
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem
from gui_qt.app import MainWindow, create_application
from modules.press_brake.cards import CARD, STATES
from modules.press_brake.demo import tools
from modules.press_brake.service import STATUS
from modules.press_brake.tool_picker import ToolPicker


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([]); w = MainWindow(tmp_path/'settings.json'); qtbot.addWidget(w)
    w.resize(1366, 768); w.show(); w.navigate('press_brake')
    w.pages['press_brake'].library_path = tmp_path/'tools.json'
    yield w
    if w.jobs.busy:
        w.jobs.cancel(); qtbot.waitUntil(lambda: not w.jobs.busy, timeout=20000)
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def finish(w, qtbot, timeout=60000):
    qtbot.waitUntil(lambda: not w.jobs.busy and not w.pages['press_brake'].preview_pending, timeout=timeout)


def test_three_check_results_keep_their_own_words_symbols_and_colours():
    assert {k: v[1] for k, v in STATES.items() if k} == STATUS          # same texts as the service and the PDF
    assert len({v[0] for v in STATES.values()}) == 4 and len({v[2] for v in STATES.values()}) == 4


def test_scene_mouse_leave_and_view_cube_click_do_not_break_the_bend_annotations(window, qtbot):
    """The bend overlay used to replace the viewer's view-cube overlay: leaving or clicking the scene raised."""
    p = window.pages['press_brake']; p.load_demo('L120'); finish(window, qtbot)
    v = p.viewer
    assert v.annotations is not v.overlay and hasattr(v.overlay, 'face_at')
    QApplication.sendEvent(v, QEvent(QEvent.Leave))
    for point in (QPointF(v.width()-40, 40), QPointF(v.width()/2, v.height()/2)):
        for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            QApplication.sendEvent(v, QMouseEvent(kind, point, v.mapToGlobal(point.toPoint()), Qt.LeftButton,
                                                  Qt.LeftButton if kind == QEvent.MouseButtonPress else Qt.NoButton, Qt.NoModifier))
    move = QMouseEvent(QEvent.MouseMove, QPointF(5, 5), v.mapToGlobal(QPoint(5, 5)), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
    QApplication.sendEvent(v, move); qtbot.wait(30)
    assert v.annotations.isVisible() and v.frame is not None


def test_step_cards_show_order_state_tool_change_and_regrip(window, qtbot):
    p = window.pages['press_brake']; p.load_demo('U'); finish(window, qtbot)
    first, second = (p.bends.item(i).data(CARD) for i in range(2))
    assert (first['number'], second['number']) == (1, 2)
    assert first['status'] is None and not first['regrip'] and second['regrip']
    assert 'R 2' in first['detail'] and p.sequence_title.text() == 'BÜKÜM SIRASI · 2'
    p.bends.setCurrentRow(1); finish(window, qtbot)
    p.punch.setCurrentIndex(p.punch.findData('demo-wide')); finish(window, qtbot)
    assert p.bends.item(1).data(CARD)['change'] and 'Takım değişimi' in p.bends.item(1).text()
    option = QStyleOptionViewItem(); option.font = p.bends.font()
    hint = p.step_cards.sizeHint(option, p.bends.model().index(1, 0))
    assert hint.height() > 60
    assert p.bend_label.text().startswith('Adım 2 / 2') and p.values['radius'].text() == '2 mm'


@pytest.mark.timeout(240)
def test_scene_read_out_follows_step_phase_angle_and_result_badge(window, qtbot):
    p = window.pages['press_brake']; p.load_demo('L120'); finish(window, qtbot)
    assert p.result_badge.text() == '○ Kontrol bekliyor'
    p.punch.setCurrentIndex(p.punch.findData('demo-wide')); finish(window, qtbot)
    p.calculate(); finish(window, qtbot, 200000)
    assert p.result.status == 'collision' and p.result_badge.text() == '✕ Çarpışma var'
    hit = next(i for i, f in enumerate(p.result.frames) if f.hits)
    p.slider.setValue(hit)
    hud = p.viewer.annotations.hud
    assert hud.startswith('Adım 1/1 · ') and '°' in hud and 'çarpışma' in hud and p.viewer.annotations.state == 'collision'
    assert 'ÇARPIŞMA' in p.frame_label.text()
    p.direction.setCurrentIndex(1); finish(window, qtbot)           # any change: old result void, badge back to pending
    assert p.result is None and p.result_badge.text() == '○ Kontrol bekliyor' and not p.pdf_button.isEnabled()


def test_tool_cards_share_one_scale_and_name_the_choice(qtbot):
    create_application([])
    d = ToolPicker(tools(), 'punch', 'demo-punch'); qtbot.addWidget(d); d.resize(1040, 720); d.show(); qtbot.wait(30)
    rect = QRectF(0, 0, 200, 150)
    scale = d.common_scale(rect)
    sections = [t.section.polygon().bounds for t in d.tools]
    assert all((b[3]-b[1])*scale <= rect.height() and (b[2]-b[0])*scale <= rect.width() for b in sections)
    assert d.scale_bar_mm() in (5, 10, 20, 25, 50, 100, 200)
    assert d.use_button.text().endswith('DEMO-NARROW')
    d.search.setText('wide'); assert d.use_button.text().endswith('DEMO-WIDE')
    d.search.clear(); d.columns.setCurrentIndex(d.columns.findData(4)); d.resize(640, 480); qtbot.wait(30); d.card_sizes()
    assert d.cards.gridSize().width() >= 170                        # narrow dialog: fewer columns, not cut text


@pytest.mark.parametrize('size', [(820, 560), (1024, 700), (1366, 768), (1920, 1080)])
def test_controls_fit_without_clipping_in_both_themes(window, qtbot, size):
    p = window.pages['press_brake']; p.load_demo('U'); finish(window, qtbot)
    for theme in ('light', 'dark'):
        window.set_theme(theme); window.resize(*size); qtbot.wait(60)
        for w in (p.previous, p.play, p.next, p.speed, p.flat_button, p.formed_button, p.fit_button,
                  p.check_button, p.demo_button, p.up, p.down):
            assert w.isVisible() and w.width() >= w.minimumSizeHint().width(), (theme, size, w.text() if hasattr(w, 'text') else w)
        assert p.viewer.width() >= 150 and p.viewer.height() >= 150
        # Narrow side panel: value tiles stack instead of cutting numbers.
        for tile in p.value_tiles:
            value = tile.findChildren(type(p.values['length']))[-1]
            assert value.width() >= value.fontMetrics().horizontalAdvance(value.text()) - 1, (theme, size, value.text())
