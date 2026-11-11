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
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix='.shaft-', delete=False) as stream:
            temporary = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite and expected_digest is not None and (not path.is_file() or fingerprint(path)!=expected_digest):
            raise FileExistsError('Onaydan sonra hedef dosya değişti; dosya korunarak kayıt durduruldu.')
        if overwrite:
            os.replace(temporary, path)
        else:
            # Publish the complete, flushed inode exclusively. A racing create
            # cannot be overwritten, and failed writes never expose partial JSON.
            os.link(temporary, path)
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
