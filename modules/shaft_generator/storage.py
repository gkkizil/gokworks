"""Versioned JSON projects, atomic writes and explicit overwrite semantics."""

import json
import hashlib
import os
from pathlib import Path
import tempfile
from .models import Project
from .validation import require_valid


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(project, path, *, overwrite=False, expected_digest=None):
    require_valid(project)
    path = Path(path)
    content = json.dumps(project.to_dict(), ensure_ascii=False, allow_nan=False, indent=2) + '\n'
    if not overwrite:
        # Exclusive create handles races, unlike an exists() check followed by write.
        with path.open('x', encoding='utf-8') as stream:
            stream.write(content)
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix='.shaft-', delete=False) as stream:
            temporary = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if expected_digest is not None and (not path.is_file() or fingerprint(path)!=expected_digest):
            raise FileExistsError('Onaydan sonra hedef dosya değişti; dosya korunarak kayıt durduruldu.')
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def load(path):
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise ValueError('Mil projesi 2 MB sınırını aşıyor.')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('JSON içinde yinelenen alan: ' + key)
            result[key] = value
        return result
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Sonlu olmayan JSON sayısı: '+value)))
        return Project.from_dict(data)
    except (TypeError, OverflowError, RecursionError) as error:
        raise ValueError('Mil projesi yapısı geçersiz.') from error
