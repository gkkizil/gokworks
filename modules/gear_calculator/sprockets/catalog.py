"""Tsubaki BS/DIN GT4 Winner, single-strand primary dimensions (mm).

https://tsubaki.eu/products/chain/drive-chain/standard-roller-chain/bs-din-gt4-winner/
Checked 2026-10-28. Four dimensional records, not copied catalogue artwork/tables.
ANSI chains are deliberately absent: equal pitch does not imply compatibility.
"""
from types import MappingProxyType
from .models import ChainSpecification

CATALOG_SOURCE='https://tsubaki.eu/products/chain/drive-chain/standard-roller-chain/bs-din-gt4-winner/'
CHAINS=MappingProxyType({s:ChainSpecification(series=s,pitch_mm=p,roller_diameter_mm=d,inner_width_mm=b)
    for s,p,d,b in [('08B-1',12.7,8.51,7.75),('10B-1',15.875,10.16,9.65),
                    ('12B-1',19.05,12.07,11.68),('16B-1',25.4,15.88,17.02)]})


def maximum_tooth_width(chain):
    return chain.inner_width_mm*(.93 if chain.pitch_mm<=12.7 else .95)
