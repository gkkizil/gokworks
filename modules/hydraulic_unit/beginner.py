"""Kolay giriş için saf Python dönüştürücüleri; hesap motoru yerine geçmez."""
from dataclasses import replace
from .core.models import Project, Phase
from .core.validation import InputError, number

STANDARD_GRAVITY = 9.80665
FORCE_FACTORS = {'kN': 1000., 'tonf': 1000 * STANDARD_GRAVITY}


def force_to_newtons(value: float, unit: str) -> float:
    """Ton-kuvvet ağırlık kütlesi değil, standart yerçekimine bağlı kuvvettir."""
    number(value,'force',zero=True)
    if unit not in FORCE_FACTORS: raise InputError('force','Geçersiz kuvvet birimi.')
    return value * FORCE_FACTORS[unit]


def phase_seconds(phase: Phase) -> float:
    if phase.duration is not None: return phase.duration
    return phase.stroke / number(phase.speed,'speed')


def simple_supported(project: Project) -> bool:
    """Karmaşık projeler kolay girişe indirgenmez; ayrıntılı görünümde açılır."""
    return (len(project.cylinders) == 1 and 1 <= len(project.phases) <= 12
            and all(p.cylinder_id == project.cylinders[0].id for p in project.phases))


def basic_cycle(project: Project) -> Project:
    """Mevcut ölçü/ayarları koruyarak örnek bir ileri–bekle–geri sırası kurar."""
    if not simple_supported(project): raise InputError('project','Bu proje için ayrıntılı görünümü kullanın.')
    cylinder = project.cylinders[0]
    travel = cylinder.stroke - cylinder.initial_position
    number(travel,'stroke')
    force = max((p.force for p in project.phases if p.kind in ('extend','regenerate')), default=10000.)
    phases = (Phase('İleri hareket',cylinder.id,'extend',force,travel,None,5.),
              Phase('Bekleme',cylinder.id,'hold',force,travel,None,2.),
              Phase('Geri hareket',cylinder.id,'retract',1000.,travel,None,5.))
    return replace(project,phases=phases)
