"""Serializable profile data. No Qt or COM objects cross this boundary."""

from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re


class Cancelled(Exception): pass


def checkpoint(stop):
    if stop is not None and stop.is_set(): raise Cancelled()


def number(value, title='Değer', *, positive=False):
    if isinstance(value, bool):
        raise ValueError(title + ' sayısal olmalı.')
    try:
        result = Decimal(str(value).strip().replace(',', '.'))
    except InvalidOperation:
        raise ValueError(title + ' için geçerli bir sayı girin.') from None
    if not result.is_finite() or (result <= 0 if positive else result < 0):
        raise ValueError(title + (' sıfırdan büyük olmalı.' if positive else ' negatif olamaz.'))
    if result > Decimal('100000000') or result.as_tuple().exponent < -9:
        raise ValueError(title + ' desteklenen aralığın dışında.')
    return result


def quantity(value):
    result = number(value, 'Adet', positive=True)
    if result != result.to_integral_value() or result > 100000:
        raise ValueError('Adet 1–100000 arasında tam sayı olmalı.')
    return int(result)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def canonical(value):
    return re.sub(r'\s+', ' ', str(value).strip()).upper().replace('×', 'X')


@dataclass
class Property:
    name: str
    raw: str = ''
    evaluated: str = ''
    resolved: bool = False
    linked: bool = False
    status: str = ''


@dataclass
class ScanRow:
    id: str
    source: str
    configuration: str
    folder: str
    profile: str = ''
    material: str = ''
    length: str = ''
    count: int = 0
    angle1: str = ''
    angle2: str = ''
    thickness: str = ''
    standard: str = ''
    stock_code: str = ''
    body_refs: list[str] = field(default_factory=list)
    occurrences: list[str] = field(default_factory=list)
    properties: dict[str, Property] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    excluded: bool = False
    geometry_verified: bool = False
    length_source: str = 'LENGTH'
    freshness: str = ''
    allowance: str = '0'
    reviewed: bool = False
    review_note: str = ''
    property_errors: list[str] = field(default_factory=list)
    display_unit: str = ''

    def errors(self):
        errors = []
        if not self.profile.strip(): errors.append('Profil kesiti eksik.')
        if not self.material.strip(): errors.append('Malzeme kalitesi eksik.')
        try: number(self.length, 'Boy', positive=True)
        except ValueError as error: errors.append(str(error))
        try: quantity(self.count)
        except ValueError as error: errors.append(str(error))
        try: number(self.allowance, 'Ek ham boy')
        except ValueError as error: errors.append(str(error))
        for angle in (self.angle1, self.angle2):
            if angle:
                try:
                    if number(angle, 'Açı') > 180: errors.append('Açı 0–180° arasında olmalı.')
                except ValueError as error: errors.append(str(error))
        return errors

    @property
    def ready(self):
        return (not self.excluded and not self.errors() and
                ((self.reviewed and bool(self.review_note.strip())) or
                 (self.geometry_verified and not self.issues)))

    @property
    def status(self):
        return 'Hariç' if self.excluded else 'Hazır' if self.ready else 'İnceleme Gerekli'

    @property
    def revision(self):
        payload = asdict(self)
        for key in ('reviewed', 'review_note'):
            payload.pop(key)
        for key in ('body_refs', 'occurrences'):
            payload[key] = sorted(payload[key])
        return digest(payload)


@dataclass
class ScanResult:
    source: str
    configuration: str
    rows: list[ScanRow] = field(default_factory=list)
    diagnostics: list[dict] = field(default_factory=list)
    scanned_parts: int = 0
    weldments: int = 0
    unscanned: int = 0

    @property
    def summary(self):
        eligible = [row for row in self.rows if not row.excluded]
        known_length = Decimal(0)
        for row in eligible:
            try: known_length += number(row.length, 'Boy', positive=True)*quantity(row.count)
            except ValueError: pass
        return dict(parts=self.scanned_parts, weldments=self.weldments,
                    profiles=sum(row.count for row in eligible),
                    length=str(known_length), property_errors=sum(len(set(row.property_errors)) for row in self.rows),
                    review=sum(not row.ready for row in eligible),
                    excluded=sum(row.excluded for row in self.rows), unscanned=self.unscanned)


@dataclass
class Demand:
    id: str
    profile: str
    material: str
    length: str
    count: int
    thickness: str = ''
    standard: str = ''
    stock_code: str = ''
    allowance: str = '0'
    source: str = 'Manuel'
    import_id: str = ''
    import_revision: str = ''
    note: str = ''
    angle1: str = ''
    angle2: str = ''
    import_scope: str = ''
    body_refs: list[str] = field(default_factory=list)

    @property
    def group(self):
        section = re.sub(r'\s*X\s*','X',canonical(self.profile)).replace('⌀','Ø')
        thickness = format(number(self.thickness, 'Et kalınlığı', positive=True).normalize(),'f') if self.thickness else ''
        return (section, thickness, *(canonical(value) for value in
                                     (self.material, self.standard, self.stock_code)))

    def validate(self):
        if not self.profile.strip() or not self.material.strip():
            raise ValueError('Profil kesiti ve malzeme kalitesi girin.')
        number(self.length, 'Boy', positive=True)
        number(self.allowance, 'Ek ham boy')
        self.count = quantity(self.count)
        if self.thickness: number(self.thickness, 'Et kalınlığı', positive=True)


@dataclass
class Project:
    demands: list[Demand] = field(default_factory=list)
    stock_length: str = '6000'
    kerf: str = '3'
    trim: str = '0'

    def validate(self):
        length = number(self.stock_length, 'Stok boyu', positive=True)
        if 2*number(self.trim, 'Uç düzeltme') >= length:
            raise ValueError('İki uç düzeltmesi stok boyundan küçük olmalı.')
        number(self.kerf, 'Testere kesim payı')
        for demand in self.demands: demand.validate()
        if len({row.id for row in self.demands}) != len(self.demands):
            raise ValueError('Kesim listesinde yinelenen kayıt kimliği var.')


def transfer(project, result):
    """Append only. Repeat scans never overwrite manual or imported rows."""
    existing = {row.import_id: row for row in project.demands if row.import_id}
    stats = dict(added=0, duplicate=0, changed=0, blocked=0)
    for row in result.rows:
        if not row.ready:
            stats['blocked'] += 1
            continue
        key = digest([result.source.casefold(), result.configuration, row.id])
        scope = digest([result.source.casefold(), result.configuration, row.source.casefold(), row.configuration])
        if key in existing:
            stats['duplicate' if existing[key].import_revision == row.revision else 'changed'] += 1
            continue
        if row.body_refs and any(d.import_scope == scope and set(d.body_refs).intersection(row.body_refs)
                                 for d in existing.values()):
            stats['changed'] += 1
            continue
        demand = Demand(key, row.profile, row.material, row.length, row.count, row.thickness,
                        row.standard, row.stock_code, row.allowance,
                        f'{row.source} [{row.configuration}] / {row.folder}', key, row.revision,
                        row.review_note or 'Doğrusal geometri ve kare uçlar doğrulandı.', row.angle1, row.angle2,
                        import_scope=scope, body_refs=list(row.body_refs))
        demand.validate()
        project.demands.append(demand)
        existing[key] = demand
        stats['added'] += 1
    return stats
