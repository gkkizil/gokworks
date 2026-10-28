"""Shared shell interactions and empty results preserve the real page/model state."""

import pytest
from PySide6.QtCore import Qt
from gui_qt.app import MainWindow, create_application
from gui_qt.components import ResultsPanel


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([])
    w = MainWindow(tmp_path / 'settings.json')
    def before_close(widget):
        widget.closing = True
        if widget.jobs.busy:
            widget.jobs.cancel()
            qtbot.waitUntil(lambda: not widget.jobs.busy, timeout=8000)
    qtbot.addWidget(w, before_close_func=before_close)
    w.resize(1024, 700); w.show()
    return w


def test_search_keyboard_no_matches_and_reset_keep_existing_page_inputs(window, qtbot):
    w = window
    original = dict(w.pages)
    w.pages['weight'].form.set_value('length', '2350')
    w.focus_module_search()
    w.browser.search.setText('İSİMLENDİRME')
    qtbot.keyClick(w.browser.search, Qt.Key_Return)
    assert w.mode == 'naming' and w.navigation['naming'].hasFocus()
    w.focus_module_search(); w.browser.search.setText('no-such-tool')
    assert w.browser.search_feedback.isVisible() and w.browser.reset_search.isVisible()
    qtbot.keyClick(w.browser.search, Qt.Key_Return)
    assert w.mode == 'naming'
    w.browser.reset_search.click()
    assert not w.browser.search.text() and not w.browser.search_feedback.isVisible()
    w.browser.search.setText('tork'); qtbot.keyClick(w.browser.search, Qt.Key_Down)
    assert w.navigation['bolt_torque'].hasFocus()
    w.focus_module_search(); qtbot.keyClick(w.browser.search, Qt.Key_Escape)
    assert w.browser.search.text() == '' and w.pages == original
    assert w.pages['weight'].form.value('length') == '2350' and not w.jobs.busy


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_long_breadcrumb_yields_to_toolbar_controls_and_selected_nav_is_reachable(window, qtbot, theme):
    w = window; w.set_theme(theme); w.resize(820, 560)
    w.navigate('geometric_tolerances'); qtbot.wait(50)
    assert w.workspace_context.text() == 'Hesaplar / Geometrik toleranslar'
    assert w.workspace_context.toolTip() == w.workspace_context.text()
    assert not w.workspace_caption_action.isVisible()
    for action in w.workbench_bar.actions():
        widget = w.workbench_bar.widgetForAction(action)
        if widget is not None and action.isVisible():
            assert widget.isVisible()
            assert w.workbench_bar.rect().contains(widget.mapTo(w.workbench_bar, widget.rect().bottomRight()))
    nav = w.navigation['geometric_tolerances']; viewport = w.browser.menu_scroll.viewport()
    assert viewport.rect().contains(nav.mapTo(viewport, nav.rect().center()))
    w.resize(1440, 900); qtbot.wait(30)
    assert w.workspace_caption_action.isVisible()


def test_empty_results_distinguish_new_work_filtered_data_and_running_jobs(qtbot, monkeypatch):
    create_application([])
    panel = ResultsPanel(); qtbot.addWidget(panel); panel.resize(600, 400); panel.show()
    assert panel.empty_state.isVisible() and panel.empty_state.reset.isHidden()
    panel.files(['A.SLDPRT', 'B.SLDPRT'])
    assert not panel.empty_state.isVisible()
    opened = []
    monkeypatch.setattr(panel, 'show_details', lambda index: opened.append(index.row()))
    panel.activateWindow(); panel.table.setCurrentIndex(panel.proxy.index(0, 0))
    panel.table.setFocus(); qtbot.wait(20); qtbot.keyClick(panel.table, Qt.Key_Return)
    assert opened == [0]
    panel.search.setFocus(); qtbot.keyClick(panel.search, Qt.Key_Return)
    assert opened == [0]  # Enter in a search field must not open a row dialog.
    panel.search.setText('missing'); qtbot.waitUntil(lambda: panel.proxy.rowCount() == 0)
    assert panel.empty_state.isVisible() and panel.empty_state.reset.isVisible()
    panel.empty_state.reset.click()
    assert panel.proxy.rowCount() == 2 and panel.model.rowCount() == 2
    panel.filter.setCurrentIndex(panel.filter.findData('error'))
    assert panel.empty_state.isVisible()
    panel.empty_state.reset.click()
    assert panel.filter.currentData() is None and panel.proxy.rowCount() == 2
    panel.clear(); panel.set_busy(True)
    assert panel.empty_state.title.text() == 'İşlem sürüyor…'
    assert not panel.empty_state.reset.isVisible() and not panel.clear_button.isEnabled()
    panel.set_busy(False)
    assert panel.empty_state.title.text() == 'Dosyalar burada görünecek'


def test_converter_custom_model_and_counter_keep_empty_feedback_in_sync(window):
    window.navigate('cad_converter')
    panel = window.pages['cad_converter'].results
    panel.tabs.setCurrentWidget(panel.table)
    assert panel.empty_state.isVisible()
    panel.filter.setCurrentIndex(panel.filter.findData('error'))
    panel.job_row(dict(source='Example.SLDPRT', configuration='Default',
                       format='STEP', status='success', detail='UI fixture'), completed=True)
    assert panel.empty_state.isVisible() and panel.empty_state.reset.isVisible()
    panel.empty_state.reset.click()
    assert not panel.empty_state.isVisible() and panel.proxy.rowCount() == 1
    assert '1 tamamlanan' in panel.counter.text()
    panel.filter.setCurrentIndex(panel.filter.findData('error'))
    assert panel.empty_state.isVisible() and panel.empty_state.reset.isVisible()
    panel.empty_state.reset.click()
    assert not panel.empty_state.isVisible() and panel.model.rowCount() == 1
