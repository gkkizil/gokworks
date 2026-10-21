"""PDF ekranının klasör ve seçenek tercihleri."""

import json
import os
from pathlib import Path

SETTINGS_PATH = Path(os.environ.get("APPDATA", str(Path.home()))) / "GOKWORKS" / "settings.json"


def load_settings(path=SETTINGS_PATH):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data, path=SETTINGS_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)
