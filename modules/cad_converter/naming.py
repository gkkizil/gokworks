"""Windows-safe deterministic destinations and atomic publication."""

import hashlib
import os
from pathlib import Path
import re
import unicodedata

from .scanner import path_key


def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', unicodedata.normalize('NFC', str(value)))
    value = value.strip().rstrip('. ') or 'Adsiz'
    if value.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        value = '_' + value
    if len(value) > 100:
        value = value[:85] + '_' + hashlib.sha256(value.encode()).hexdigest()[:10]
    return value


class Destinations:
    def __init__(self, options, sources):
        self.options = options
        self.claims = {}
        names = {}
        for source in sources:
            names.setdefault(Path(source.path).stem.casefold(), set()).add(path_key(source.path))
        self.duplicates = {name for name, paths in names.items() if len(paths) > 1}

    def path(self, source, configuration, fmt):
        o = self.options
        stem = Path(source.path).stem
        if stem.casefold() in self.duplicates:
            stem += '_' + hashlib.sha256(path_key(source.path).encode()).hexdigest()[:8]
        if o.naming == 'configuration' or o.configurations != 'active':
            stem += '_' + configuration
        if o.naming == 'format': stem += '_' + fmt.folder
        name = safe_name(o.prefix + stem + o.suffix)
        folder = Path(o.output).resolve() / fmt.folder
        if o.preserve_folders and source.root:
            relative = Path(source.path).resolve().parent.relative_to(Path(source.root).resolve())
            folder = folder.joinpath(*(safe_name(p) for p in relative.parts))
        target = folder / (name + fmt.extension)
        owner = (path_key(source.path), configuration, fmt.key)
        key = str(target).casefold()
        if key in self.claims and self.claims[key] != owner:
            digest = hashlib.sha256(repr(owner).encode()).hexdigest()[:10]
            target = folder / (name + '_' + digest + fmt.extension)
            key = str(target).casefold()
        if key in self.claims and self.claims[key] != owner:
            raise ValueError('Çıktı isimleri çakıştı; farklı bir ön ek veya çıktı klasörü seçin.')
        self.claims[key] = owner
        return target


def publish(temporary, target, overwrite):
    if overwrite:
        os.replace(temporary, target)
    elif os.name == 'nt':
        os.rename(temporary, target)
    else:
        os.link(temporary, target)
        Path(temporary).unlink()
