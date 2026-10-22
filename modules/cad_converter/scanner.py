"""Deterministic file discovery and physical-file deduplication."""

import os
from pathlib import Path
from .models import Source, checkpoint

EXTENSIONS = {'.sldprt', '.sldasm'}


def path_key(path):
    return os.path.normcase(str(Path(path).resolve()))


def identity(path):
    path = Path(path).resolve()
    try:
        info = path.stat()
        if info.st_ino:
            return ('inode', info.st_dev, info.st_ino)
    except OSError:
        pass
    return ('path', path_key(path))


def scan(paths, *, recursive=True, existing=(), stop=None):
    seen = {identity(s.path) for s in existing}
    sources, issues = [], []

    def add(file, root=''):
        checkpoint(stop)
        file = Path(file)
        if file.name.startswith('~$') or file.suffix.casefold() not in EXTENSIONS:
            return
        if not file.is_file():
            issues.append(f'{file.name}: dosya bulunamadı veya okunamıyor.'); return
        key = identity(file)
        if key not in seen:
            seen.add(key); sources.append(Source(str(file.resolve()), str(root)))

    for entry in paths:
        checkpoint(stop)
        entry = Path(entry).resolve()
        if entry.is_dir():
            def failed(error):
                issues.append(f'{error.filename}: klasör okunamadı.')
            for parent, folders, names in os.walk(entry, onerror=failed, followlinks=False):
                checkpoint(stop)
                folders.sort(key=str.casefold)
                for name in sorted(names, key=str.casefold):
                    add(Path(parent) / name, entry)
                if not recursive:
                    break
        elif entry.suffix.casefold() in EXTENSIONS:
            add(entry)
        else:
            issues.append(f'{entry.name}: yalnız SLDPRT ve SLDASM dosyaları eklenir.')
    return sources, issues
