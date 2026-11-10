"""The animation button receiver lives and disconnects with its page."""
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent
from gui_qt.app import create_application, MainWindow


def test_animation_button_sync_preserves_signal_blocking_and_hidden_timer_pause(qtbot, tmp_path):
    create_application([]); window = MainWindow(tmp_path/'settings.json')
    try:
        window.show(); window.navigate('belt_drive'); page = window.pages['belt_drive']
        toggles = []; page.animate.toggled.connect(toggles.append)
        page.canvas.animationChanged.emit(True)
        assert page.animate.isChecked() and not toggles
        page.animate.blockSignals(True); page.canvas.animationChanged.emit(False)
        assert page.animate.signalsBlocked() and not page.animate.isChecked()
        page.animate.blockSignals(False)
        page.animate.click(); qtbot.wait(20)
        window.navigate('pdf'); qtbot.waitUntil(lambda: not page.canvas.timer.isActive(), timeout=1000)
        assert page.canvas.animating and page.animate.isChecked()  # resumes consistently on return
    finally:
        window.close(); window.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert not shiboken6.isValid(page) and not shiboken6.isValid(page.canvas)
