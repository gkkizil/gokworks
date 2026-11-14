"""Plain full-stroke, out-and-back inputs; engineering stays in core.service."""
from dataclasses import dataclass, replace
import math

from .beginner import FORCE_FACTORS, force_to_newtons, phase_seconds
from .core.cylinder import areas, buckling
from .core.models import Phase, Project
from .core.validation import InputError, number


@dataclass(frozen=True)
class PracticalInputs:
    bore: float = 63.
    rod: float = 36.
    stroke: float = 300.
    force: float = 3.
    extend_time: float = 5.
    return_time: float = 5.
    hold_time: float = 0.
    return_force: float = 0.
    force_unit: str = 'tonf'


TITLES = {'bore': 'Silindirin iç çapı', 'rod': 'Parlak milin çapı', 'stroke': 'Gideceği yol (strok)',
          'force': 'İleri itme kuvveti', 'extend_time': 'İleri hareket süresi',
          'return_time': 'Geri dönüş süresi', 'hold_time': 'Uçta bekleme süresi',
          'return_force': 'Geri çekme kuvveti'}


def practical_project(base: Project, values: PracticalInputs) -> Project:
    """Replace only the single cylinder's dimensions and an explicitly chosen cycle."""
    if len(base.cylinders) != 1:
        raise InputError('practical.project', 'Birden fazla silindir için hareket planını veya ayrıntılı ayarları kullanın.')
    for key, title in TITLES.items():
        try:
            number(getattr(values, key), key, zero=key in ('force', 'hold_time', 'return_force'))
        except InputError:
            suffix = 'sıfır veya daha büyük' if key in ('force', 'hold_time', 'return_force') else 'sıfırdan büyük'
            raise InputError('practical.' + key, f'{title}: {suffix} bir sayı girin.') from None
    cylinder = replace(base.cylinders[0], bore=values.bore / 1000, rod=values.rod / 1000,
                       stroke=values.stroke / 1000, initial_position=0.)
    try:
        areas(cylinder); buckling(cylinder, 0)
    except InputError as error:
        key = error.field if error.field in ('bore', 'rod', 'stroke') else 'rod'
        message = 'Mil çapı, silindirin iç çapından küçük olmalı.' if key == 'rod' else str(error)
        raise InputError('practical.' + key, message) from None
    except ArithmeticError:
        raise InputError('practical.bore', 'Ölçü çok büyük; gerçek ölçüyü milimetre cinsinden girin.') from None
    force = force_to_newtons(values.force, values.force_unit)
    back = force_to_newtons(values.return_force, values.force_unit)
    for key, load in (('force',force),('return_force',back)):
        if not math.isfinite(load):raise InputError('practical.' + key, TITLES[key] + ': değer çok büyük.')
    old = {p.kind: p for p in base.phases} if practical_values(base) is not None else {}
    def phase(kind, name, load, duration):
        template = old.get(kind, Phase(name, cylinder.id, kind))
        return replace(template, force=load, stroke=cylinder.stroke, speed=None, duration=duration)
    phases = [phase('extend', 'İleri itme', force, values.extend_time)]
    if values.hold_time:
        phases.append(phase('hold', 'Uçta bekleme', force, values.hold_time))
    phases.append(phase('retract', 'Geri dönüş', back, values.return_time))
    return replace(base, cylinders=(cylinder,), phases=tuple(phases))


def practical_values(project: Project) -> PracticalInputs | None:
    """Only genuinely representable projects round-trip; never flatten a special plan."""
    if len(project.cylinders) != 1:
        return None
    c = project.cylinders[0]; phases = project.phases
    kinds = tuple(p.kind for p in phases)
    if (c.initial_position != 0 or kinds not in (('extend', 'retract'), ('extend', 'hold', 'retract'))
            or any(p.cylinder_id != c.id or p.back_pressure != 0 for p in phases)
            or any(not math.isclose(p.stroke, c.stroke, rel_tol=1e-12, abs_tol=1e-15)
                   for p in phases if p.kind in ('extend', 'retract'))):
        return None
    forward, backward = phases[0], phases[-1]
    hold = phases[1] if len(phases) == 3 else None
    if hold is not None and hold.force != forward.force:
        return None
    return PracticalInputs(c.bore * 1000, c.rod * 1000, c.stroke * 1000,
                           forward.force / FORCE_FACTORS['tonf'], phase_seconds(forward), phase_seconds(backward),
                           phase_seconds(hold) if hold else 0., backward.force / FORCE_FACTORS['tonf'])
