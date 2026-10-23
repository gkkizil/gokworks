"""PDF ekranının klasör ve seçenek tercihleri."""

import json
import os
from pathlib import Path
from tempfile import mkstemp

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
    # Serialize before touching disk, and never claim an unrelated *.tmp file.
    content = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    fd, name = mkstemp(prefix='.gokworks-settings-', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
