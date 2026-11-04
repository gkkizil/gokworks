"""Exact external common-tangent length and monotone inverse (bisection).

The low-level formula needs C>|R2-R1|. A usable two-pulley layout additionally
requires disjoint reference circles C>R1+R2. Actual outside-body clearance is
not established without manufacturer/CAD data.
"""

import math
from .._numbers import checked, positive, integer
from ..models import CenterSolution, LengthMetrics


def length_metrics(driver_diameter_mm, driven_diameter_mm, center_mm):
    r1 = positive(driver_diameter_mm, 'Sürücü referans çapı') / 2.
    r2 = positive(driven_diameter_mm, 'Sürülen referans çapı') / 2.
    center = positive(center_mm, 'Eksen mesafesi')
    delta = r2 - r1
    if center <= abs(delta):
        raise ValueError('Dış ortak teğet için C > |R₂ − R₁| olmalı.')
    sine = delta / center
    alpha = math.asin(sine)
    straight = center * math.sqrt((1. - sine) * (1. + sine))
    exact = checked(2. * straight + math.pi * r1 + math.pi * r2 + 2. * delta * alpha, 'Tam kayış uzunluğu')
    approximate = checked(2. * center + math.pi * r1 + math.pi * r2 + delta * (delta / center), 'Yaklaşık kayış uzunluğu')
    return LengthMetrics(center, alpha, straight, math.pi - 2. * alpha, math.pi + 2. * alpha, exact, approximate)


def solve_center_distance(driver_diameter_mm, driven_diameter_mm, length_mm, *,
                          absolute_tolerance_mm=1e-10, relative_tolerance=1e-13, max_iterations=128, stop=None):
    if stop is not None and stop.is_set():
        from ..validation import CalculationCancelled
        raise CalculationCancelled('Eksen mesafesi hesabı durduruldu.')
    d1 = positive(driver_diameter_mm, 'Sürücü referans çapı')
    d2 = positive(driven_diameter_mm, 'Sürülen referans çapı')
    length = positive(length_mm, 'Kayış uzunluğu')
    absolute = positive(absolute_tolerance_mm, 'Mutlak tolerans')
    relative = positive(relative_tolerance, 'Bağıl tolerans')
    integer(max_iterations, 'İterasyon sınırı')
    low = d1 / 2. + d2 / 2.
    minimum = length_metrics(d1, d2, low).exact_mm
    if length <= minimum:
        raise ValueError(f'Kayış uzunluğu, ayrık referans çemberleri için {minimum:.12g} mm değerinden büyük olmalı.')
    if d1 == d2:
        center = (length - math.pi * d1) / 2.
        if center <= low:
            raise ValueError('Bu uzunluk sayısal hassasiyet içinde ayrık kasnak üretmiyor.')
        return CenterSolution(center, length_metrics(d1, d2, center).exact_mm - length, 0)
    high = length / 2.
    for iteration in range(1, max_iterations + 1):
        if stop is not None and stop.is_set():
            from ..validation import CalculationCancelled
            raise CalculationCancelled('Eksen mesafesi hesabı durduruldu.')
        center = low + (high - low) / 2.
        value = length_metrics(d1, d2, center).exact_mm
        if value > length:
            high = center
        else:
            low = center
        if high - low <= max(absolute, relative * abs(center)) or value == length:
            residual = value - length
            if center <= d1 / 2. + d2 / 2.:
                raise ValueError('Bu uzunluk sayısal hassasiyet içinde ayrık kasnak üretmiyor.')
            return CenterSolution(center, residual, iteration)
    raise ValueError('Eksen mesafesi çözümü yakınsamadı; tolerans ve uzunluğu kontrol edin.')
