"""Optional user-selected replacements for the LGPL Qt/PySide and GEOS libraries."""

import os
from pathlib import Path
import sys

_dll_handles = []
_configured = None
_geometry_configured = None
_cad_configured = None


def configure_libraries():
    global _configured, _geometry_configured, _cad_configured
    cad = os.environ.get('GOKWORKS_CAD_DIR')
    if cad:
        cad_root = Path(cad).resolve()
        if not (cad_root/'OCP/__init__.py').is_file() or not (cad_root/'cadquery_ocp_proxy/__init__.py').is_file():
            raise RuntimeError('GOKWORKS_CAD_DIR, uyumlu OCP, cadquery_ocp_proxy ve OCCT dinamik kitaplıklarını içermeli.')
        if str(cad_root) not in sys.path:
            sys.path.insert(0,str(cad_root))
        if os.name == 'nt' and _cad_configured != cad_root:
            for folder in (cad_root/'OCP',cad_root/'cadquery_ocp_novtk.libs'):
                if folder.is_dir(): _dll_handles.append(os.add_dll_directory(str(folder)))
        _cad_configured = cad_root
    geometry = os.environ.get('GOKWORKS_GEOMETRY_DIR')
    if geometry:
        geometry_root = Path(geometry).resolve()
        if not (geometry_root/'shapely/__init__.py').is_file():
            raise RuntimeError('GOKWORKS_GEOMETRY_DIR, uyumlu shapely paketini ve GEOS kitaplıklarını içermeli.')
        if str(geometry_root) not in sys.path:
            sys.path.insert(0,str(geometry_root))
        if os.name == 'nt' and _geometry_configured != geometry_root:
            for folder in (geometry_root/'shapely',geometry_root/'shapely.libs'):
                if folder.is_dir(): _dll_handles.append(os.add_dll_directory(str(folder)))
        _geometry_configured = geometry_root
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
