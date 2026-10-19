"""Optional user-selected replacements for the LGPL Qt/PySide libraries."""

import os
from pathlib import Path
import sys

_dll_handles = []
_configured = None


def configure_libraries():
    global _configured
    value = os.environ.get('GOKWORKS_LIBRARY_DIR')
    if not value:
        return
    root = Path(value).resolve()
    if not all((root/name/'__init__.py').is_file() for name in ('PySide6', 'shiboken6')):
        raise RuntimeError('GOKWORKS_LIBRARY_DIR, uyumlu PySide6 ve shiboken6 paketlerini içermeli.')
    if str(root) not in sys.path:sys.path.insert(0, str(root))
    if os.name == 'nt' and _configured != root:
        for folder in (root/'PySide6', root/'shiboken6', root/'PySide6/Qt/bin'):
            if folder.is_dir():
                _dll_handles.append(os.add_dll_directory(str(folder)))
    _configured = root
    for plugins in (root/'PySide6/plugins', root/'PySide6/Qt/plugins'):
        if plugins.is_dir():
            os.environ['QT_PLUGIN_PATH'] = str(plugins)
            break
