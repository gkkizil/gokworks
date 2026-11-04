"""Declared dimensional catalogues, deliberately incapable of claiming a power rating."""

from dataclasses import dataclass, field
from .._numbers import integer, positive
from .profiles import get_profile


@dataclass(frozen=True, slots=True)
class CatalogSource:
    name: str
    manufacturer: str = ''
    series: str = ''
    revision: str = ''
    reference: str = ''  # URL/document/page; caller-declared, not independently verified.
    kind: str = 'user_defined'  # user_defined / example

    def __post_init__(self):
        if any(not isinstance(getattr(self, name), str) for name in
               ('name', 'manufacturer', 'series', 'revision', 'reference', 'kind')):
            raise ValueError('Katalog kaynak alanları metin olmalı.')
        if not self.name.strip() or self.kind not in ('user_defined', 'example'):
            raise ValueError('Katalog kaynak adı ve user_defined/example kaynak türü gerekli.')


@dataclass(frozen=True, slots=True)
class LengthCatalog:
    identifier: str
    profile: str
    reference_line: str
    source: CatalogSource
    lengths_mm: tuple[float, ...] = ()
    tooth_counts: tuple[int, ...] = ()

    def __post_init__(self):
        profile = get_profile(self.profile)
        if not isinstance(self.identifier, str) or not self.identifier.strip() or not isinstance(self.source, CatalogSource):
            raise ValueError('Katalog kimliği ve CatalogSource gerekli.')
        if not profile.nominal_supported or self.reference_line != profile.reference_line:
            raise ValueError('Katalog profili/referans çizgisi desteklenmiyor veya uyuşmuyor.')
        for name in ('lengths_mm', 'tooth_counts'):
            values = getattr(self, name)
            if type(values) not in (tuple, list) or len(values) > 10000:
                raise ValueError('Katalog en çok 10000 öğeli bir liste/tuple olmalı.')
            object.__setattr__(self, name, tuple(values))
        values = self.tooth_counts if profile.family == 'timing' else self.lengths_mm
        extra = self.lengths_mm if profile.family == 'timing' else self.tooth_counts
        if not values or extra:
            raise ValueError('Senkron katalog yalnız diş adetleri; V katalog yalnız datum uzunlukları içerir.')
        for value in values:
            (integer if profile.family == 'timing' else positive)(value, 'Katalog boyutu')
            if profile.family == 'timing':
                positive(value * profile.pitch_mm, 'Katalog bölüm uzunluğu')
        if len(set(values)) != len(values):
            raise ValueError('Katalog boyutları tekrarlanmamalı.')


@dataclass(frozen=True, slots=True)
class BeltCandidate:
    catalog_id: str
    profile: str
    source: CatalogSource
    reference_line: str
    length_mm: float
    belt_teeth: int | None
    center_mm: float | None
    center_deviation_mm: float | None
    small_wrap_deg: float | None
    engaged_small_teeth_estimate: float | None
    status: str  # GEOMETRICALLY_SUITABLE / UNSUITABLE
    reason: str
    dimension_listed: bool = field(default=True, init=False)
    power_capacity_verified: bool = field(default=False, init=False)
    production_approved: bool = field(default=False, init=False)
