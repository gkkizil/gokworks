"""Conservative bolt-body screening; see docs/bolt-calculator.md for scope."""

from dataclasses import dataclass
from math import hypot, isfinite, pi, sqrt

# ISO metric coarse threads, diameter and pitch in mm.
THREADS = {f'M{d}': (d, p) for d, p in (
    (3, .5), (4, .7), (5, .8), (6, 1), (8, 1.25), (10, 1.5),
    (12, 1.75), (14, 2), (16, 2), (18, 2.5), (20, 2.5), (22, 2.5),
    (24, 3), (27, 3), (30, 3.5), (33, 3.5), (36, 4), (39, 4))}
# ISO 898-1 proof stress Sp, MPa. 8.8 has a separate value above M16.
PROOF_STRESS = {'4.6': 225., '5.6': 280., '8.8': 580., '10.9': 830., '12.9': 970.}
MODES = ('Çekme', 'Kesme', 'Birleşik yük')
UNITS = {'kN': 1000., 'N': 1., 'kgf': 9.80665}
SECTIONS = ('Dişli kesit', 'Dişsiz gövde')
PLANES = ('Tek kesme', 'Çift kesme')


def number(value, title, *, minimum=0., maximum=1e9, integer=False):
    try:
        result = float(str(value).strip().replace(',', '.'))
    except (TypeError, ValueError):
        raise ValueError(f'{title}: geçerli bir sayı girin.') from None
    if not isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f'{title}: {minimum:g}–{maximum:g} aralığında olmalı.')
    if integer and not result.is_integer():
        raise ValueError(f'{title}: tam sayı girin.')
    return result


@dataclass(frozen=True)
class Result:
    metric: str
    grade: str
    mode: str
    pitch: float
    count: int
    planes: int
    section: str
    safety_factor: float
    proof_stress: float
    tensile_area: float
    shear_area: float
    tension_n: float
    shear_n: float
    tensile_stress: float
    shear_stress: float
    equivalent_stress: float
    allowable_stress: float
    utilization: float
    available_factor: float | None
    tension_capacity_n: float
    shear_capacity_n: float

    @property
    def safe(self):
        return self.utilization <= 1.

    @property
    def loaded(self):
        return self.tension_n > 0 or self.shear_n > 0


def calculate(*, metric='M10', grade='8.8', mode='Çekme', tension='10', shear='0',
              unit='kN', count='1', safety_factor='2', section='Dişli kesit', planes='Tek kesme'):
    for value, choices, title in ((metric, THREADS, 'Metrik ölçü'), (grade, PROOF_STRESS, 'Kalite sınıfı'),
                                  (mode, MODES, 'Yük türü'), (unit, UNITS, 'Yük birimi'),
                                  (section, SECTIONS, 'Kesme kesiti'), (planes, PLANES, 'Kesme düzlemi')):
        if value not in choices:
            raise ValueError(f'{title}: listeden bir değer seçin.')
    bolts = int(number(count, 'Cıvata adedi', minimum=1, maximum=1000, integer=True))
    factor = number(safety_factor, 'Emniyet katsayısı', minimum=1, maximum=10)
    ft = number(tension, 'Çekme yükü')*UNITS[unit] if mode != 'Kesme' else 0.
    fv = number(shear, 'Kesme yükü')*UNITS[unit] if mode != 'Çekme' else 0.
    diameter, pitch = THREADS[metric]
    tensile_area = pi/4*(diameter-.938194*pitch)**2
    # Thread-root area is intentionally smaller than tensile stress area.
    shear_area = pi/4*(diameter-1.226869*pitch)**2 if section == 'Dişli kesit' else pi/4*diameter**2
    shear_planes = 2 if planes == 'Çift kesme' else 1
    proof = 600. if grade == '8.8' and diameter > 16 else PROOF_STRESS[grade]
    sigma = ft/(bolts*tensile_area)
    tau = fv/(bolts*shear_planes*shear_area)
    equivalent = hypot(sigma, sqrt(3)*tau)
    allowable = proof/factor
    return Result(metric, grade, mode, pitch, bolts, shear_planes, section, factor, proof,
                  tensile_area, shear_area, ft, fv, sigma, tau, equivalent, allowable,
                  equivalent/allowable, proof/equivalent if equivalent else None,
                  allowable*tensile_area*bolts, allowable/sqrt(3)*shear_area*bolts*shear_planes)


def fmt(value, digits=2):
    return f'{value:,.{digits}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


SCOPE = ('Statik yük ve eşit yük paylaşımı kabul edilir. Girilen çekme yükü cıvatalarda taşınan toplam kuvvettir. '
         'Ön sıkmalı bağlantıda dış yükü doğrudan bu alana girmeyin; ön yük ve bağlantı rijitliği ayrıca hesaplanmalıdır. '
         'Sonuç yalnızca cıvata gövdesi içindir; somun/diş sıyırması, plaka ezilmesi, kenar yırtılması, '
         'eksantrik yük, eğilme, yorulma, darbe ve sıcaklık etkileri bu hesaba dahil değildir.')
