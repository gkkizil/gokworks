"""Find candidate SolidWorks assemblies without opening SolidWorks."""

import os
from pathlib import Path
import re
import stat

from modules.naming.exporter import Cancelled


def _check_cancelled(stop):
    if stop is not None and stop.is_set():
        raise Cancelled()


def _read_directory(folder, stop):
    assemblies, subfolders = [], []
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                _check_cancelled(stop)
                if entry.name.startswith('~'):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    subfolders.append(Path(entry.path))
                elif (Path(entry.name).suffix.casefold() == '.sldasm'
                      and entry.is_file(follow_symlinks=False)):
                    assemblies.append(Path(entry.path))
    except OSError as error:
        raise OSError(error.errno,
                      f'Montaj klasörü okunamadı: {folder}. {error.strerror or error}',
                      str(folder)) from error
    _check_cancelled(stop)
    return assemblies, subfolders


def _natural_key(path, folder):
    relative = path.relative_to(folder).as_posix()
    tokens = re.split(r'([0-9]+)', relative.casefold())
    return (tuple((1, int(token)) if token.isascii() and token.isdecimal()
                  else (0, token) for token in tokens),
            relative.casefold(), relative)


def discover_assemblies(folder, stop=None) -> tuple[Path, ...]:
    """Return assemblies in *folder*, or its descendants if none are at its root.

    Results use natural, case-insensitive relative-path ordering. Temporary
    SolidWorks files and symbolic links are ignored. The scan never opens or
    modifies a document. An empty tuple means no assembly was found; unreadable
    directories raise an OSError rather than returning an incomplete list.
    """
    _check_cancelled(stop)
    if folder is None or not str(folder).strip():
        raise ValueError('Montajın bulunduğu klasörü seçin.')
    folder = Path(folder).expanduser().absolute()
    try:
        mode = folder.stat().st_mode
    except FileNotFoundError as error:
        raise ValueError(f'Montaj klasörü bulunamadı: {folder}') from error
    except OSError as error:
        raise OSError(error.errno,
                      f'Montaj klasörüne erişilemedi: {folder}. {error.strerror or error}',
                      str(folder)) from error
    if not stat.S_ISDIR(mode):
        raise ValueError(f'Montaj kaynağı bir klasör olmalıdır: {folder}')

    assemblies, pending = _read_directory(folder, stop)
    if assemblies:
        return tuple(sorted(assemblies, key=lambda path: _natural_key(path, folder)))
    while pending:
        _check_cancelled(stop)
        current = pending.pop()
        found, subfolders = _read_directory(current, stop)
        assemblies.extend(found)
        pending.extend(subfolders)
    _check_cancelled(stop)
    return tuple(sorted(assemblies, key=lambda path: _natural_key(path, folder)))
