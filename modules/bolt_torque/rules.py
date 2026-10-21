"""Quick torque estimate in N·m; no GUI, CAD, FEA or joint-design dependency.

T = K F d; F = As * yield_reference * preload_percent / 100.
Lengths enter in mm; only the torque lever arm is converted to metres.
Mechanical-property bases are explicit; see docs/bolt-torque.md.
"""

from dataclasses import dataclass
from math import isfinite, pi

from modules.bolt.rules import THREADS, pitch_choices as bolt_pitch_choices, thread_geometry


METRICS = tuple(name for name, (diameter, _) in THREADS.items() if 3 <= diameter <= 36)
GRADES = ('4.8', '5.8', '8.8', '10.9', '12.9')
THREAD_SERIES = ('Normal diş', 'İnce diş')
CONDITIONS = ('Kuru', 'Hafif yağlı')
DEFAULT_K = {'Kuru': .20, 'Hafif yağlı': .15}
K_ASSUMPTION = ('Kuru K = 0,20 ve hafif yağlı K = 0,15 yaklaşık varsayımlardır. '
                'Gerçek K, kaplama, yağ ve yüzey koşullarına bağlıdır.')
K_SURFACE_GUIDE = (
    ('0,10–0,13', 'Pürüzsüz, çok iyi yağlanmış yüzey'),
    ('0,15', 'Hafif yağlı standart çelik'),
    ('0,20', 'Kuru, kaplamasız standart çelik'),
    ('0,22–0,25', 'Bazı kuru çinko kaplamalı yüzeyler'),
    ('0,30+', 'Yüksek sürtünme; doğrulanmış veri gerekir'),
)
K_GUIDE_NOTE = ('Yaklaşık başvuru değerleridir; yüzey, kaplama ve yağlayıcıya göre değişir. '
                'Paslı/kirli cıvatalarda bu tabloyu kullanmayın.')
MANUFACTURER_NOTE = 'Kritik bağlantılarda üretici şartnamesini esas alın.'


@dataclass(frozen=True)
class Strength:
    mpa: float
    symbol: str
    basis: str


# ISO 898-1:2013 mechanical-property definitions, kept separate from proof
# stress Sp in bolt.rules. 4.8/5.8 use nominal Rp0.2 (320/400), not the full-size
# permanent-set-test values Rpf (340/420), which are a different property.
# Other classes use their minimum yield/0.2% proof strengths, including the
# 8.8 diameter boundary. This basis is shown in the UI and copied result.
STRENGTHS = {
    '4.8': Strength(320., 'Rp0,2', 'ISO 898-1 · nominal Rp0,2'),
    '5.8': Strength(400., 'Rp0,2', 'ISO 898-1 · nominal Rp0,2'),
    '8.8': Strength(640., 'ReL', 'ISO 898-1 · minimum ReL · d ≤ 16 mm'),
    '10.9': Strength(940., 'Rp0,2', 'ISO 898-1 · minimum Rp0,2'),
    '12.9': Strength(1100., 'Rp0,2', 'ISO 898-1 · minimum Rp0,2'),
}
LARGE_88 = Strength(660., 'ReL', 'ISO 898-1 · minimum ReL · d > 16 mm')


def _choice(value, choices, title):
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f'{title}: listeden bir değer seçin.')
    return value


def _number(value, title):
    if isinstance(value, bool):
        raise ValueError(f'{title}: geçerli bir sayı girin.')
    try:
        result = float(str(value).strip().replace(',', '.'))
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f'{title}: geçerli bir sayı girin.') from None
    if not isfinite(result):
        raise ValueError(f'{title}: sonlu bir sayı girin.')
    return result


def pitch_choices(metric, thread_series='Normal diş'):
    _choice(metric, METRICS, 'Cıvata ölçüsü')
    _choice(thread_series, THREAD_SERIES, 'Diş türü')
    return bolt_pitch_choices(metric, 'Kaba diş' if thread_series == 'Normal diş' else 'İnce diş')


def strength_for(metric, grade):
    _choice(metric, METRICS, 'Cıvata ölçüsü')
    _choice(grade, GRADES, 'Kalite sınıfı')
    return LARGE_88 if grade == '8.8' and THREADS[metric][0] > 16 else STRENGTHS[grade]


@dataclass(frozen=True)
class Result:
    metric: str
    diameter_mm: float
    pitch_mm: float
    thread_series: str
    grade: str
    condition: str
    k: float
    preload_percent: float
    tensile_area_mm2: float
    yield_strength_mpa: float
    strength_symbol: str
    strength_basis: str
    preload_n: float
    torque_nm: float

    @property
    def preload_kn(self):
        return self.preload_n / 1000

    @property
    def diameter_m(self):
        return self.diameter_mm / 1000

    @property
    def custom_k(self):
        return self.k != DEFAULT_K[self.condition]


def calculate(*, metric='M10', thread_series='Normal diş', pitch=None,
              grade='8.8', condition='Kuru', k=None, preload_percent=70):
    """Return an estimate for one bolt; K may override the condition default.

    ``preload_percent`` is a percentage (70 means 0.70), from 0 to 100.
    A zero target has zero preload/torque. K must be finite and positive.
    The selected metric and pitch must belong to the curated metric series.
    """
    choices = pitch_choices(metric, thread_series)
    selected_pitch = choices[0] if pitch is None else _number(pitch, 'Diş adımı')
    if selected_pitch not in choices:
        raise ValueError('Diş adımı: seçili çap ve diş türüne uygun bir adım seçin.')
    strength = strength_for(metric, grade)
    _choice(condition, CONDITIONS, 'Bağlantı koşulu')
    coefficient = DEFAULT_K[condition] if k is None else _number(k, 'K tork katsayısı')
    if coefficient <= 0:
        raise ValueError('K tork katsayısı sıfırdan büyük olmalı.')
    percent = _number(preload_percent, 'Hedef ön yük oranı')
    if not 0 <= percent <= 100:
        raise ValueError('Hedef ön yük oranı %0–100 aralığında olmalı.')
    diameter, selected_pitch = thread_geometry(metric,
        'Kaba diş' if thread_series == 'Normal diş' else 'İnce diş', selected_pitch)
    area = pi / 4 * (diameter - .938194 * selected_pitch) ** 2
    preload = area * strength.mpa * (percent / 100)
    # Multiply the dimensionless lever-arm factor first to avoid an
    # avoidable overflow for a large, but finite, user-entered coefficient.
    torque = coefficient * (preload * diameter / 1000)
    if not isfinite(torque):
        raise ValueError('K tork katsayısı hesaplanamayacak kadar büyük.')
    return Result(metric, diameter, selected_pitch, thread_series, grade, condition,
                  coefficient, percent, area, strength.mpa, strength.symbol,
                  strength.basis, preload, torque)
