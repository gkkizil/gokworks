"""Preserve the existing JSON preferences; use QSettings for Qt window state."""

import json
from pathlib import Path
import shutil
from datetime import datetime

from PySide6.QtCore import QObject, QSettings, QTimer
from shared.settings import SETTINGS_PATH, load_settings, save_settings


class SettingsStore(QObject):
    def __init__(self, path=SETTINGS_PATH, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.values = load_settings(self.path)
        self.qt = QSettings(str(self.path.with_suffix('.qt.ini')), QSettings.IniFormat)
        self.dirty = False
        self.last_error = ''
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self.flush)

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        if self.values.get(key) != value:
            self.values[key] = value
            self.dirty = True
            self.timer.start()

    def flush(self):
        self.timer.stop()
        if not self.dirty:
            return True
        try:
            if self.path.exists():
                try:
                    valid = json.loads(self.path.read_text(encoding='utf-8'))
                    if not isinstance(valid, dict):
                        raise ValueError('Settings root is not an object')
                except (ValueError, UnicodeError):
                    backup = self.path.with_name(f'{self.path.stem}.invalid-{datetime.now():%Y%m%d-%H%M%S-%f}.json')
                    shutil.copy2(self.path, backup)
            save_settings(self.values, self.path)
            self.qt.setValue('migration/schema', 1)
            self.qt.sync()
            self.dirty = False
            self.last_error = ''
            return True
        except OSError as error:
            self.last_error = str(error)
            return False
