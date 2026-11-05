"""Explicit declared-table method; NOT a Gates/Optibelt calculation standard."""

from dataclasses import dataclass
from .._numbers import finite, positive
from .products import sequence, text
from .profiles import get_profile


def ordered_axis(values, name):
    values = sequence(values, name, maximum=1000)
    if not values:
        raise ValueError(name + ': boş eksen.')
    for value in values:
        positive(value, name)
    if any(b <= a for a, b in zip(values, values[1:])):
        raise ValueError(name + ': eksen artan ve tekrarsız olmalı.')
    return values


@dataclass(frozen=True, slots=True)
class CorrectionTable:
    quantity: str  # wrap_deg / length_mm / width_mm / engaged_teeth
    axis: tuple[float, ...]
    factors: tuple[float, ...]
    interpolation: str = 'none'

    def __post_init__(self):
        if self.quantity not in ('wrap_deg', 'length_mm', 'width_mm', 'engaged_teeth'):
            raise ValueError('Bilinmeyen düzeltme büyüklüğü.')
        object.__setattr__(self, 'axis', ordered_axis(self.axis, self.quantity))
        factors = sequence(self.factors, 'Katsayılar', maximum=1000)
        if len(factors) != len(self.axis):
            raise ValueError('Düzeltme ekseni ve katsayı sayısı farklı.')
        for value in factors:
            positive(value, 'Düzeltme katsayısı')
        object.__setattr__(self, 'factors', factors)
        if self.interpolation not in ('none', 'linear_declared'):
            raise ValueError('Yalnız açıkça beyan edilen doğrusal enterpolasyon desteklenir.')


@dataclass(frozen=True, slots=True)
class RatingTable:
    identifier: str
    series_id: str
    source_id: str
    profile: str
    method: str  # declared_additive_corrected_v1 only; never implicitly manufacturer approved.
    small_pulley_axis: tuple[float, ...]  # V: datum mm; timing: teeth.
    rpm_axis: tuple[float, ...]
    base_power_kw: tuple[tuple[float, ...], ...]  # rows small pulley, columns rpm.
    additional_power_kw: float | None = None
    corrections: tuple[CorrectionTable, ...] = ()
    interpolation: str = 'none'
    minimum_pulley: float | None = None  # datum mm / teeth, matching family.
    maximum_speed_m_s: float | None = None
    installation_allowance_mm: float | None = None
    tensioning_allowance_mm: float | None = None
    method_reference: str = ''
    reference_width_mm: float | None = None  # Timing table's explicitly declared base width.

    def __post_init__(self):
        for name in ('identifier', 'series_id', 'source_id'):
            text(getattr(self, name), name)
        profile = get_profile(self.profile)
        if not profile.nominal_supported or self.method != 'declared_additive_corrected_v1':
            raise ValueError('Desteklenmeyen kapasite yöntemi/profili; üretici yöntemi varsayılmaz.')
        for name in ('small_pulley_axis', 'rpm_axis'):
            object.__setattr__(self, name, ordered_axis(getattr(self, name), name))
        rows = sequence(self.base_power_kw, 'Güç matrisi', maximum=1000)
        if len(rows) != len(self.small_pulley_axis):
            raise ValueError('Güç matrisi satır sayısı farklı.')
        rows = tuple(sequence(row, 'Güç satırı', maximum=1000) for row in rows)
        for row in rows:
            if len(row) != len(self.rpm_axis):
                raise ValueError('Güç matrisi sütun sayısı farklı.')
            for value in row:
                positive(value, 'Temel kapasite')
        object.__setattr__(self, 'base_power_kw', rows)
        corrections = sequence(self.corrections, 'Düzeltmeler', maximum=4)
        if any(not isinstance(item, CorrectionTable) for item in corrections) or len({x.quantity for x in corrections}) != len(corrections):
            raise ValueError('Geçersiz/mükerrer düzeltme tablosu.')
        object.__setattr__(self, 'corrections', corrections)
        if self.interpolation not in ('none', 'bilinear_declared'):
            raise ValueError('Doğrulanmamış enterpolasyon yöntemi.')
        if self.additional_power_kw is not None and finite(self.additional_power_kw, 'Ek güç') < 0:
            raise ValueError('Ek güç negatif olamaz.')
        for key in ('minimum_pulley', 'maximum_speed_m_s', 'reference_width_mm'):
            if getattr(self, key) is not None:
                positive(getattr(self, key), key)
        for key in ('installation_allowance_mm', 'tensioning_allowance_mm'):
            value = getattr(self, key)
            if value is not None and finite(value, key) < 0:
                raise ValueError('Ayar mesafesi negatif olamaz.')
        text(self.method_reference, 'Yöntem kaynağı', optional=True)
