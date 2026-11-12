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
    assert v.bend_annotations is not v.overlay and hasattr(v.overlay, 'face_at')
    QApplication.sendEvent(v, QEvent(QEvent.Leave))
    for point in (QPointF(v.width()-40, 40), QPointF(v.width()/2, v.height()/2)):
        for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            QApplication.sendEvent(v, QMouseEvent(kind, point, v.mapToGlobal(point.toPoint()), Qt.LeftButton,
                                                  Qt.LeftButton if kind == QEvent.MouseButtonPress else Qt.NoButton, Qt.NoModifier))
    move = QMouseEvent(QEvent.MouseMove, QPointF(5, 5), v.mapToGlobal(QPoint(5, 5)), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
    QApplication.sendEvent(v, move); qtbot.wait(30)
    assert v.bend_annotations.isVisible() and v.frame is not None


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
    hud = p.viewer.bend_annotations.hud
    assert hud.startswith('Adım 1/1 · ') and '°' in hud and 'çarpışma' in hud and p.viewer.bend_annotations.state == 'collision'
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


def test_library_actions_share_a_collapsed_section_so_step_cards_keep_their_height(window, qtbot):
    p = window.pages['press_brake']; p.load_demo('U'); finish(window, qtbot)
    window.resize(820, 560); qtbot.wait(60)
    assert not p.dxf_section.is_expanded() and not p.catalog_button.isVisible() and not p.import_tool.isVisible()
    first = p.bends.visualItemRect(p.bends.item(0))
    assert first.height() > 60 and p.bends.viewport().height() >= first.height()+40   # more than one card in view
    p.dxf_section.set_expanded(True); qtbot.wait(20)
    assert p.catalog_button.isVisible() and p.catalog_button.isEnabled() and p.import_tool.isVisible()


def test_catalogue_cards_use_turkish_decimals_and_no_scale_bar_without_a_drawing():
    from modules.press_brake.sources import manufacturer_tools
    from modules.press_brake.tool_picker import card_spec
    rolleri = next(t for t in manufacturer_tools() if t.code == '04600')
    assert rolleri.section is None and card_spec(rolleri).endswith('H 104,91 mm') and '.' not in card_spec(rolleri)


def click_card_button(p, row, field):
    from modules.press_brake.cards import CARD as _C
    option = QStyleOptionViewItem(); option.font = p.bends.font(); option.rect = p.bends.visualItemRect(p.bends.item(row))
    card = p.bends.item(row).data(_C); rect = p.step_cards.card_rect(option)
    box = next(b for kind, b, f in p.step_cards.layout(card, rect.width(), option.font)[0] if kind == 'button' and f == field)
    point = box.translated(rect.left(), rect.top()).center().toPoint()
    from PySide6.QtTest import QTest
    QTest.mouseClick(p.bends.viewport(), Qt.LeftButton, Qt.NoModifier, point)


def test_in_card_direction_and_flip_buttons_change_the_plan_like_the_side_panel(window, qtbot):
    p = window.pages['press_brake']; p.load_demo('U'); finish(window, qtbot)
    revision = p.plan.revision
    click_card_button(p, 1, 'reverse'); finish(window, qtbot)
    assert p.plan.steps[1].reverse and not p.plan.steps[0].reverse and p.plan.revision == revision+1
    assert p.bends.currentRow() == 1 and p.direction.currentData() is True and p.result is None
    click_card_button(p, 1, 'flip'); finish(window, qtbot)
    assert p.plan.steps[1].orientation == 180 and p.orientation.currentData() == 180
    card = p.bends.item(1).data(CARD)
    assert card['reverse'] and card['flip'] and 'Yön ters' in p.bends.item(1).text()
    click_card_button(p, 1, 'flip'); finish(window, qtbot)
    assert p.plan.steps[1].orientation == 0


def test_dragging_a_card_reorders_the_plan(window, qtbot):
    p = window.pages['press_brake']; p.load_demo('U'); finish(window, qtbot)
    before = [s.bend for s in p.plan.steps]
    p.bends.setCurrentRow(1)
    p.bends.model().moveRow(p.bends.rootIndex(), 1, p.bends.rootIndex(), 0)   # what an internal drop does
    qtbot.waitUntil(lambda: [s.bend for s in p.plan.steps] == before[::-1], timeout=5000); finish(window, qtbot)
    assert p.result is None and [p.bends.item(i).data(Qt.UserRole) for i in range(2)] == before[::-1]
    assert p.bends.dragDropMode() == p.bends.DragDropMode.InternalMove


@pytest.mark.timeout(240)
def test_step_badges_follow_the_playback_position(window, qtbot):
    p = window.pages['press_brake']; p.load_demo('U'); finish(window, qtbot)
    assert all(p.bends.item(i).data(CARD)['progress'] is None for i in range(2))   # nothing played before a check
    p.calculate(); finish(window, qtbot, 200000)
    second = next(i for i, f in enumerate(p.result.frames) if f.step == 1)
    p.slider.setValue(0)
    assert [p.bends.item(i).data(CARD)['progress'] for i in range(2)] == ['current', 'todo']
    p.slider.setValue(second)
    assert [p.bends.item(i).data(CARD)['progress'] for i in range(2)] == ['done', 'current']
    assert 'oynatıldı' in p.bends.item(0).text()


def test_target_angle_controls_change_the_step_and_reset_to_cad(window, qtbot):
    p = window.pages['press_brake']; p.load_demo('U'); finish(window, qtbot)
    bend = p.plan.bend(p.plan.steps[0].bend); p.bends.setCurrentRow(0); finish(window, qtbot)
    assert p.target.value() == bend.inside_angle and not p.target_cad.isEnabled()
    p.target_plus.click(); finish(window, qtbot)
    assert p.plan.steps[0].target == bend.inside_angle+1 and p.result is None
    assert p.values['inside'].text() == f'{bend.inside_angle+1:g}°' and p.target_cad.isEnabled()
    assert f'(CAD {bend.inside_angle:g}°)' in p.bends.item(0).data(CARD)['detail']
    p.target.setValue(0.5)                                          # below range: clamped to 1°, still valid
    finish(window, qtbot)
    p.target_cad.click(); finish(window, qtbot)
    assert p.plan.steps[0].target is None and p.target.value() == bend.inside_angle


def test_flat_plan_numbers_bend_lines_in_order_and_click_selects_the_step(window, qtbot):
    from PySide6.QtTest import QTest
    p = window.pages['press_brake']; p.load_demo('U'); finish(window, qtbot)
    p.flat_plan.parentWidget().parentWidget().parentWidget().ensureWidgetVisible(p.flat_plan); qtbot.wait(30)
    lines = p.flat_plan.lines()
    assert [i for i, _, _ in lines] == [0, 1] and [b.id for _, b, _ in lines] == [s.bend for s in p.plan.steps]
    to = p.flat_plan.mapping(); _, _, (a, b) = lines[1]
    on_line = ((to(a)+to(b))/2+QPointF(25, 0) if abs(to(a).y()-to(b).y()) < 1 else (to(a)+to(b))/2+QPointF(0, 25)).toPoint()
    assert p.flat_plan.step_at(QPointF(on_line)) == 1
    QTest.mouseClick(p.flat_plan, Qt.LeftButton, Qt.NoModifier, on_line); finish(window, qtbot)
    assert p.bends.currentRow() == 1 and p.flat_plan.current == 1
    p.down.setFocus(); p.bends.setCurrentRow(0); p.down.click(); finish(window, qtbot)   # order follows the plan
    assert [b.id for _, b, _ in p.flat_plan.lines()] == [s.bend for s in p.plan.steps]
    assert p.flat_plan.step_at(QPointF(2, 2)) is None


@pytest.mark.timeout(300)
def test_checked_motion_exports_as_an_mp4_video(window, qtbot, tmp_path):
    from modules.press_brake.video import video_codec
    p = window.pages['press_brake']; p.load_demo('L120'); finish(window, qtbot)
    assert not p.video_button.isEnabled()                         # nothing checked yet
    p.calculate(); finish(window, qtbot, 200000)
    assert p.video_button.isEnabled()
    if video_codec() is None:
        pytest.skip('Qt Multimedia has no MP4 encoder on this machine')
    target = tmp_path/'animasyon.mp4'; target.write_bytes(b'old')    # replaced only when the recording finished
    p.speed.setCurrentIndex(2); p.export_video(str(target))
    qtbot.waitUntil(lambda: p.status_text.startswith(('Video kaydedildi', 'Video kaydedilemedi')), timeout=200000)
    assert p.status_text.startswith('Video kaydedildi'), p.status_text
    data = target.read_bytes()
    assert data[4:8] == b'ftyp' and len(data) > 10000 and '24 kare/s' in p.status_text
    assert not list(tmp_path.glob('.*kayit.mp4')) and p.video_button.isEnabled()


def test_video_frames_carry_the_step_read_out_and_scope(qapp):
    # QPainter text needs an application even in a fresh, standalone batch.
    import threading
    from modules.press_brake.demo import load_demo
    from modules.press_brake.service import run
    from modules.press_brake.video import WIDTH, HEIGHT, caption, render_frame
    from modules.dxf_dwg.preview.viewer import Camera
    plan = load_demo('L120'); result = run(plan, threading.Event())
    frame = result.frames[len(result.frames)//2]
    image = render_frame(plan, result, frame, Camera().state(), threading.Event())
    assert (image.width(), image.height()) == (WIDTH, HEIGHT)
    assert caption(plan, frame).startswith('Adım 1/1 · ') and '°' in caption(plan, frame)


@pytest.mark.timeout(240)
def test_clicking_the_selected_card_after_flat_view_returns_to_the_step(window, qtbot):
    from PySide6.QtTest import QTest
    p = window.pages['press_brake']; p.load_demo('L120'); finish(window, qtbot)
    def click_card():
        rect = p.bends.visualItemRect(p.bends.item(0))
        QTest.mouseClick(p.bends.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(rect.center().x(), rect.top()+12))
    p.flat_button.click(); finish(window, qtbot)
    assert p.viewer.frame is None and p.view_mode == 'flat'
    click_card(); finish(window, qtbot)                                  # before a check: the step preview comes back
    assert p.view_mode == 'step' and p.viewer.frame is not None
    p.calculate(); finish(window, qtbot, 200000)
    p.formed_button.click(); finish(window, qtbot)
    assert p.viewer.frame is None
    click_card(); finish(window, qtbot)                                  # after a check: the checked frames come back
    assert p.viewer.frame is not None and p.viewer.frame.step == 0
    p.flat_button.click(); p.slider.setValue(3)                          # the slider leaves the flat view too
    assert p.view_mode == 'step' and p.viewer.frame is p.result.frames[3]
