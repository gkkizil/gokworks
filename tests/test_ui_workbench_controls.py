"""Shared workbench controls: sketch view, panel layout, status tones and module keys."""

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from gui_qt.app import MainWindow, create_application
from gui_qt.components import BasePage
from gui_qt.diagrams import EngineeringDiagram


def window(qtbot, tmp_path, name='settings.json'):
    create_application([])
    w = MainWindow(tmp_path / name)
    w.resize(1366, 768)
    qtbot.addWidget(w)
    w.show()
    return w


def wheel(view, delta, modifiers=Qt.NoModifier):
    point = QPointF(view.viewport().rect().center())
    event = QWheelEvent(point, view.viewport().mapToGlobal(point), QPoint(), QPoint(0, delta),
                        Qt.NoButton, modifiers, Qt.NoScrollPhase, False)
    view.wheelEvent(event)
    return event


def test_sketch_view_zooms_with_ctrl_wheel_keeps_zoom_and_fits(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    w.navigate('bolt')
    page = w.pages['bolt']
    view = page.diagrams['dimensions']
    assert isinstance(view, EngineeringDiagram) and not view.zoomed
    plain = wheel(view, 120)
    assert not plain.isAccepted() and not view.zoomed           # plain wheel scrolls the page
    wheel(view, 120, Qt.ControlModifier)
    assert view.zoomed and view.dragMode() == EngineeringDiagram.ScrollHandDrag
    zoom = view.zoom
    page.form.set_value('metric', 'M12')
    page.update_result()
    assert view.zoom == zoom                                     # value change keeps the user's zoom
    page.fit_button.click()
    assert not view.zoomed and view.dragMode() == EngineeringDiagram.NoDrag
    view.zoom_by(1.2)
    qtbot.keyClick(view, Qt.Key_0)
    assert not view.zoomed
    qtbot.keyClick(view, Qt.Key_Plus)
    assert view.zoomed
    qtbot.keyClick(view, Qt.Key_Minus)
    assert not view.zoomed                                       # back at the fitted minimum
    for _ in range(40):
        view.zoom_by(2)
    assert view.zoom == EngineeringDiagram.ZOOM_LIMITS[1]
    qtbot.mouseDClick(view.viewport(), Qt.LeftButton)
    assert not view.zoomed


def test_calculation_inputs_can_be_hidden_and_the_choice_persists(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    w.navigate('weight')
    page = w.pages['weight']
    assert page.input_card.isVisible() and page.inputs_button.text() == 'Parametreleri gizle'
    page.inputs_button.click()
    assert page.input_card.isHidden() and page.inputs_button.text() == 'Parametreleri göster'
    assert page.diagrams['section'].isVisible()                  # the workspace keeps the room
    w.close()
    again = window(qtbot, tmp_path)
    again.navigate('weight')
    restored = again.pages['weight']
    assert restored.input_card.isHidden()
    QApplication.processEvents()
    restored.toggle_inputs()
    assert restored.input_card.isVisible()


def test_splitter_position_is_remembered(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    w.navigate('bolt')
    page = w.pages['bolt']
    QApplication.processEvents()
    total = sum(page.splitter.sizes())
    page.splitter.setSizes([total // 2, total - total // 2])
    page.remember_split()
    stored = w.settings.get('layout/bolt_split')
    assert stored == page.splitter.sizes()


def test_status_tones_distinguish_success_warning_and_error(qtbot, tmp_path):
    assert BasePage.status_tone('Kaydedildi: rapor.pdf') == 'success'
    assert BasePage.status_tone('Teknik resim kısmen tamamlandı') == 'warning'
    assert BasePage.status_tone('Kaydedildi', error=True) == 'error'
    assert BasePage.status_tone('Değerler güncel') == 'muted'
    # Batch summaries: zero counts do not make a clean run look like a warning.
    assert BasePage.status_tone('Tamamlandı · 4 başarılı, 0 uyarılı, 0 atlanan, 0 hatalı') == 'success'
    assert BasePage.status_tone('Tamamlandı · 3 başarılı, 1 uyarılı, 0 atlanan, 0 hatalı') == 'warning'
    assert BasePage.status_tone('Tamamlandı · 3 başarılı, 0 uyarılı, 0 atlanan, 1 hatalı') == 'warning'
    assert BasePage.status_tone('Tamamlandı · 10 başarılı, 0 uyarılı, 2 atlanan, 0 hatalı') == 'warning'
    assert BasePage.status_tone('Değerler güncel', tone='success') == 'success'
    w = window(qtbot, tmp_path)
    w.navigate('weight')
    page = w.pages['weight']
    page.set_status('Listeye eklendi: Kiriş')
    assert w.global_status.property('role') == 'success'
    page.set_status('Ölçü geçersiz', True)
    assert w.global_status.property('role') == 'error'


def test_ctrl_page_keys_move_through_modules_in_sidebar_order(qtbot, tmp_path):
    w = window(qtbot, tmp_path)
    order = [key for key in w.browser.buttons if key in w.pages]
    w.navigate(order[0])
    w.navigate_relative(1)
    assert w.mode == order[1]
    w.navigate_relative(-2)
    assert w.mode == order[-1]                                   # wraps around
    assert w.browser.buttons[order[-1]].isChecked()
