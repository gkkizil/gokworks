"""Nominal seçim serileri ve açık mühendislik varsayımları.

Seriler kullanıcı görev tanımından alınmıştır; ISO 3320/IEC tam metni veya
üretici kataloğu doğrulaması değildir. Basınçlar tipik ön tasarım uyarılarıdır.
"""
BORES_MM = (25, 32, 40, 50, 63, 80, 100, 125, 140, 160, 180, 200, 250)
RODS_MM = (12, 14, 18, 22, 28, 36, 45, 56, 70, 90, 110, 140)
MOTORS_KW = (.37, .55, .75, 1.1, 1.5, 2.2, 3, 4, 5.5, 7.5, 11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90, 110)
ACCUMULATORS_L = (.7, 1, 2.5, 4, 6, 10, 20, 32, 50)
PIPE_IDS_MM = (6, 8, 10, 12, 16, 19, 25, 32, 38, 50, 63, 76, 100)
PUMP_CC = (4, 6, 8, 10, 12, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200)
# ηv, ηhm, varsayımsal nominal üst basınç (Pa); ürün garantisi değildir.
PUMP_DEFAULTS = {'gear': (.95, .90, 250e5), 'vane': (.92, .90, 160e5),
                 'axial_fixed': (.96, .93, 350e5), 'axial_variable': (.96, .93, 350e5)}
PUMP_LABELS = {'gear': 'Dişli', 'vane': 'Paletli', 'axial_fixed': 'Eksenel pistonlu, sabit',
               'axial_variable': 'Eksenel pistonlu, değişken'}
MOUNT_K = {'fixed_free': 2., 'pinned_pinned': 1., 'fixed_pinned': .699, 'fixed_fixed': .5}
SPEED_RANGES = {'suction': (.6, 1.2), 'pressure': (3., 6.), 'return': (2., 4.)}
MOTOR_RPM = {2: 2900., 4: 1450., 6: 960.}
ATMOSPHERE_PA = 101325.
DEFAULT_DENSITY = 870.
DEFAULT_E = 210e9
BUCKLING_SAFETY = 3.5
CYLINDER_EFFICIENCY = .95
RELIEF_FACTOR = 1.1
OVERLOAD = .10
DEBOUNCE_MS = 300
MAX_PHASES = 1000
SOURCE_NOTE = 'Görev tanımı nominal serileri; üretici ürün/kapasite onayı değildir.'
# ν40 / ν100 [m²/s]: yalnız örnek eğriler, üretici yağ katalog verisi değil.
OIL_EXAMPLES = {'ISO VG 32': (32e-6, 5.4e-6), 'ISO VG 46': (46e-6, 6.8e-6),
                'ISO VG 68': (68e-6, 8.7e-6)}


def select_up(value: float, series: tuple) -> float | None:
    """İhtiyacın altına inmeyen ilk nominal değer; seri dışında None."""
    return next((v for v in series if v >= value * (1 - 1e-12)), None)
