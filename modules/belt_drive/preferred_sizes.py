"""Renard R40 preferred dimensions, not a manufacturer's stock catalogue.

ISO 3 defines preferred numbers. Applying them here to nominal diameters or
datum lengths does NOT certify ISO 4183/4184 compliance or product availability.
"""

from decimal import Decimal
from ._numbers import positive

R40_MANTISSAS = (100,106,112,118,125,132,140,150,160,170,180,190,200,212,224,236,
                250,265,280,300,315,335,355,375,400,425,450,475,500,530,560,600,
                630,670,710,750,800,850,900,950)


def preferred_sizes(minimum_mm, maximum_mm):
    low=positive(minimum_mm,'Tercihli ölçü alt sınırı')
    high=positive(maximum_mm,'Tercihli ölçü üst sınırı')
    if low>high:
        raise ValueError('Tercihli ölçü alt sınırı üst sınırı aşamaz.')
    if low<.001 or high>1e7:
        raise ValueError('Tercihli ölçü üretimi 0.001–10000000 mm aralığındadır.')
    return tuple(float(Decimal(n).scaleb(exponent-2)) for exponent in range(-3,8)
                 for n in R40_MANTISSAS if low<=float(Decimal(n).scaleb(exponent-2))<=high)


# Reference screening values: supplied technical handbook printed p.76, Table 4.
# These are not manufacturer capacity/minimum-diameter approval or groove CAD data.
REFERENCE_MIN_DATUM_MM = {'Z':50.,'A':75.,'B':125.,'C':200.,'D':355.,
                          'SPZ':63.,'SPA':90.,'SPB':140.,'SPC':224.}
