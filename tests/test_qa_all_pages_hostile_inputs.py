"""QA sweep (2026-11-03): every page, every tab, hostile values, no unhandled exception.

Blocking dialogs are neutralised, so file pickers return "cancelled". Buttons that
reach SOLIDWORKS, the file system or exports are not clicked here; their own
module tests cover them. Calculation buttons are clicked with hostile inputs.
"""

import sys
import traceback

import pytest
from PySide6.QtWidgets import (QAbstractSpinBox, QCheckBox, QComboBox, QDialog, QFileDialog, QLineEdit,
                               QMenu, QMessageBox, QPushButton, QTabWidget, QToolButton)

from gui_qt.app import MODULES, MainWindow, create_application

HOSTILE = ('', '-1', '0', '-0', '1e308', '1e-300', 'abc', '1.000', '1,5', '1.234,5', 'ğüşİı',
           '9' * 80, 'nan', 'inf', '  12  ')
UNSAFE_WORDS = ('Çık', 'Kapat', 'SolidWorks', 'Aç', 'Kaydet', 'Dışa', 'Aktar', 'Seç', 'Göz', 'PDF', 'DXF',
                'STEP', 'Excel', 'CSV', 'Rapor', 'Yazdır', 'Bağlan', 'Tara', 'Klasör', 'Dosya', 'Önizle',
                'Başlat', 'Oluştur', 'Gönder', 'Sil', 'indir', 'download')


@pytest.fixture
def quiet_dialogs(monkeypatch):
    for name in ('getOpenFileName', 'getSaveFileName', 'getOpenFileNames'):
        monkeypatch.setattr(QFileDialog, name, staticmethod(lambda *a, **k: ('', '')))
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: ''))
    for name in ('information', 'warning', 'critical', 'question'):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.No))
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: QMessageBox.No)
    monkeypatch.setattr(QDialog, 'exec', lambda self: 0)
    monkeypatch.setattr(QMenu, 'exec', lambda self, *a, **k: None)


@pytest.fixture
def unhandled(monkeypatch):
    seen = []
    monkeypatch.setattr(sys, 'excepthook', lambda kind, value, tb: seen.append(
        ''.join(traceback.format_exception(kind, value, tb))))
    return seen


def _visible(widgets):
    return [w for w in widgets if w.isVisible() and w.isEnabled()]


@pytest.mark.parametrize('key', [key for key, _, _ in MODULES])
def test_page_survives_hostile_inputs_on_every_tab(qtbot, tmp_path, quiet_dialogs, unhandled, key):
    create_application([])
    window = MainWindow(tmp_path / 'settings.json')
    window.resize(1366, 768)
    qtbot.addWidget(window)
    window.show()
    window.navigate(key)
    page = window.pages[key]
    pump = lambda: [qtbot.wait(0) for _ in range(2)]  # noqa: E731
    states = [(None, None)] + [(tabs, i) for tabs in page.findChildren(QTabWidget) for i in range(tabs.count())]
    for tabs, index in states:
        if tabs is not None:
            tabs.setCurrentIndex(index)
            pump()
        edits = [e for e in _visible(page.findChildren(QLineEdit))
                 if not e.isReadOnly() and not isinstance(e.parent(), (QAbstractSpinBox, QComboBox))]
        for edit in edits:
            original = edit.text()
            for value in HOSTILE:
                edit.setText(value)
                edit.editingFinished.emit()
                pump()
            edit.setText(original)
            edit.editingFinished.emit()
        for spin in [s for s in _visible(page.findChildren(QAbstractSpinBox)) if not s.isReadOnly()]:
            for value in HOSTILE:
                spin.lineEdit().setText(value)
                spin.interpretText()
                pump()
            spin.setValue(spin.maximum())
            pump()
            spin.setValue(spin.minimum())
            pump()
        for combo in _visible(page.findChildren(QComboBox)):
            for index_ in range(combo.count()):
                combo.setCurrentIndex(index_)
                pump()
        for box in _visible(page.findChildren(QCheckBox)):
            box.click()
            pump()
            box.click()
        buttons = [b for b in _visible(page.findChildren(QPushButton) + page.findChildren(QToolButton))
                   if b.menu() is None and not any(w.lower() in b.text().lower() for w in UNSAFE_WORDS)]
        for hostile in ('', '-1', '1e308', 'abc'):
            saved = [(edit, edit.text()) for edit in edits]
            for edit, _ in saved:
                edit.setText(hostile)
                edit.editingFinished.emit()
            for button in buttons:
                if button.isVisible() and button.isEnabled():
                    button.click()
                    pump()
            for edit, text in saved:
                edit.setText(text)
                edit.editingFinished.emit()
    pump()
    assert not unhandled, unhandled[0]
