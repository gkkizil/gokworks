"""Conservative bolt-body screening; see docs/bolt-calculator.md for scope."""

from dataclasses import dataclass
from math import ceil, hypot, isfinite, pi, sqrt

# ISO metric coarse threads, diameter and pitch in mm.
THREADS = {f'M{d}': (d, p) for d, p in (
    (3, .5), (4, .7), (5, .8), (6, 1), (8, 1.25), (10, 1.5),
    (12, 1.75), (14, 2), (16, 2), (18, 2.5), (20, 2.5), (22, 2.5),
    (24, 3), (27, 3), (30, 3.5), (33, 3.5), (36, 4), (39, 4))}
# Curated fine pitches: BAT metric fine geometry, plus ISO 262 M33/M39.
# This list is not a claim that every option is an ISO 8676 hex-head size.
FINE_PITCHES = {f'M{d}': pitches for d, pitches in (
    (3, (.35,)), (4, (.5,)), (5, (.5,)), (6, (.75,)),
    (8, (1., .75)), (10, (1.25, 1., .75)), (12, (1.5, 1.25, 1.)),
    (14, (1.5, 1.25, 1.)), (16, (1.5, 1.)), (18, (2., 1.5, 1.)),
    (20, (2., 1.5, 1.)), (22, (2., 1.5, 1.)), (24, (2., 1.5, 1.)),
    (27, (2., 1.5, 1.)), (30, (3., 2., 1.5)), (33, (2.,)),
    (36, (3., 2., 1.5)), (39, (3.,)))}
THREAD_SERIES = ('Kaba diş', 'İnce diş')
# ISO 262 selected fine pitches; additional fine geometry remains available.
STANDARD_FINE_PITCHES = {f'M{d}': pitches for d, pitches in (
    (8, (1.,)), (10, (1.25, 1.)), (12, (1.5, 1.25)),
    (14, (1.5,)), (16, (1.5,)), (18, (2., 1.5)),
    (20, (2., 1.5)), (22, (2., 1.5)), (24, (2.,)),
    (27, (2.,)), (30, (2.,)), (33, (2.,)), (36, (3.,)), (39, (3.,)))}
# ISO 898-1 coarse proof stress Sp, MPa. 8.8 differs above M16.
# Fine threads retain these conservative bounds; see docs for the material basis.
PROOF_STRESS = {'4.6': 225., '5.6': 280., '8.8': 580., '10.9': 830., '12.9': 970.}
MODES = ('Çekme', 'Kesme', 'Birleşik yük')
UNITS = {'kg': 9.80665, 'N': 1., 'kN': 1000., 'kgf': 9.80665}
UNIT_LABELS = {'kg': 'kg yük', 'N': 'Newton (N)', 'kN': 'kN'}
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


def pitch_choices(metric, thread_series='Kaba diş'):
    if metric not in THREADS:
        raise ValueError('Metrik ölçü: listeden bir değer seçin.')
    if thread_series not in THREAD_SERIES:
        raise ValueError('Diş türü: listeden bir değer seçin.')
    return (THREADS[metric][1],) if thread_series == 'Kaba diş' else FINE_PITCHES[metric]


def thread_geometry(metric, thread_series='Kaba diş', pitch=None):
    choices = pitch_choices(metric, thread_series)
    selected = choices[0] if pitch is None else number(pitch, 'Diş adımı', minimum=.01, maximum=10)
    if selected not in choices:
        raise ValueError('Diş adımı: seçili çap ve diş türü için listeden bir değer seçin.')
    return THREADS[metric][0], selected


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
    unit: str
    thread_series: str = 'Kaba diş'

    @property
    def safe(self):
        return self.utilization <= 1.

    @property
    def loaded(self):
        return self.tension_n > 0 or self.shear_n > 0

    @property
    def tension_utilization(self):
        return self.tensile_stress/self.allowable_stress

    @property
    def shear_utilization(self):
        return sqrt(3)*self.shear_stress/self.allowable_stress

    @property
    def safety_margin(self):
        """Proportional load increase to the selected limit; not a yield margin."""
        return 1/self.utilization-1 if self.utilization > 0 else None

    @property
    def minimum_count(self):
        """Required equal-sharing count, including counts beyond the input limit."""
        if not self.loaded:
            return None

        def stress(count):
            return hypot(self.tension_n/(count*self.tensile_area),
                         sqrt(3)*(self.shear_n/(count*self.planes*self.shear_area)))

        count = max(1, ceil(stress(1)/self.allowable_stress))
        # Check integer boundaries with the same arithmetic as calculate().
        # A tolerance here could recommend a count that still fails the check.
        if stress(count)/self.allowable_stress > 1:
            count += 1
        if count > 1 and stress(count-1)/self.allowable_stress <= 1:
            count -= 1
        return count

    @property
    def tension_limit_with_shear_n(self):
        """Total admissible tension with the current shear held fixed."""
        if self.shear_utilization > 1:
            return None
        return self.tension_capacity_n*sqrt(max(0., 1-self.shear_utilization**2))

    @property
    def shear_limit_with_tension_n(self):
        """Total admissible shear with the current tension held fixed."""
        if self.tension_utilization > 1:
            return None
        return self.shear_capacity_n*sqrt(max(0., 1-self.tension_utilization**2))


def calculate(*, metric='M10', grade='8.8', mode='Çekme', tension='10', shear='0',
              unit='kN', count='1', safety_factor='2', section='Dişli kesit', planes='Tek kesme',
              thread_series='Kaba diş', pitch=None):
    for value, choices, title in ((metric, THREADS, 'Metrik ölçü'), (grade, PROOF_STRESS, 'Kalite sınıfı'),
                                  (mode, MODES, 'Yük türü'), (unit, UNITS, 'Yük birimi'),
                                  (section, SECTIONS, 'Kesme kesiti'), (planes, PLANES, 'Kesme düzlemi')):
        if value not in choices:
            raise ValueError(f'{title}: listeden bir değer seçin.')
    bolts = int(number(count, 'Cıvata adedi', minimum=1, maximum=1000, integer=True))
    factor = number(safety_factor, 'Emniyet katsayısı', minimum=1, maximum=10)
    ft = number(tension, 'Çekme yükü')*UNITS[unit] if mode != 'Kesme' else 0.
    fv = number(shear, 'Kesme yükü')*UNITS[unit] if mode != 'Çekme' else 0.
    diameter, pitch = thread_geometry(metric, thread_series, pitch)
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
                  allowable*tensile_area*bolts, allowable/sqrt(3)*shear_area*bolts*shear_planes,
                  'kg' if unit == 'kgf' else unit, thread_series)


def fmt(value, digits=2):
    return f'{value:,.{digits}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def force_text(force_n, unit):
    suffix = 'kg yük' if unit in ('kg', 'kgf') else unit
    return f'{fmt(force_n/UNITS[unit])} {suffix}'


SCOPE = ('Statik yük ve eşit yük paylaşımı kabul edilir. Girilen çekme yükü cıvatalarda taşınan toplam kuvvettir. '
         'Ön sıkmalı bağlantıda dış yükü doğrudan bu alana girmeyin; ön yük ve bağlantı rijitliği ayrıca hesaplanmalıdır. '
         'Sonuç yalnızca cıvata gövdesi içindir; somun/diş sıyırması, plaka ezilmesi, kenar yırtılması, '
         'eksantrik yük, eğilme, yorulma, darbe ve sıcaklık etkileri bu hesaba dahil değildir.')
