"""QA (2026-11-03): CSV reports never leave a half-written user file."""

import os

import pytest

from shared import files
from shared.files import write_csv_atomic, write_text_atomic


def test_csv_is_excel_friendly_and_complete(tmp_path):
    path = write_csv_atomic(tmp_path / 'rapor.csv', ('Alan', 'Değer'), [('Kütle', '1,5 kg'), ('Not', 'a;b "c"')])
    raw = path.read_bytes()
    assert raw.startswith(b'\xef\xbb\xbf')                     # BOM: Excel reads Turkish characters
    assert raw.decode('utf-8-sig').splitlines() == ['Alan;Değer', 'Kütle;1,5 kg', 'Not;"a;b ""c"""']


def test_failed_publish_keeps_the_existing_file_and_no_temporary(tmp_path, monkeypatch):
    target = tmp_path / 'rapor.csv'
    target.write_text('ESKİ RAPOR', encoding='utf-8')

    def deny(temporary, path):
        raise PermissionError(13, 'locked')
    monkeypatch.setattr(files, '_publish', deny)
    with pytest.raises(PermissionError):
        write_csv_atomic(target, ('Alan',), [('x',)])
    assert target.read_text(encoding='utf-8') == 'ESKİ RAPOR'
    assert os.listdir(tmp_path) == ['rapor.csv']


def test_unencodable_text_fails_before_touching_disk(tmp_path):
    target = tmp_path / 'r.txt'
    target.write_text('eski', encoding='utf-8')
    with pytest.raises(UnicodeEncodeError):
        write_text_atomic(target, 'ğ', encoding='ascii')
    assert target.read_text(encoding='utf-8') == 'eski' and os.listdir(tmp_path) == ['r.txt']


def test_calculation_page_report_uses_the_atomic_writer(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from gui_qt.app import MainWindow, create_application
    create_application([])
    window = MainWindow(tmp_path / 'settings.json')
    qtbot.addWidget(window)
    window.navigate('bolt')
    page = window.pages['bolt']
    page.update_result()
    target = tmp_path / 'civata.csv'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', staticmethod(lambda *a, **k: (str(target), '')))
    page.save_report()
    import csv
    with target.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.reader(stream, delimiter=';'))
    assert rows[0] == ['Alan', 'Değer'] and rows[1:] == [list(map(str, row)) for row in page.report]
