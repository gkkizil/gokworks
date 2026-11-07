"""Manual menu input must survive editor focus changes and damaged preferences."""

import gc

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QLineEdit

from gui_qt.app import MainWindow, create_application
from shared.settings import save_settings


@pytest.fixture
def window(qtbot, tmp_path):
    create_application([])
    widget = MainWindow(tmp_path / 'settings.json')
    qtbot.addWidget(widget)
    widget.resize(1366, 768)
    widget.show()
    widget.navigate('k_factor')
    yield widget
    assert not widget.jobs.busy
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


@pytest.mark.parametrize('command', ['scan_button', 'apply_button'])
def test_last_typed_cell_value_is_committed_before_the_command(window, qtbot, monkeypatch, command):
    page = window.pages['k_factor']
    page.rows_model.replace([dict(thickness='2', k='0,274', r='1,5')])
    index = page.rows_model.index(0, 1)
    page.rows.setCurrentIndex(index)
    page.rows.edit(index)
    editor = page.rows.findChild(QLineEdit)
    assert editor is not None
    editor.setFocus()
    editor.selectAll()
    qtbot.keyClicks(editor, '0,417')
    calls = []
    monkeypatch.setattr(page, 'start_operation', lambda *args: calls.append(args))
    qtbot.mouseClick(getattr(page, command), Qt.LeftButton)
    assert len(calls) == 1
    assert calls[0][0].rows[0].k_factor == .417
    assert calls[0][1] is (command == 'scan_button')
    assert page.settings.get('kr_manual_k') == '0,417'


def test_invalid_last_cell_cannot_start_an_assignment(window, qtbot, monkeypatch):
    page = window.pages['k_factor']
    page.rows_model.replace([dict(thickness='2', k='0,274', r='1,5')])
    index = page.rows_model.index(0, 1)
    page.rows.setCurrentIndex(index)
    page.rows.edit(index)
    editor = page.rows.findChild(QLineEdit)
    editor.setFocus()
    editor.selectAll()
    qtbot.keyClicks(editor, '1,1')
    calls = []
    monkeypatch.setattr(page, 'start_operation', lambda *args: calls.append(args))
    qtbot.mouseClick(page.apply_button, Qt.LeftButton)
    assert not calls
    assert page.tabs.currentIndex() == 0
    assert page.status_kind == 'error'


def test_deeply_nested_saved_row_string_cannot_crash_the_kr_page(qtbot, tmp_path):
    create_application([])
    path = tmp_path / 'settings.json'
    raw = '[' * 10000 + '0' + ']' * 10000
    save_settings({'kr_manual_rows': raw, 'kr_manual_thickness': '2',
                   'kr_manual_k': '0,274', 'kr_manual_r': '1,5', 'custom_setting': 'koru'}, path)
    widget = MainWindow(path)
    qtbot.addWidget(widget)
    widget.navigate('k_factor')
    assert widget.pages['k_factor'].rows_model.rowCount() == 1
    assert widget.pages['k_factor'].recipe().rows[0].k_factor == .274
    assert widget.settings.get('custom_setting') == 'koru'
    assert widget.settings.get('kr_manual_rows') == raw
    widget.close()
