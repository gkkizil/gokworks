"""Sıkı sürümlü .gwhyd proje sözleşmesi; sonuçlar yüklemede yeniden hesaplanır."""
import json
import types
from dataclasses import fields, is_dataclass, asdict
from typing import get_args, get_origin, get_type_hints
from pathlib import Path
from .core.models import Project
from .core.service import calculate_project
from .core.validation import InputError
from shared.files import write_text_atomic

SCHEMA = 'gokworks.hydraulic_unit'
VERSION = 1
MAX_BYTES = 2 * 1024 * 1024


def _typed(value, target, path):
    if get_origin(target) is types.UnionType:
        if value is None and type(None) in get_args(target):
            return None
        target = next(t for t in get_args(target) if t is not type(None))
    if is_dataclass(target):
        hints = get_type_hints(target)
        if not isinstance(value, dict) or set(value) != {f.name for f in fields(target)}:
            raise InputError(path, f'{path}: eksik veya bilinmeyen alan.')
        return target(**{k: _typed(v, hints[k], path + '.' + k) for k, v in value.items()})
    if get_origin(target) is tuple:
        if not isinstance(value, list):
            raise InputError(path, f'{path}: liste gerekli.')
        return tuple(_typed(v, get_args(target)[0], path) for v in value)
    if target is float and type(value) in (int, float):
        return float(value)
    if type(value) is not target:
        raise InputError(path, f'{path}: veri türü geçersiz.')
    return value


def dumps(project: Project) -> str:
    calculate_project(project)
    return json.dumps(dict(schema=SCHEMA, version=VERSION, units='SI', project=asdict(project)),
                      ensure_ascii=False, allow_nan=False, indent=2)


def _pairs(pairs):
    data = {}
    for k, v in pairs:
        if k in data:
            raise InputError(k, 'Tekrarlanan JSON alanı.')
        data[k] = v
    return data


def loads(text: str | bytes) -> Project:
    if len(text.encode('utf-8') if isinstance(text, str) else text) > MAX_BYTES:
        raise InputError('project', 'Proje dosyası en çok 2 MiB olabilir.')
    def bad(value):
        raise InputError('project', 'JSON sonlu sayılar içermeli: ' + value)
    try:
        data = json.loads(text, object_pairs_hook=_pairs, parse_constant=bad)
        if (not isinstance(data, dict) or set(data) != {'schema','version','units','project'}
                or data['schema'] != SCHEMA or type(data['version']) is not int
                or data['version'] != VERSION or data['units'] != 'SI'):
            raise InputError('project', 'Desteklenmeyen proje şeması, sürüm veya birim.')
        project = _typed(data['project'], Project, 'project')
        calculate_project(project)
        return project
    except (RecursionError, OverflowError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError('project', 'Proje dosyası okunamadı veya veri sınırı aşıldı.') from exc


def save(project: Project, path) -> Path:
    return write_text_atomic(path, dumps(project))


def load(path) -> Project:
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise InputError('project', 'Proje dosyası çok büyük.')
    return loads(path.read_bytes())
