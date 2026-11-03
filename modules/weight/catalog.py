"""Verified standard-section library (EN 10365, EN 10056-1) loaded from data/sections.json.

Values come from manufacturer datasheets via data/extract_catalogue.py; each row was
checked against its own dimensions (area formula) and against area × 7850 = kg/m.
Families without a verified source (IPN, HL, small angles) are deliberately absent.
"""

from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path

from . import sections as s

DATA = Path(__file__).resolve().parent / 'data' / 'sections.json'
MISSING = ('IPN', 'HL', 'HE AA', 'küçük köşebentler (L < 120)')


@dataclass(frozen=True)
class Profile:
    family: str
    designation: str
    h: float
    b: float
    tw: float
    tf: float
    r: float
    r2: float
    area_cm2: float
    mass_kg_m: float
    sources: tuple
    differences: tuple

    @property
    def title(self):
        return display_name(self.family, self.designation)

    def geometric_area_mm2(self):
        """Area from the listed dimensions with the parallel-flange formulas."""
        shape = family_info(self.family)['shape']
        dims = dict(h=self.h, b=self.b, tw=self.tw, tf=self.tf, r=self.r, t=self.tf, r1=self.r)
        if shape == 'I':
            return s.i_section(dims)[0]
        if shape in ('U', 'U_tapered'):
            return s.channel(dims)[0]
        return s.angle(dict(b=self.b, h=self.h, t=self.tf, r1=self.r))[0]


def display_name(family, designation):
    """HE 200 A → HEA 200 (the common shop name); others unchanged."""
    if family in ('HEA', 'HEB', 'HEM'):
        parts = designation.split()
        return f'{family} {parts[1]}'
    return designation


@lru_cache(maxsize=1)
def load():
    return json.loads(DATA.read_text(encoding='utf-8'))


def families():
    return tuple(load()['families'])


def family_info(family):
    return load()['families'][family]


def sources():
    return load()['sources']


@lru_cache(maxsize=None)
def profiles(family):
    rows = family_info(family)['sections']
    return tuple(Profile(family, r['designation'], r['h'], r['b'], r['tw'], r['tf'], r['r'], r.get('r2', 0.0),
                         r['area_cm2'], r['mass_kg_m'], tuple(r['sources']), tuple(r.get('differences', ())))
                 for r in rows)


def profile(family, name):
    for item in profiles(family):
        if name in (item.designation, item.title):
            return item
    raise ValueError(f'{family} kütüphanesinde “{name}” bulunamadı.')


def source_text(item):
    info, docs = family_info(item.family), sources()
    parts = [f'{docs[key]["manufacturer"]} – {docs[key]["document"]} ({docs[key]["date"]})' for key in item.sources]
    return f'{info["standard"]} · ' + '; '.join(parts)


def validate():
    """Re-run the extraction checks on the shipped data (used by tests)."""
    problems = []
    basis = load()['density_basis_kg_m3']
    for family in families():
        for item in profiles(family):
            mass = item.area_cm2 * 1e-4 * basis
            if not math.isclose(mass, item.mass_kg_m, rel_tol=.006, abs_tol=.06):
                problems.append(f'{item.designation}: kütle')
            if family_info(family)['shape'] != 'U_tapered':
                if not math.isclose(item.geometric_area_mm2(), item.area_cm2 * 100, rel_tol=.004, abs_tol=6):
                    problems.append(f'{item.designation}: alan')
    return problems


__all__ = ['Profile', 'MISSING', 'display_name', 'families', 'family_info', 'profiles', 'profile',
           'source_text', 'validate', 'sources']
