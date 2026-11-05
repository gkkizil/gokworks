"""Auditable declared-table arithmetic. No manufacturer method is certified here.

No extrapolation; no default service, width or correction factor. Numeric
provisional evaluations never become official manufacturer capacity approval.
"""

from bisect import bisect_left
from dataclasses import dataclass
from math import ceil
from .._numbers import positive
from ..models import Issue
from ..catalog.profiles import get_profile


class TableRangeError(ValueError):
    pass


def bracket(axis, value, allow_interpolation=False):
    positive(value, 'Tablo sorgusu')
    index = bisect_left(axis, value)
    if index < len(axis) and axis[index] == value:
        return index, index, 0.
    if not allow_interpolation or index == 0 or index == len(axis):
        raise TableRangeError('Tablo aralığı dışında veya enterpolasyon izni yok; ekstrapolasyon yapılmaz.')
    return index-1, index, (value-axis[index-1]) / (axis[index]-axis[index-1])


def interpolate_1d(table, value):
    a, b, fraction = bracket(table.axis, value, table.interpolation == 'linear_declared')
    return table.factors[a] + (table.factors[b] - table.factors[a]) * fraction


def interpolate_power(table, small_pulley, rpm):
    allow = table.interpolation == 'bilinear_declared'
    a, b, tx = bracket(table.small_pulley_axis, small_pulley, allow)
    c, d, ty = bracket(table.rpm_axis, rpm, allow)
    lower = table.base_power_kw[a][c] + (table.base_power_kw[a][d] - table.base_power_kw[a][c]) * ty
    upper = table.base_power_kw[b][c] + (table.base_power_kw[b][d] - table.base_power_kw[b][c]) * ty
    return positive(lower + (upper-lower)*tx, 'Enterpole edilmiş temel kapasite')


@dataclass(frozen=True, slots=True)
class CapacityEvaluation:
    status: str
    table_id: str | None
    method: str | None
    source_id: str | None
    source_status: str | None
    design_power_kw: float | None
    per_belt_power_kw: float | None = None
    total_power_kw: float | None = None
    required_belts: int | None = None
    capacity_margin: float | None = None
    meets_declared_demand: bool | None = None
    installation_allowance_mm: float | None = None
    tensioning_allowance_mm: float | None = None
    interpolation: str | None = None
    applied_factors: tuple[tuple[str, float], ...] = ()
    checks: tuple[Issue, ...] = ()
    manufacturer_verified: bool = False
    method_reference: str = ''


class TabulatedRatingProvider:
    """The documented declared_additive_corrected_v1 contract, not a brand algorithm."""

    def evaluate(self, catalog, belt, result, belt_count):
        table = next((item for item in catalog.ratings if item.series_id == belt.series_id and item.profile == belt.profile), None)
        checks = []
        design = result.design_power_kw
        def missing(message):
            checks.append(Issue('CAPACITY', message, severity='NOT_EVALUATED'))
            return CapacityEvaluation('NOT_EVALUATED', table.identifier if table else None,
                table.method if table else None, table.source_id if table else None,
                catalog.source(table.source_id).effective_status if table else None, design, checks=tuple(checks))
        if table is None:
            return missing('Seri/profil için güç tablosu yok; Gates/Optibelt yöntemi varsayılmaz.')
        source = catalog.source(table.source_id)
        if source.effective_status in ('OUTDATED', 'INCOMPLETE'):
            return missing('Eski veya eksik kaynak kapasite onayı için kullanılamaz.')
        if design is None:
            return missing('Servis faktörü eksik; otomatik 1.0 seçilmedi.')
        if table.additional_power_kw is None or not table.method_reference:
            return missing('Ek güç terimi veya açık yöntem referansı eksik; sıfır varsayılmadı.')
        timing = get_profile(belt.profile).family == 'timing'
        expected = {'engaged_teeth', 'length_mm', 'width_mm'} if timing else {'wrap_deg', 'length_mm'}
        corrections = {item.quantity: item for item in table.corrections}
        if set(corrections) != expected or (timing and table.reference_width_mm is None):
            return missing('Beyan edilen yöntemin tüm düzeltmeleri/referans genişliği gerekli; 1.0 varsayılmadı.')
        if belt_count is None:
            return missing('V kasnağı kanal/kayış adedi bilinmiyor.')
        small_driver = result.driver_reference_diameter_mm <= result.driven_reference_diameter_mm
        small = (result.specification.driver.teeth if small_driver else result.specification.driven.teeth) if timing else \
            min(result.driver_reference_diameter_mm, result.driven_reference_diameter_mm)
        rpm = result.specification.load.input_rpm if small_driver else result.nominal_output_rpm
        queries = dict(length_mm=belt.length_mm, width_mm=belt.width_mm,
            wrap_deg=min(result.driver_wrap_deg, result.driven_wrap_deg),
            engaged_teeth=min(result.engaged_driver_teeth_estimate, result.engaged_driven_teeth_estimate) if timing else None)
        try:
            base = interpolate_power(table, small, rpm)
            if timing and interpolate_1d(corrections['width_mm'], table.reference_width_mm) != 1.:
                return missing('Referans genişliği katsayısı 1 olmalı; genişlik tablosu çelişiyor.')
            factors = tuple((name, interpolate_1d(corrections[name], queries[name])) for name in sorted(expected))
            available = positive(base + table.additional_power_kw, 'Düzeltilmemiş kapasite')
            for _, factor in factors:
                available = positive(available * factor, 'Düzeltilmiş kapasite')
            total = positive(available * belt_count, 'Toplam kapasite')
            margin = positive(total / design, 'Kapasite oranı')
            required = ceil(positive(design / available, 'Gerekli adet oranı'))
        except (ValueError, OverflowError) as error:
            return missing(str(error))
        checks.append(Issue('UNVERIFIED_METHOD', 'Sayısal sonuç yalnız beyan edilen tablo/yöntem içindir; üretici tarafından doğrulanmadı.', severity='NOT_EVALUATED'))
        checks.append(Issue('CAPACITY_MARGIN', 'Kapasite oranı bütün tasarımın emniyet katsayısı değildir.', severity='INFO'))
        return CapacityEvaluation('PROVISIONAL', table.identifier, table.method, table.source_id, source.effective_status,
            design, available, total, required if not timing else None, margin, total >= design,
            table.installation_allowance_mm, table.tensioning_allowance_mm,
            table.interpolation + '; corrections=' + ','.join(x.interpolation for x in table.corrections), factors, tuple(checks),
            method_reference=table.method_reference)
