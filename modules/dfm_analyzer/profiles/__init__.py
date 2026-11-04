"""DFM rule profiles: versioned JSON, bundled examples and user files."""

from dataclasses import dataclass, field
import json
from pathlib import Path

from ..models import SEVERITIES

SCHEMA, VERSION = 'gokworks.dfm_profile', 1
HERE = Path(__file__).resolve().parent


@dataclass
class Profile:
    id: str
    name: str
    profile_version: str
    process: str
    verified: bool
    note: str
    rules: dict
    closure_tolerance: float = .05
    short_segment: float = .05
    thickness_range: tuple | None = None
    materials: list = field(default_factory=list)
    envelope: tuple | None = None
    path: str = ''


def _number(value, title, *, positive=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{title}: sayı olmalı.')
    value = float(value)
    if value != value or value in (float('inf'), float('-inf')) or (positive and value <= 0) or value < 0:
        raise ValueError(f'{title}: pozitif ve sonlu olmalı.')
    return value


def parse(data, path=''):
    """Validate a profile dict; every error names the field."""
    from ..rules import REGISTRY
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or data.get('version') != VERSION:
        raise ValueError('GOKWORKS DFM profili (sürüm 1) değil.')
    for key in ('id', 'name', 'profile_version', 'process', 'note'):
        if not isinstance(data.get(key), str) or (key != 'note' and not data[key].strip()):
            raise ValueError(f'Profil alanı eksik veya metin değil: {key}.')
    if not isinstance(data.get('verified'), bool):
        raise ValueError('Profil alanı “verified” doğru/yanlış olmalı.')
    rules = data.get('rules')
    if not isinstance(rules, dict) or not rules:
        raise ValueError('Profilde kural yok.')
    for rid, cfg in rules.items():
        if rid not in REGISTRY:
            raise ValueError(f'Bilinmeyen kural: {rid}.')
        if not isinstance(cfg, dict) or set(cfg) - {'enabled', 'severity', 'min_mm', 'factor_t', 'reference'}:
            raise ValueError(f'{rid}: geçersiz kural ayarı.')
        if 'severity' in cfg and cfg['severity'] not in SEVERITIES:
            raise ValueError(f'{rid}: önem ERROR, WARNING veya INFO olmalı.')
        if 'enabled' in cfg and not isinstance(cfg['enabled'], bool):
            raise ValueError(f'{rid}: enabled doğru/yanlış olmalı.')
        for key in ('min_mm', 'factor_t'):
            if key in cfg:
                cfg[key] = _number(cfg[key], f'{rid}.{key}')
    thickness = data.get('thickness_range_mm')
    if thickness is not None:
        if not isinstance(thickness, list) or len(thickness) != 2:
            raise ValueError('thickness_range_mm [en az, en çok] olmalı.')
        low, high = (_number(v, 'thickness_range_mm') for v in thickness)
        if low > high:
            raise ValueError('thickness_range_mm: en az, en çoktan büyük olamaz.')
        thickness = (low, high)
    envelope = data.get('envelope_mm')
    if envelope is not None:
        if not isinstance(envelope, list) or len(envelope) != 2:
            raise ValueError('envelope_mm [genişlik, boy] olmalı.')
        envelope = tuple(_number(v, 'envelope_mm') for v in envelope)
    materials = data.get('materials', [])
    if not isinstance(materials, list) or not all(isinstance(m, str) for m in materials):
        raise ValueError('materials metin listesi olmalı.')
    return Profile(data['id'], data['name'], data['profile_version'], data['process'], data['verified'], data['note'],
                   rules, _number(data.get('closure_tolerance_mm', .05), 'closure_tolerance_mm'),
                   _number(data.get('short_segment_mm', .05), 'short_segment_mm'), thickness, materials, envelope, str(path))


def load(path):
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError(f'{path.name}: profil okunamadı ({error}).') from None
    return parse(data, path)


def bundled():
    return {p.id: p for p in (load(f) for f in sorted(HERE.glob('*.json')))}
