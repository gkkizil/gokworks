"""Optibelt SK 2018 reference calculation; not a generic SP-section rating.

Manufacturer-authored manual, printed pp74/76/87/98–101. Historical reference
data, not current product approval. Linear interpolation only inside available
table cells. Missing cells and out-of-range inputs never become capacities.
"""
from bisect import bisect_left
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path

from .._numbers import positive


@lru_cache(maxsize=1)
def reference_data():
    return json.loads((Path(__file__).parents[1]/'catalog'/'data'/'optibelt-sk-reference-2018.json').read_text(encoding='utf-8'))


def bracket(axis, value):
    if not axis[0] <= value <= axis[-1]:
        raise ValueError('Optibelt SK referans tablosunun dışında; ekstrapolasyon yapılmadı.')
    i = bisect_left(axis, value)
    return (i, i) if axis[i] == value else (i-1, i)


def linear(points, value):
    lo, hi = bracket([p[0] for p in points], value)
    x, a = points[lo]; y, b = points[hi]
    return a if lo == hi else a+(b-a)*(value-x)/(y-x)


@dataclass(frozen=True, slots=True)
class SKRating:
    base_power_kw: float
    additional_power_kw: float
    wrap_factor: float
    length_factor: float
    per_belt_power_kw: float
    design_power_kw: float
    required_belts: int
    small_diameter_mm: float
    small_rpm: float
    ratio: float
    source_pdf_page: int
    flex_rate_hz: float
    manufacturer_verified: bool = False
    model: str = 'Optibelt SK · 2018 referans hesabı'


def rate(profile, result):
    data = reference_data()
    if profile not in data['profiles'] or result.specification.belt.profile != profile:
        raise ValueError('Optibelt SK yalnız SPZ/SPA/SPB/SPC ve aynı profil için kullanılabilir.')
    design = result.design_power_kw
    if design is None:
        raise ValueError('Kanal hesabı için servis faktörünü açıkça girin; 1.0 varsayılmaz.')
    table = data['profiles'][profile]
    d1, d2 = result.driver_reference_diameter_mm, result.driven_reference_diameter_mm
    small = min(d1, d2)
    rpm = result.specification.load.input_rpm if d1 <= d2 else result.nominal_output_rpm
    ratio = max(d1, d2)/small
    rows = table['rows']; diameters = table['diameters_mm']
    nl, nh = bracket([r['rpm'] for r in rows], rpm)
    dl, dh = bracket(diameters, small)
    def diameter_power(row):
        a, b = row['base_kw'][dl], row['base_kw'][dh]
        if a is None or b is None:
            raise ValueError('Güç tablosunda boş hücre; kapasite tahmin edilmedi.')
        return a if dl == dh else a+(b-a)*(small-diameters[dl])/(diameters[dh]-diameters[dl])
    base = linear([(rows[i]['rpm'], diameter_power(rows[i])) for i in sorted({nl, nh})], rpm)
    # Printed ratio bands have 0.01 resolution. In their gaps use the lower
    # increment conservatively; exactly equal pulleys have no ratio increment.
    band = 3 if ratio > 1.57 else 2 if ratio >= 1.27 else 1 if ratio >= 1.06 else 0
    addition = 0. if ratio < 1.01 else linear(
        [(rows[i]['rpm'], rows[i]['additional_kw'][band]) for i in sorted({nl, nh})], rpm)
    wrap = linear(data['wrap_factors'], abs(d2-d1)/result.center_mm)
    # A length-mode solve retains the exact catalogue Ld. Its reconstructed
    # tangent-path length differs by numerical solver tolerance; using that
    # residual here would reject the genuine first/last table entries.
    datum_length = result.selected_length_mm if result.selected_length_mm is not None else result.length_exact_mm
    length = linear(table['length_factors'], datum_length)
    flex = 2000*result.speed_m_s/datum_length
    if result.speed_m_s > 42. or flex > 100.:
        raise ValueError('Optibelt SK hız veya bükülme frekansı sınırı aşıldı (42 m/s, 100 s⁻¹).')
    per_belt = positive((base+addition)*wrap*length, 'Düzeltilmiş kayış gücü')
    required = math.ceil(positive(design/per_belt, 'Gerekli kayış adedi'))
    return SKRating(base, addition, wrap, length, per_belt, design, required,
                    small, rpm, ratio, table['pdf_page'], flex)
