"""Read and export notices embedded in either a folder or single-file package."""

import os
from pathlib import Path
import sys
import tempfile
import zipfile

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
    QPlainTextEdit, QFileDialog, QMessageBox)
from .components import button


def license_files():
    root = Path(__file__).resolve().parents[1]
    directory = root/'licenses' if getattr(sys, 'frozen', False) else root/'packaging/licenses'
    files = {p.relative_to(directory).as_posix():p for p in directory.rglob('*') if p.is_file()}
    if not getattr(sys, 'frozen', False):
        files['THIRD_PARTY_NOTICES.md'] = root/'docs/THIRD_PARTY_NOTICES.md'
    return files


def export_licenses(path, files):
    path = Path(path)
    with tempfile.TemporaryDirectory(prefix='.gokworks-licenses-', dir=path.parent) as folder:
        temporary = Path(folder)/'licenses.zip'
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, source in files.items():archive.write(source, name)
        os.replace(temporary, path)


class LicensesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('GOKWORKS · Lisanslar')
        self.resize(780, 600)
        self.files = license_files()
        layout = QVBoxLayout(self)
        self.picker = QComboBox()
        self.picker.addItems(sorted(self.files))
        layout.addWidget(self.picker)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text, 1)
        actions = QHBoxLayout()
        actions.addWidget(button('Lisansları kaydet', self.export))
        actions.addStretch()
        actions.addWidget(button('Kapat', self.accept))
        layout.addLayout(actions)
        self.picker.currentTextChanged.connect(self.display)
        self.picker.setCurrentText('THIRD_PARTY_NOTICES.md')
        self.display(self.picker.currentText())

    def display(self, name):
        try:self.text.setPlainText(self.files[name].read_text(encoding='utf-8', errors='replace'))
        except (KeyError, OSError):self.text.setPlainText('Lisans metni okunamadı.')

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Lisansları kaydet', 'GOKWORKS-Lisanslar.zip', 'ZIP (*.zip)')
        if not path:return
        try:export_licenses(path, self.files)
        except OSError as error:QMessageBox.warning(self, 'Kaydedilemedi', str(error))
