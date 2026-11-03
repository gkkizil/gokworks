"""Resolve a user tolerance into exact deviations and SOLIDWORKS tolerance data.

ISO 286 limits come only from the verified table in ``modules.iso_fits``
(integer nanometres, 1–400 mm). A class or diameter outside that table is an
error; deviations are never estimated.
"""

from dataclasses import dataclass
from decimal import Decimal

from modules.iso_fits import rules as iso

# swTolType_e (verified against SOLIDWORKS 2024 interop, see drawing/README.md)
SW_TOL = {'none': 0, 'bilateral': 2, 'limit': 3, 'symmetric': 4, 'fit': 7, 'fit_with_tol': 8, 'fit_tol_only': 9}


@dataclass(frozen=True)
class Resolved:
    kind: str            # none / symmetric / bilateral / limit / iso_fit
    sw_type: int
    upper: float         # signed mm
    lower: float         # signed mm
    fit: str
    text: str            # tolerance part only, e.g. 'h6', '±0,02', '+0,00 / −0,03'

    def as_dict(self):
        return dict(kind=self.kind, sw_type=self.sw_type, upper_mm=self.upper, lower_mm=self.lower,
                    fit=self.fit, text=self.text)


def _fmt(value, signed=True, places=None):
    if places is None:
        places = max(2, min(4, -Decimal(repr(value)).normalize().as_tuple().exponent))
    text = f'{abs(value):.{places}f}'.replace('.', ',')
    if not signed:
        return text
    return ('−' if value < 0 else '+') + text


def resolve(spec, nominal, feature=''):
    """Return :class:`Resolved` or raise ``ValueError`` with a user-facing reason."""
    kind = spec.kind
    if kind == 'none':
        return Resolved('none', SW_TOL['none'], 0., 0., '', '')
    if kind == 'symmetric':
        return Resolved(kind, SW_TOL['symmetric'], spec.upper, -spec.upper, '', '±' + _fmt(spec.upper, signed=False))
    if kind == 'bilateral':
        return Resolved(kind, SW_TOL['bilateral'], spec.upper, spec.lower, '',
                        f'{_fmt(spec.upper)} / {_fmt(spec.lower)}')
    if kind == 'limit':
        upper, lower = nominal + spec.upper, nominal + spec.lower
        return Resolved(kind, SW_TOL['limit'], spec.upper, spec.lower, '',
                        f'{_fmt(upper, False, 3)} / {_fmt(lower, False, 3)}')
    if kind != 'iso_fit':
        raise ValueError('Tolerans türü desteklenmiyor.')
    if feature not in ('shaft', 'hole'):
        raise ValueError('ISO geçme yalnız çap ölçülerinde kullanılabilir.')
    code = spec.fit.strip()
    if code not in iso.classes(feature):
        family = 'mil' if feature == 'shaft' else 'delik'
        raise ValueError(f'{code}: doğrulanmış ISO 286 tablosunda olmayan {family} sınıfı. '
                         f'Desteklenenler: {", ".join(iso.classes(feature))}.')
    try:
        band = iso.limits(format(Decimal(repr(float(nominal))).normalize(), 'f'), code, feature)
    except ValueError as error:
        raise ValueError(f'Ø{_fmt(nominal, False)}: {error}') from None
    upper, lower = band.upper_nm / 1e6, band.lower_nm / 1e6
    deviations = f'{_fmt(upper)} / {_fmt(lower)}'
    if spec.display == 'class':
        return Resolved(kind, SW_TOL['fit'], upper, lower, code, code)
    if spec.display == 'deviations':
        return Resolved(kind, SW_TOL['fit_tol_only'], upper, lower, code, deviations)
    return Resolved(kind, SW_TOL['fit_with_tol'], upper, lower, code, f'{code} ({deviations})')
