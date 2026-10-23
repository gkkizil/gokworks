"""PDF ekranının klasör ve seçenek tercihleri."""

import json
import os
from pathlib import Path
from tempfile import mkstemp
from threading import Lock
import time

SETTINGS_PATH = Path(os.environ.get("APPDATA", str(Path.home()))) / "GOKWORKS" / "settings.json"
_publish_lock = Lock()


def _publish(temporary, path):
    # Windows replacement may briefly deny access while another instance or a
    # virus scanner holds the destination. Serialize local publishers and retry
    # only the Windows sharing/access errors, with a bounded 100 ms backoff.
    with _publish_lock:
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                return
            except PermissionError as error:
                if getattr(error, 'winerror', None) not in (5, 32, 33) or attempt == 4:
                    raise
                time.sleep(.01*(attempt+1))


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
        _publish(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
