"""Versioned, unit-normalized analysis records. No COM or Qt objects cross here."""

from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal, InvalidOperation
import hashlib
import json
from uuid import uuid4


UNITS = {'mm': Decimal(1), 'cm': Decimal(10), 'm': Decimal(1000), 'in': Decimal('25.4'), 'µm': Decimal('.001')}
KINDS = ('linear', 'horizontal', 'vertical', 'ordinate', 'diameter', 'radius', 'angle',
         'reference', 'basic', 'arc', 'chamfer', 'gdt', 'unknown')
DISTRIBUTIONS = ('normal', 'uniform', 'triangular')


def number(value, title='Değer'):
    if isinstance(value, bool):
        raise ValueError(f'{title}: sayı girin.')
    try:
        result = Decimal(str(value).strip().replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ValueError(f'{title}: geçerli bir sayı girin.') from None
    if not result.is_finite() or abs(result) > Decimal('1e12'):
        raise ValueError(f'{title}: sonlu, en çok ±10¹² bir sayı girin.')
    return result


def length(value, unit='mm'):
    if unit not in UNITS:
        raise ValueError('Uzunluk birimi mm, cm, m, in veya µm olmalı. Açı uzunluğa çevrilemez.')
    return number(value) * UNITS[unit]


def fmt(value, digits=6):
    if value is None:
        return 'Bilinmiyor'
    return f'{value:.{digits}f}'.replace('.', ',')


def serializable(value):
    if hasattr(value, '__dataclass_fields__'):
        value = asdict(value)
    return json.loads(json.dumps(value, default=lambda item: str(item) if isinstance(item, Decimal) else item,
                                 ensure_ascii=False, allow_nan=False))


def digest(value):
    return hashlib.sha256(json.dumps(serializable(value), sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def snapshot(project):
    """Copy mutable containers, share immutable dimension/term/source records."""
    return replace(project,dimensions=list(project.dimensions),terms=list(project.terms),sources=list(project.sources))


@dataclass(frozen=True)
class Dimension:
    id: str
    name: str
    nominal: Decimal | None
    lower: Decimal | None
    upper: Decimal | None
    kind: str = 'linear'
    tolerance_type: str = 'manual'
    source: str = ''
    sheet: str = ''
    view: str = ''
    configuration: str = ''
    model: str = ''
    api_name: str = ''
    persistent_ref: str = ''
    physical_id: str = ''
    position: tuple = ()  # drawing-space millimetres, not model geometry
    display_unit: str = 'mm'
    display_text: str = ''
    provenance: str = 'manual'
    original_signature: str = ''  # original API values, retained after manual completion
    note: str = ''
    geometry_kind: str = ''  # Native Type2, retained even when classified as reference/BASIC.

    def __post_init__(self):
        for key in ('nominal', 'lower', 'upper'):
            if getattr(self, key) is not None:
                object.__setattr__(self, key, number(getattr(self, key), self.name))

    @property
    def minimum(self):
        return None if self.nominal is None or self.lower is None else self.nominal + self.lower

    @property
    def maximum(self):
        return None if self.nominal is None or self.upper is None else self.nominal + self.upper


def manual_dimension(name, nominal, lower, upper, unit='mm', **kwargs):
    return Dimension(uuid4().hex, name.strip(), length(nominal, unit), length(lower, unit),
                     length(upper, unit), display_unit=unit, **kwargs)


def iso_dimension(name, nominal, code, feature):
    from modules.iso_fits.rules import limits, mm
    band = limits(str(nominal), code, feature)
    return Dimension(uuid4().hex, name.strip(), band.nominal_mm, mm(band.lower_nm), mm(band.upper_nm),
                     kind='diameter', tolerance_type='ISO 286 ' + code, provenance='iso_286',
                     note='Gerçek ISO 286 tablosu. Zincirde çapın fonksiyonel ilişkisini belirtin.')


@dataclass(frozen=True)
class Term:
    dimension_id: str
    direction: int = 1
    start: str = ''
    end: str = ''
    axis: str = 'X'
    datum: str = ''  # user-defined common functional frame, not inferred from drawing position
    factor: Decimal = Decimal(1)
    relation: str = ''
    distribution: str = 'inherit'
    mean: Decimal | None = None
    sigma: Decimal | None = None
    mode: Decimal | None = None
    alignment_confirmed: bool = False  # Explicit user confirmation, never inferred from drawing position.

    def __post_init__(self):
        for key in ('factor', 'mean', 'sigma', 'mode'):
            if getattr(self, key) is not None:
                object.__setattr__(self, key, number(getattr(self, key)))


@dataclass(frozen=True)
class SourceStamp:
    path: str
    sha256: str
    size: int
    modified_ns: int
    title: str = ''
    dirty: bool = False
    notes: tuple = ()


@dataclass
class Project:
    name: str = 'Yeni tolerans analizi'
    id: str = field(default_factory=lambda: uuid4().hex)
    dimensions: list = field(default_factory=list)
    terms: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    start: str = 'P0'
    end: str = ''
    critical: str = 'K · Fonksiyonel boşluk'
    axis: str = 'X'
    datum: str = 'A'
    acceptance_min: Decimal | None = Decimal(0)
    acceptance_max: Decimal | None = None
    method: str = 'all'
    distribution: str = 'normal'
    input_sigma: Decimal = Decimal(3)
    output_sigma: Decimal = Decimal(3)
    truncate_normal: bool = True
    samples: int = 50000
    seed: int | None = 42
    independent: bool = True
    offline_snapshot: bool = False
    confirmed_digest: str = ''

    def __post_init__(self):
        for key in ('acceptance_min','acceptance_max','input_sigma','output_sigma'):
            if getattr(self,key) is not None:setattr(self,key,number(getattr(self,key),key))

    def fingerprint(self):
        data = asdict(self)
        data.pop('confirmed_digest')
        return digest(data)

    def invalidate(self):
        self.confirmed_digest = ''

    def confirm(self):
        from modules.tolerance_stack.chain import validate
        validate(self, confirmed=False)
        self.confirmed_digest = self.fingerprint()


@dataclass(frozen=True)
class Contribution:
    dimension_id: str
    name: str
    worst_case_percent: float
    variance_percent: float | None


@dataclass(frozen=True)
class Result:
    project_digest: str
    timestamp: str
    nominal: Decimal
    minimum: Decimal
    maximum: Decimal
    mean: float | None
    sigma: float | None
    rss_minimum: float | None
    rss_maximum: float | None
    worst_case_pass: bool | None
    rss_pass: bool | None
    kind: str
    contributions: tuple
    assumptions: tuple
    monte_carlo: dict | None = None
