"""Ft is a force DIFFERENCE, not pretension, total tension or bearing load."""

import math
from .._numbers import positive, integer, checked
from ..models import ShaftForces


def effective_force_delta_n(power_kw, speed_m_s):
    return positive((positive(power_kw, 'Güç') / positive(speed_m_s, 'Kayış hızı')) * 1000., 'Etkin kuvvet farkı')


def simplified_shaft_forces(path, effective_delta_n, pretension_per_belt_n, count=1, rotation='ccw'):
    """Massless, constant mean tension, equal sharing; not a manufacturer procedure."""
    count = integer(count, 'Kayış adedi')
    initial = positive(pretension_per_belt_n, 'Kayış başına başlangıç gerilmesi')
    delta = positive(positive(effective_delta_n, 'Etkin kuvvet farkı') / count, 'Kayış başına etkin kuvvet farkı')
    tight, slack = positive(initial + delta / 2., 'Gergin kol'), initial - delta / 2.
    if slack <= 0:
        raise ValueError('F₀, nominal Ft/(2×adet) değerinden büyük olmalı; bu modelde gevşek kol gerilmesi pozitif kalmıyor.')
    if not math.isclose(tight - slack, delta, rel_tol=1e-11, abs_tol=1e-10):
        raise ValueError('Ön germe/yük oranı sayısal hassasiyeti aşıyor; F₁−F₂ farkı güvenilir temsil edilemiyor.')
    if rotation not in ('ccw', 'cw'):
        raise ValueError('Dönüş yönü ccw veya cw olmalı.')
    upper, lower = (tight, slack) if rotation == 'ccw' else (slack, tight)
    force = (path.upper_direction * upper + path.lower_direction * lower) * count
    return ShaftForces(initial, tight, slack, checked(force.x, 'Mil Fx'), checked(force.y, 'Mil Fy'),
                       -force.x, -force.y, positive(math.hypot(force.x, force.y), 'Mil bileşkesi'))
