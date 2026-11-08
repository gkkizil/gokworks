"""Darcy–Weisbach/Blasius ve ASTM D341 Walther ön tasarım hesabı.

Walther: log10(log10(ν[cSt]+0.7)) = A-B log10(T[K]). İki noktalı
bağıntı burada ν>2 cSt için uygulanır; gerçek yağ ürün eğrisi gereklidir.
"""
import math
from dataclasses import replace
from .models import Oil, Pipe
from .catalogs import PIPE_IDS_MM, OIL_EXAMPLES, SPEED_RANGES, select_up
from .validation import number, finite, choice, InputError


def viscosity(oil: Oil) -> float:
    choice(oil.grade, ('ISO VG 32','ISO VG 46','ISO VG 68','Custom'), 'oil.grade')
    for key in ('nu40','nu100','temperature','density'):
        number(getattr(oil, key), 'oil.' + key)
    if oil.nu100 >= oil.nu40 or oil.nu100 <= 2e-6:
        raise InputError('oil.nu100', 'ν40 > ν100 > 2 cSt olmalı.')
    if oil.grade in OIL_EXAMPLES:
        nominal = OIL_EXAMPLES[oil.grade][0]
        if not .9 * nominal <= oil.nu40 <= 1.1 * nominal:
            raise InputError('oil.nu40', '40 °C viskozitesi seçilen ISO VG sınıfının ±%10 aralığında değil; Custom seçin.')
    if not oil.source.strip():
        raise InputError('oil.source', 'Yağ verisinin kaynağı veya örnek olduğu yazılmalı.')
    y40 = math.log10(math.log10(oil.nu40 * 1e6 + .7))
    y100 = math.log10(math.log10(oil.nu100 * 1e6 + .7))
    b = (y40 - y100) / (math.log10(373.15) - math.log10(313.15))
    y = y40 - b * (math.log10(oil.temperature) - math.log10(313.15))
    try:
        nu = (10 ** (10 ** y) - .7) * 1e-6
    except OverflowError as exc:
        raise InputError('oil.temperature', 'Sıcaklık viskozite bağıntısının dışında.') from exc
    if not math.isfinite(nu) or nu <= 2e-6:
        raise InputError('oil.temperature', 'Walther basit bağıntısı bu sıcaklıkta ν > 2 cSt gerektirir.')
    return nu


def oil_for_grade(grade: str, **overrides) -> Oil:
    """Kaynağı açıkça örnek olarak işaretli yağ eğrisi oluşturur."""
    choice(grade, OIL_EXAMPLES, 'oil.grade')
    nu40,nu100 = OIL_EXAMPLES[grade]
    oil = replace(Oil(grade=grade,nu40=nu40,nu100=nu100),**overrides)
    viscosity(oil)
    return oil


def recommended_velocity(role: str, pressure: float = 0.) -> tuple[float,float]:
    """Görev tanımı ön seçim hızları; ürün uygunluğu değildir."""
    choice(role,SPEED_RANGES,'pipe.role'); number(pressure,'pressure',zero=True)
    return (5.,8.) if role == 'pressure' and pressure > 200e5 else SPEED_RANGES[role]


def diameter_for_flow(flow: float, velocity: float) -> float:
    number(flow, 'flow', zero=True); number(velocity, 'velocity')
    return math.sqrt(4 * flow / (math.pi * velocity))


def pipe_result(pipe: Pipe, flow: float, oil: Oil) -> dict:
    choice(pipe.role, ('suction','pressure','return'), 'pipe.role')
    for key in ('target_velocity','min_velocity','max_velocity'):
        number(getattr(pipe, key), 'pipe.' + key)
    if pipe.min_velocity >= pipe.max_velocity:
        raise InputError('pipe.min_velocity', 'Hız alt sınırı üst sınırdan küçük olmalı.')
    number(pipe.length, 'pipe.length', zero=True); number(flow, 'flow', zero=True)
    for value in pipe.zeta:
        number(value, 'pipe.zeta', zero=True)
    nu = viscosity(oil)
    theoretical = diameter_for_flow(flow, pipe.target_velocity)
    nominal = select_up(theoretical * 1000, PIPE_IDS_MM)
    diameter = pipe.diameter if pipe.diameter is not None else (None if nominal is None else nominal / 1000)
    if diameter is None:
        return dict(required_diameter=theoretical, diameter=None, velocity=None, reynolds=None,
                    friction_factor=None, pressure_drop=None, regime='NOT_EVALUATED', flow=flow)
    number(diameter, 'pipe.diameter')
    velocity = 4 * flow / (math.pi * diameter**2)
    re = velocity * diameter / nu
    regime = 'laminar' if re < 2300 else 'transition' if re < 4000 else 'turbulent' if re <= 1e5 else 'outside_blasius'
    laminar = (75 if pipe.hose_laminar else 64) / re if re else 0.
    turbulent = .3164 / re**.25 if re else 0.
    factor = laminar if re < 2300 else max(laminar, turbulent) if re < 4000 else turbulent
    loss = (factor * pipe.length / diameter + sum(pipe.zeta)) * oil.density * velocity**2 / 2
    finite(loss, 'pipe.pressure_drop')
    return dict(required_diameter=theoretical, diameter=diameter, velocity=velocity, reynolds=re,
                friction_factor=factor, pressure_drop=loss, regime=regime, flow=flow)
