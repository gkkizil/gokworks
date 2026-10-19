"""Local fatal-error traces without CAD content or frame-local variables."""

import atexit
from datetime import datetime, timezone
import faulthandler
import os
from pathlib import Path
import sys
import tempfile
import traceback
from uuid import uuid4


_stream = None
_path = None
_original_hook = None
_exception_hook = None


def log_directory():
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_STATE_HOME')
    return (Path(base) if base else Path.home()/'.local/state')/'GOKWORKS/logs'


def new_log_path(role):
    for folder in (log_directory(), Path(tempfile.gettempdir())/'GOKWORKS/logs'):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            previous = sorted((p for p in folder.glob('GOKWORKS-*.log') if p != _path),
                              key=lambda p: p.stat().st_mtime, reverse=True)
            for old in previous[9:]:
                try:
                    old.unlink()
                except OSError:
                    pass
            stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
            return folder/f'GOKWORKS-{role}-{stamp}-{uuid4().hex[:8]}.log'
        except OSError:
            continue
    return None


def record(message, path=None):
    try:
        target = Path(path) if path else _path
        if target is None or (target.exists() and target.stat().st_size >= 1024*1024):
            return
        with target.open('a', encoding='utf-8') as stream:
            stream.write(datetime.now(timezone.utc).isoformat()+' '+message+'\n')
    except OSError:
        pass


def snapshot(label):
    """Capture Python stacks before a native library aborts (not just on SIGSEGV)."""
    record(label)
    try:
        if _stream is not None and _stream.tell() < 1024*1024:
            faulthandler.dump_traceback(file=_stream, all_threads=True)
            _stream.flush()
    except (OSError, ValueError, RuntimeError):
        pass


def enable(role, path=None):
    global _stream, _path, _original_hook, _exception_hook
    if _stream is not None:
        return _path
    target = Path(path) if path else new_log_path(role)
    if target is None:
        return None
    stream = None
    try:
        stream = target.open('a', encoding='utf-8', buffering=1)
        faulthandler.enable(file=stream, all_threads=True)
    except (OSError, RuntimeError):
        if stream is not None:
            stream.close()
        return None
    _stream, _path = stream, target
    record(f'role={role} pid={os.getpid()} python={sys.version_info.major}.{sys.version_info.minor}')
    _original_hook = sys.excepthook

    def exception(kind, value, tb):
        # Do not dump model contents, Python locals, or exception text that may
        # embed commercially sensitive source paths.
        record('unhandled_exception='+kind.__name__)
        try:
            if _stream is not None and _stream.tell() < 1024*1024:
                traceback.print_tb(tb, file=_stream)
                _stream.flush()
        except (OSError, ValueError):
            pass
        if sys.stderr is not None:
            _original_hook(kind, value, tb)

    _exception_hook = exception
    sys.excepthook = exception
    atexit.register(close)
    return target


def close():
    global _stream, _path, _original_hook, _exception_hook
    if _stream is not None:
        record('normal_python_shutdown')
        faulthandler.disable()
        _stream.close()
        _stream = None
    if _exception_hook is not None and sys.excepthook is _exception_hook:
        sys.excepthook = _original_hook
    _path = _original_hook = _exception_hook = None
