"""Elle girilen sapmalardan geçme hesabı ve ISO tablo karşılaştırması."""

from dataclasses import dataclass
from decimal import Decimal
import re

from iso_fits.rules import (Fit, LimitBand, PRESETS, calculate, classes, diameter,
                            diameter_bracket, limits)


TARGETS = ('Genel kontrol', 'Serbest / kayar', 'Ara / konumlandırma', 'Sıkı / pres')


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
    classes(feature)  # Validate the feature independently of any ISO class.
    nominal = diameter(nominal)
    lower, upper = deviation_nm(lower), deviation_nm(upper)
    title = 'Delik' if feature == 'hole' else 'Mil'
    if lower > upper:
        raise ValueError(f'{title}: alt sapma üst sapmadan büyük olamaz.')
    band = LimitBand('Manuel', nominal, upper, lower, diameter_bracket(nominal))
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


def closest_classes(band, feature):
    """Return every equally near class; alphabetic order is not a preference."""
    matches = compare_classes(band, feature)
    return tuple(item for item in matches if item.distance_nm == matches[0].distance_nm)


@dataclass(frozen=True)
class PairMatch:
    fit: Fit
    distance_nm: int
    worst_limit_difference_nm: int
    beyond_reference_width: bool

    @property
    def code(self):
        return f'{self.fit.hole.code}/{self.fit.shaft.code}'


def _pair_match(fit, reference):
    differences = [abs(a-b) for band, ref in ((fit.hole, reference.hole), (fit.shaft, reference.shaft))
                   for a, b in ((band.lower_nm, ref.lower_nm), (band.upper_nm, ref.upper_nm))]
    beyond = any(abs(band.lower_nm-ref.lower_nm) > ref.tolerance_nm
                 or abs(band.upper_nm-ref.upper_nm) > ref.tolerance_nm
                 for band, ref in ((fit.hole, reference.hole), (fit.shaft, reference.shaft)))
    return PairMatch(reference, sum(differences), max(differences), beyond)


def closest_pair(fit):
    hole = compare_classes(fit.hole, 'hole')[0].code
    shaft = compare_classes(fit.shaft, 'shaft')[0].code
    return _pair_match(fit, calculate(fit.hole.nominal_mm, hole, shaft))


def closest_preset(fit):
    return min((_pair_match(fit, calculate(fit.hole.nominal_mm, p.hole, p.shaft)) for p in PRESETS),
               key=lambda item: (item.distance_nm, item.code))


@dataclass(frozen=True)
class Compatibility:
    status: str
    title: str
    explanation: str


def compatibility(fit, target='Genel kontrol'):
    if target not in TARGETS:
        raise ValueError('Geçersiz montaj hedefi.')
    low, high = fit.minimum_clearance_nm, fit.maximum_clearance_nm
    if target == 'Serbest / kayar':
        if low > 0:
            return Compatibility('compatible', 'Boşluklu hedefe boyutsal olarak uygun',
                                 'Tüm izin verilen ölçü kombinasyonlarında pozitif boşluk var.')
        if low == 0:
            return Compatibility('boundary', 'Sınırda temas; serbest montaj garanti değil',
                                 'Minimum boşluk sıfır. Yüzey ve şekil hataları montajı zorlaştırabilir.')
        return Compatibility('incompatible', 'Serbest/kayar hedefe tüm limitlerde uygun değil',
                             'Bazı veya tüm ölçü kombinasyonlarında mil delikten büyük; sıkılık oluşur.')
    if target == 'Sıkı / pres':
        if high < 0:
            return Compatibility('compatible', 'Sıkı hedefe boyutsal olarak uygun',
                                 'Tüm ölçü kombinasyonlarında sıkılık var. Pres kuvveti/ısıl montaj ayrıca hesaplanmalı.')
        if high == 0 and low < 0:
            return Compatibility('boundary', 'Sınırda temas; sıkılık garanti değil',
                                 'En az sıkılık sıfır; tüm parçalar için sıkı montaj garanti edilemez.')
        return Compatibility('incompatible', 'Sıkı/pres hedefe tüm limitlerde uygun değil',
                             'Sınırda temas veya boşluk oluşabilir; her parçada sıkılık yok.')
    if target == 'Ara / konumlandırma':
        if low < 0 < high:
            return Compatibility('compatible', 'Ara geçme hedefi oluşuyor',
                                 'Gerçekleşen ölçüye göre boşluk veya sıkılık mümkündür; montaj yöntemi değişebilir.')
        return Compatibility('incompatible', 'Ara geçme hedefi oluşmuyor',
                             'Limitler hem pozitif boşluk hem negatif sıkılık bölgesini kapsamıyor.')
    if low < 0 < high:
        return Compatibility('conditional', 'Montaj ölçüye bağlı; aynı montaj sonucu garanti değil',
                             'Bazı parçalar boşluklu, bazıları sıkı geçer. Her parçanın aynı şekilde takılması garanti değil.')
    if high <= 0 and low < 0:
        return Compatibility('conditional', 'Sıkılık veya sınırda temas; montaj değerlendirmesi gerekir',
                             'Mil delikten büyük veya sınırda eşit. Pres/ısıl yöntem, malzeme ve yüzey değerlendirilmelidir.')
    if low == 0:
        return Compatibility('boundary', 'Sınırda temas; hedefi seçerek kontrol edin',
                             'Boşluk sıfıra inebilir. Kayar/serbest montaj için yüzey ve şekil etkileri önemlidir.')
    return Compatibility('info', 'Tüm limitlerde boşluklu eşleşme',
                         'Hedefi seçerek kayar, ara veya sıkı geçmeye boyutsal uygunluğu kontrol edin.')


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
    if closest.shaft in ('e8', 'f7', 'g6') or (closest.hole in ('F8', 'G7') and closest.shaft == 'h6'):
        return 'Hareketli / yağlı çalışma adayı'
    return 'Boşluklu / kayar geçme adayı'
