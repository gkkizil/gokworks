"""SI sınır dönüşümleri. psi: uluslararası pound/in²; gpm: ABD galonu/dakika."""
from .validation import finite, InputError

FACTORS = {'Pa': 1., 'bar': 1e5, 'MPa': 1e6, 'psi': 6894.757293168,
           'm3/s': 1., 'L/min': 1e-3 / 60, 'gpm': .003785411784 / 60,
           'm': 1., 'mm': .001, 'in': .0254, 'W': 1., 'kW': 1000.,
           'm3': 1., 'L': .001, 'm2/s': 1., 'cSt': 1e-6,
           'rad/s': 1., 'rpm': 2 * 3.141592653589793 / 60, 'N': 1., 'kN': 1000.,
           'm/s': 1., 'mm/s': .001, 's': 1., 'cm3/rev': 1e-6, 'm3/rev': 1.}
GROUPS = (('Pa','bar','MPa','psi'), ('m3/s','L/min','gpm'), ('m','mm','in'),
          ('W','kW'), ('m3','L'), ('m2/s','cSt'), ('rad/s','rpm'), ('N','kN'),
          ('m/s','mm/s'), ('s',), ('cm3/rev','m3/rev'))


def convert(value: float, source: str, target: str) -> float:
    finite(value, 'birim')
    if source == target and source in ('°C', 'K'):
        return value
    if (source, target) == ('°C', 'K'):
        return value + 273.15
    if (source, target) == ('K', '°C'):
        return value - 273.15
    if not any(source in g and target in g for g in GROUPS):
        raise InputError('birim', 'Birim boyutları uyuşmuyor.')
    return value * FACTORS[source] / FACTORS[target]
