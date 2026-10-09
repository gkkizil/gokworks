"""Elle girilen sapmalardan geçme hesabı ve ISO tablo karşılaştırması."""

from dataclasses import dataclass
from decimal import Decimal
import re

from iso_fits.rules import Fit, LimitBand, PRESETS, calculate, classes, diameter, limits


def deviation_nm(value):
    if isinstance(value, bool):
        raise ValueError('Sapma sayısal olmalı.')
    text = str(value).strip().replace('−', '-')
    if not re.fullmatch(r'[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)', text):
        raise ValueError('Sapmayı mm olarak girin; örneğin +0,02 veya -0,02.')
    value = Decimal(text.replace(',', '.'))
    if value.as_tuple().exponent < -6 or abs(value) > 400:
        raise ValueError('Sapma en fazla 6 ondalık basamak ve ±400 mm aralığında olmalı.')
    return int(value*1_000_000)


def manual_band(nominal, lower, upper, feature):
    # Reuse the verified diameter range and table interval definition.
    reference = limits(nominal, 'H7' if feature == 'hole' else 'h6', feature)
    lower, upper = deviation_nm(lower), deviation_nm(upper)
    title = 'Delik' if feature == 'hole' else 'Mil'
    if lower > upper:
        raise ValueError(f'{title}: alt sapma üst sapmadan büyük olamaz.')
    band = LimitBand('Manuel', reference.nominal_mm, upper, lower, reference.bracket_mm)
    if band.minimum_mm <= 0:
        raise ValueError(f'{title}: minimum ölçü sıfırdan büyük olmalı.')
    return band


def calculate_manual(nominal, hole_lower, hole_upper, shaft_lower, shaft_upper):
    nominal = diameter(nominal)
    return Fit(manual_band(nominal, hole_lower, hole_upper, 'hole'),
               manual_band(nominal, shaft_lower, shaft_upper, 'shaft'))


@dataclass(frozen=True)
class Match:
    code: str
    lower_difference_nm: int
    upper_difference_nm: int

    @property
    def distance_nm(self):
        return abs(self.lower_difference_nm)+abs(self.upper_difference_nm)

    @property
    def exact(self):
        return self.distance_nm == 0


def compare_classes(band, feature):
    """Tam eşitliği ve alt/üst fark toplamıyla en yakın tabloları ayır."""
    matches = []
    for code in classes(feature):
        standard = limits(band.nominal_mm, code, feature)
        matches.append(Match(code, band.lower_nm-standard.lower_nm,
                             band.upper_nm-standard.upper_nm))
    return tuple(sorted(matches, key=lambda item: (item.distance_nm, item.code)))


def usage_hint(fit):
    """Pratik adlar öneridir; ISO sınıflaması Fit.kind tarafından hesaplanır."""
    if fit.kind == 'interference':
        return 'Sıkı geçme · pres/ısıl montaj değerlendirmesi'
    if fit.kind == 'transition':
        return 'Ara / konumlandırma geçmesi · ölçüye bağlı montaj'
    if fit.minimum_clearance_nm == 0:
        return ('Sınırda temas · tolerans aralığı yok' if fit.maximum_clearance_nm == 0
                else 'Kayar geçme adayı · sınırda temas')
    def distance(preset):
        standard = calculate(fit.hole.nominal_mm, preset.hole, preset.shaft)
        return sum(abs(a-b) for band, ref in ((fit.hole, standard.hole), (fit.shaft, standard.shaft))
                   for a, b in ((band.lower_nm, ref.lower_nm), (band.upper_nm, ref.upper_nm)))
    candidates = [p for p in PRESETS if calculate(fit.hole.nominal_mm, p.hole, p.shaft).kind == 'clearance']
    closest = min(candidates, key=distance)
    if closest.shaft in ('c11', 'd9'):
        return 'Bol / serbest geçme adayı'
    if closest.shaft in ('e8', 'f7', 'g6'):
        return 'Hareketli / yağlı çalışma adayı'
    return 'Boşluklu / kayar geçme adayı'
