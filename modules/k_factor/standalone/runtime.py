"""Writable per-user MakePy cache for the standalone frozen Windows tool."""

import os
from pathlib import Path
import sys
import threading

_cache_lock = threading.Lock()
_configured_cache = None


def prepare_generated_cache():
    global _configured_cache
    if not getattr(sys, "frozen", False):
        return None
    with _cache_lock:
        if _configured_cache is not None:
            return _configured_cache
        import win32com
        import win32com.gen_py
        from win32com.client import gencache

        user_data = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or Path.home() / "AppData/Local")
        cache = user_data / "GOKWORKS/KR-Deneme/com-cache" / f"py{sys.version_info.major}{sys.version_info.minor}-pywin32-312"
        cache.mkdir(parents=True, exist_ok=True)
        # PyInstaller's bundle directory is temporary. Generated interfaces must
        # remain importable from an ordinary writable Python package directory.
        win32com.__gen_path__ = str(cache)
        win32com.gen_py.__path__ = [str(cache)]
        gencache.is_readonly = False
        gencache.is_zip = False
        gencache.GetGeneratePath()
        gencache.Rebuild(verbose=0)
        _configured_cache = cache
        return cache
