"""Doğrulanan sınıflar için tabloyla ISO 286 limit ve geçme hesabı.

Tablo sapmaları tam sayı nanometredir; hesapta float ve yaklaşık IT formülü
kullanılmaz. Çap aralıkları alt sınır hariç, üst sınır dahil seçilir.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import json
from pathlib import Path
import re

MIN_DIAMETER, MAX_DIAMETER = Decimal('1'), Decimal('400')
CLASSIFICATION = {'clearance': 'Boşluklu geçme', 'transition': 'Ara geçme',
                  'interference': 'Sıkı geçme'}


@lru_cache(maxsize=1)
def _tables():
    data = json.loads(Path(__file__).with_name('tables.json').read_text(encoding='utf-8'))
    assert data['units'] == 'nm'
    return data


def classes(feature):
    if feature not in ('hole', 'shaft'):
        raise ValueError('Eleman delik veya mil olmalı.')
    return tuple(_tables()['holes' if feature == 'hole' else 'shafts'])


def diameter(value):
    if isinstance(value, bool):
        raise ValueError('Nominal çap sayısal olmalı.')
    text = str(value).strip()
    if not re.fullmatch(r'\+?(?:\d+(?:[.,]\d*)?|[.,]\d+)', text):
        raise ValueError('Nominal çap için sayı girin; virgül veya nokta kullanabilirsiniz.')
    try:
        number = Decimal(text.replace(',', '.'))
    except InvalidOperation:
        raise ValueError('Nominal çap sayısal olmalı.') from None
    if not number.is_finite() or not MIN_DIAMETER <= number <= MAX_DIAMETER:
        raise ValueError('Doğrulanan tablo aralığı: 1–400 mm.')
    # Keep exact calculation within Decimal's default precision.
    if number.as_tuple().exponent < -9:
        raise ValueError('Nominal çap en fazla 9 ondalık basamak içerebilir.')
    return number


def mm(nanometres):
    return Decimal(nanometres) / Decimal(1_000_000)


def format_mm(value, *, signed=False):
    places = max(6, min(9, -value.as_tuple().exponent))
    text = format(value, f'+.{places}f' if signed else f'.{places}f')
    if Decimal(text) == 0:
        text = ('+' if signed else '')+'0.'+'0'*places
    return text.replace('.', ',')


def format_deviation(nanometres, unit='mm'):
    if unit == 'mm':
        return format_mm(mm(nanometres), signed=True)+' mm'
    if unit != 'µm':
        raise ValueError('Birim mm veya µm olmalı.')
    value = Decimal(nanometres)/1000
    places = max(1, min(3, -value.as_tuple().exponent))
    return format(value, f'+.{places}f').replace('.', ',')+' µm'


@dataclass(frozen=True)
class LimitBand:
    code: str
    nominal_mm: Decimal
    upper_nm: int
    lower_nm: int
    bracket_mm: tuple[int, int]

    @property
    def minimum_mm(self):
        return self.nominal_mm+mm(self.lower_nm)

    @property
    def maximum_mm(self):
        return self.nominal_mm+mm(self.upper_nm)

    @property
    def tolerance_nm(self):
        return self.upper_nm-self.lower_nm


def limits(nominal, code, feature):
    nominal = diameter(nominal)
    if code not in classes(feature):
        raise ValueError(f"Desteklenmeyen {'delik' if feature == 'hole' else 'mil'} sınıfı: {code}")
    data = _tables()
    index = next(i for i, upper in enumerate(data['bounds_mm']) if nominal <= upper)
    upper, lower = data['classes'][code][index]
    bracket = (0 if index == 0 else data['bounds_mm'][index-1], data['bounds_mm'][index])
    return LimitBand(code, nominal, upper, lower, bracket)


@dataclass(frozen=True)
class Fit:
    hole: LimitBand
    shaft: LimitBand

    @property
    def minimum_clearance_nm(self):
        return self.hole.lower_nm-self.shaft.upper_nm

    @property
    def maximum_clearance_nm(self):
        return self.hole.upper_nm-self.shaft.lower_nm

    @property
    def kind(self):
        if self.minimum_clearance_nm >= 0:
            return 'clearance'
        if self.maximum_clearance_nm <= 0:
            return 'interference'
        return 'transition'

    @property
    def minimum_interference_nm(self):
        return max(0, -self.maximum_clearance_nm)

    @property
    def maximum_interference_nm(self):
        return max(0, -self.minimum_clearance_nm)

    def sample(self, selection):
        if selection == 'En az boşluk':
            return self.hole.minimum_mm, self.shaft.maximum_mm
        if selection == 'En çok boşluk':
            return self.hole.maximum_mm, self.shaft.minimum_mm
        if selection == 'Orta değer':
            return ((self.hole.minimum_mm+self.hole.maximum_mm)/2,
                    (self.shaft.minimum_mm+self.shaft.maximum_mm)/2)
        raise ValueError('Geçersiz örnek boyut seçimi.')


def calculate(nominal, hole='H8', shaft='f7'):
    return Fit(limits(nominal, hole, 'hole'), limits(nominal, shaft, 'shaft'))


@dataclass(frozen=True)
class Preset:
    hole: str
    shaft: str
    label: str

    @property
    def code(self):
        return f'{self.hole} / {self.shaft}'


PRESETS = (
    Preset('H11', 'c11', 'Geniş boşluk'),
    Preset('H9', 'd9', 'Serbest hareket'),
    Preset('H8', 'e8', 'Boşluklu kılavuzlama'),
    Preset('H8', 'f7', 'Hareketli eşleşme'),
    Preset('H7', 'g6', 'Küçük pozitif boşluk'),
    Preset('H7', 'h6', 'Sıfır minimum boşluk'),
    Preset('H8', 'h7', 'Kayar eşleşme'),
    Preset('H7', 'js6', 'Simetrik mil bölgesi'),
    Preset('H7', 'k6', 'Konumlandırma'),
    Preset('H7', 'm6', 'Dar ara eşleşme'),
    Preset('H7', 'n6', 'Sıkılığa yaklaşan eşleşme'),
    Preset('H7', 'p6', 'Sıkılık için değerlendirme'),
    Preset('H7', 'r6', 'Daha büyük sıkılık'),
    Preset('H7', 's6', 'Yüksek sıkılık'),
)
