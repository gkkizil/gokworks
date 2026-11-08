"""Hidrostatik F=pA ve süreklilik Q=Av; Euler elastik kolon ön kontrolü.

ISO 3320 boyut serisi yaklaşımı görev tanımındaki nominal adaylarla sınırlıdır.
Burkulma, silindir üreticisinin komple kolon/stabilite hesabının yerine geçmez.
"""
import math
from .models import Cylinder, CylinderOperatingPoint
from .catalogs import BORES_MM, RODS_MM, MOUNT_K, BUCKLING_SAFETY, select_up
from .validation import number, efficiency, choice, InputError


def areas(c: Cylinder) -> tuple[float, float, float]:
    number(c.bore, 'bore'); number(c.rod, 'rod'); number(c.stroke, 'stroke')
    efficiency(c.efficiency, 'cylinder_efficiency')
    if c.rod >= c.bore:
        raise InputError('rod', 'Mil çapı piston çapından küçük olmalı.')
    number(c.initial_position, 'initial_position', zero=True)
    if c.initial_position > c.stroke:
        raise InputError('initial_position', 'Başlangıç konumu strok aralığında olmalı.')
    a1 = math.pi * c.bore**2 / 4
    a2 = math.pi * (c.bore**2 - c.rod**2) / 4
    return a1, a2, a1 / a2


def effective_area(c: Cylinder, kind: str) -> tuple[float, float]:
    a1, a2, _ = areas(c)
    choice(kind, ('extend','retract','regenerate','hold'), 'movement')
    if kind == 'regenerate':
        return a1 - a2, 0.
    return (a2, a1) if kind == 'retract' else (a1, a2)


def force_at_pressure(c: Cylinder, pressure: float, kind: str = 'extend', back_pressure: float = 0.) -> float:
    number(pressure, 'pressure', zero=True); number(back_pressure, 'back_pressure', zero=True)
    if kind == 'regenerate' and back_pressure:
        raise InputError('back_pressure', 'İdeal rejeneratif bağlantı ayrı karşı basınç kabul etmez.')
    a, b = effective_area(c, kind)
    return (pressure * a - back_pressure * b) * c.efficiency


def required_pressure(c: Cylinder, force: float, kind: str = 'extend', back_pressure: float = 0.) -> float:
    number(force, 'force', zero=True); number(back_pressure, 'back_pressure', zero=True)
    if kind == 'regenerate' and back_pressure:
        raise InputError('back_pressure', 'İdeal rejeneratif bağlantıda iki oda eş basınçlıdır; ayrı karşı basınç modeli yok.')
    a, b = effective_area(c, kind)
    return (force / c.efficiency + back_pressure * b) / a


def bore_for_force(force: float, pressure: float, *, rod: float = 0., efficiency_value: float = .95,
                   kind: str = 'extend', back_pressure: float = 0.) -> tuple[float | None, float]:
    number(force, 'force', zero=True); number(pressure, 'pressure'); number(rod, 'rod', zero=True)
    number(back_pressure, 'back_pressure', zero=True)
    efficiency(efficiency_value, 'efficiency'); choice(kind, ('extend','retract'), 'movement')
    if pressure <= back_pressure:
        raise InputError('pressure', 'Ters çap hesabında besleme basıncı karşı basınçtan yüksek olmalı.')
    numerator = 4 * force / (math.pi * efficiency_value) + (pressure * rod**2 if kind == 'retract' else -back_pressure * rod**2)
    theoretical = max(rod, math.sqrt(max(0., numerator / (pressure - back_pressure))))
    nominal = select_up(theoretical * 1000, tuple(v for v in BORES_MM if v / 1000 > rod))
    return (nominal / 1000 if nominal else None), theoretical


def buckling(c: Cylinder, compression_force: float) -> dict:
    areas(c); number(c.effective_length, 'effective_length'); number(c.young_modulus, 'young_modulus')
    number(compression_force, 'compression_force', zero=True); choice(c.mounting, MOUNT_K, 'mounting')
    inertia = math.pi * c.rod**4 / 64
    length = MOUNT_K[c.mounting] * c.effective_length
    critical = math.pi**2 * c.young_modulus * inertia / length**2
    safety = critical / compression_force if compression_force else None
    return dict(critical_force=critical, safety=safety, effective_length=length,
                passed=safety is None or safety >= BUCKLING_SAFETY)


def calculate_cylinder(c: Cylinder, point: CylinderOperatingPoint) -> dict:
    """Bağımsız silindir sekmesi: girdi hız/süre karşılıklı dışlayıcıdır."""
    a1, a2, ratio = areas(c)
    number(point.pressure, 'pressure'); number(point.travel, 'travel')
    if point.travel > c.stroke:
        raise InputError('travel', 'Hareket boyu silindir strokunu aşamaz.')
    if (point.speed is None) == (point.duration is None):
        raise InputError('speed', 'Hız veya süreden yalnız birini girin.')
    speed = number(point.speed, 'speed') if point.speed is not None else point.travel / number(point.duration, 'duration')
    a, opposite = effective_area(c, point.kind)
    pressure = required_pressure(c, point.force, point.kind, point.back_pressure)
    nominal, theoretical = (None, None) if point.kind == 'regenerate' else bore_for_force(
        point.force, point.pressure, rod=c.rod, back_pressure=point.back_pressure,
        efficiency_value=c.efficiency, kind='retract' if point.kind == 'retract' else 'extend')
    # Rejeneratif bağlantıda etkin alan mil alanıdır; D değiştirmek kuvveti
    # artırmaz. İstenen kuvvet için mil serisi ayrıca seçilir.
    rod_min = math.sqrt(4 * point.force / (math.pi * point.pressure * c.efficiency)) if point.kind == 'regenerate' else None
    rod_nominal = select_up(rod_min * 1000, RODS_MM) if rod_min is not None else None
    return dict(piston_area=a1, annular_area=a2, area_ratio=ratio, effective_area=a,
                force=force_at_pressure(c, point.pressure, point.kind, point.back_pressure),
                required_pressure=pressure, flow=a * speed, return_flow=opposite * speed,
                speed=speed, duration=point.travel / speed, theoretical_bore=theoretical,
                nominal_bore=nominal, required_regenerative_rod=rod_min,
                nominal_regenerative_rod=None if rod_nominal is None else rod_nominal / 1000,
                buckling=buckling(c, point.force if point.kind != 'retract' else 0.))
