"""Navigating between modules fades the new page in briefly and can be turned off."""

from gui_qt.app import MainWindow, create_application
from gui_qt.transitions import DURATION_MS


def make_window(qtbot, tmp_path):
    create_application([])
    window = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(window)
    window.resize(1200, 800); window.show()
    window.page_transition.headless_allowed = True   # offscreen test platform
    return window


def test_navigation_fades_in_and_never_blocks_input(qtbot, tmp_path):
    window = make_window(qtbot, tmp_path)
    veil = window.page_transition.veil
    window.navigate('weight')
    assert window.stack.currentWidget() is window.pages['weight']   # page switches immediately
    assert veil.isVisible() and veil.get_opacity() > .5
    from PySide6.QtCore import Qt
    assert veil.testAttribute(Qt.WA_TransparentForMouseEvents)
    assert veil.geometry() == window.stack.rect()
    qtbot.waitUntil(lambda: not veil.isVisible(), timeout=DURATION_MS * 10)
    assert veil.get_opacity() == 0
    window.navigate('weight')   # same page: no transition
    assert not veil.isVisible()
    window.settings.flush()


def test_transition_can_be_disabled_and_is_remembered(qtbot, tmp_path):
    window = make_window(qtbot, tmp_path)
    window.set_page_transitions(False)
    window.navigate('bolt')
    assert not window.page_transition.veil.isVisible()
    assert window.settings.get('page_transitions') is False
    window.settings.flush()
    again = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(again)
    assert again.page_transition.enabled is False
    again.settings.flush()


def test_headless_runs_skip_the_animation_by_default(qtbot, tmp_path):
    create_application([])
    window = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(window); window.show()
    window.navigate('iso_fits')
    assert not window.page_transition.veil.isVisible()
    window.settings.flush()


def test_test_runs_disable_the_animation_through_the_environment(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv('GOKWORKS_PAGE_TRANSITIONS', '0')
    create_application([])
    window = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(window); window.show()
    window.navigate('bolt')
    assert window.page_transition.enabled and not window.page_transition.veil.isVisible()
    window.settings.flush()
