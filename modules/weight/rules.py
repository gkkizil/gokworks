"""Weight from cross-sectional geometry or a user-provided catalogue area."""

from dataclasses import dataclass
import math

from modules.weight.materials import MATERIALS, MATERIAL_ALIASES, MATERIAL_GROUPS, MATERIAL_NOTES, MATERIAL_SOURCES

KINDS = ('Kutu profil', 'Sac levha', 'Boru', 'Köşebent', 'Kare demir',
         'T profil', 'U profil', 'HEA', 'HP', 'HD', 'HL', 'IPN', 'UPE',
         'Altıköşe', 'HE', 'IPE', 'UPN', 'Mil', 'Silme lama')
UNITS = {'mm': 1, 'cm': 10, 'm': 1000}
METHODS = ('Ölçülerden', 'Katalog alanından')
_BEAM_KINDS = ('U profil', 'HEA', 'HP', 'HD', 'HL', 'IPN', 'UPE', 'HE', 'IPE', 'UPN')
FIELDS = {
    'Kutu profil': ('b', 'h', 't'),
    'Sac levha': ('b', 't'),
    'Boru': ('d', 't'),
    'Köşebent': ('b', 'h', 't'),
    'Kare demir': ('b',),
    'T profil': ('b', 'h', 'tw', 'tf'),
    **{kind: ('b', 'h', 'tw', 'tf') for kind in _BEAM_KINDS},
    'Altıköşe': ('s',),
    'Mil': ('d',),
    'Silme lama': ('b', 't'),
}
FIELD_LABELS = {
    'b': 'Genişlik',
    'h': 'Yükseklik',
    't': 'Kalınlık',
    'tw': 'Gövde kalınlığı',
    'tf': 'Başlık kalınlığı',
    'd': 'Dış çap',
    's': 'Anahtar ağzı',
    'length': 'Boy / uzunluk',
}
DEFAULT_DIMENSIONS = {'b': 100, 'h': 100, 't': 5, 'tw': 5,
                      'tf': 8, 'd': 50, 's': 30, 'length': 1000}
SCOPE = ('Ağırlık, kesit alanı × boy × yoğunluk ile hesaplanır. Kutu profilde köşe '
         'yarıçapları EN 10219-2 (soğuk) / EN 10210-2 (sıcak) hesap değerleriyle, köşebentte '
         'kök ve uç yarıçapları EN 10056-1 değerleriyle kesitten düşülür. Diğer profillerde '
         'kök radyüsleri ve başlık eğimleri yoktur; standart profil için katalog kesit alanını '
         'kullanabilirsiniz. Üretim toleransları dahil değildir. Yoğunluk seçilen malzemeye '
         'göre sabittir ve değiştirilemez.')

# Corner geometry. Box sections: A = 2t(b+h-2t) - (4-pi)(ro^2 - ri^2) with the
# radii EN 10219-2 / EN 10210-2 specify for calculating section properties.
BOX_CORNERS = ('Soğuk şekillendirilmiş · EN 10219', 'Sıcak bitirilmiş · EN 10210', 'Keskin köşe')
# Angles (EN 10056-1): A = t(b+h-t) + (4-pi)/4 · (r1^2 - 2·r2^2), r2 = r1/2.
ANGLE_CORNERS = ('Sıcak haddelenmiş · EN 10056-1', 'Keskin köşe')
# Root radius r1 of equal-leg angles by leg length (EN 10056-1).
ANGLE_ROOT_RADIUS = {20: 3.5, 25: 3.5, 30: 5, 35: 5, 40: 6, 45: 7, 50: 7, 60: 8, 65: 9, 70: 9,
                     75: 10, 80: 10, 90: 11, 100: 12, 120: 13, 130: 14, 150: 16, 160: 17,
                     180: 18, 200: 18, 250: 18}


def box_radii(t, corner):
    """(outer, inner) corner radius in mm for the section-property calculation."""
    if corner == BOX_CORNERS[0]:
        factor = (2.0, 1.0) if t <= 6 else (2.5, 1.5) if t <= 10 else (3.0, 2.0)
    elif corner == BOX_CORNERS[1]:
        factor = (1.5, 1.0)
    else:
        return 0.0, 0.0
    return factor[0] * t, factor[1] * t


def angle_root_radius(b, h, corner):
    """(r1, exact) — EN 10056-1 root radius for the longer leg; exact if it is a table size."""
    if corner != ANGLE_CORNERS[0]:
        return 0.0, True
    leg = max(b, h)
    sizes = [size for size in ANGLE_ROOT_RADIUS if size <= leg] or [min(ANGLE_ROOT_RADIUS)]
    nearest = max(sizes)
    return float(ANGLE_ROOT_RADIUS[nearest]), (b == h and leg == nearest)


def _number(value, label):
    try:
        if isinstance(value, bool):
            raise ValueError()
        number = float(str(value).strip().replace(',', '.'))
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f'{label} için geçerli bir sayı girin.') from None
    if not math.isfinite(number):
        raise ValueError(f'{label} sonlu bir sayı olmalı.')
    return number


def _positive(value, label):
    number = _number(value, label)
    if number <= 0:
        raise ValueError(f'{label} sıfırdan büyük olmalı.')
    return number


def fmt(value, digits=3):
    """Display a number with a decimal comma and no unnecessary zeroes."""
    number = _number(value, 'Değer')
    if not isinstance(digits, int) or isinstance(digits, bool) or not 0 <= digits <= 12:
        raise ValueError('Ondalık basamak sayısı 0–12 arasında olmalı.')
    result = f'{number:.{digits}f}'
    if '.' in result:
        result = result.rstrip('0').rstrip('.')
    if number != 0 and float(result) == 0:
        result = f'{number:.3g}'
    return ('0' if result == '-0' else result).replace('.', ',')


@dataclass(frozen=True)
class Result:
    kind: str
    material: str
    density: float
    unit: str
    count: int
    length_mm: float
    area_mm2: float
    volume_m3: float
    mass_kg: float
    total_volume_m3: float
    total_mass_kg: float
    kg_per_m: float
    dimensions_mm: dict
    method: str
    approximate: bool
    corner_radii: tuple = ()   # box: (outer, inner); angle: (root, toe) in mm

    @property
    def piece_text(self):
        return f'{fmt(self.mass_kg)} kg'

    @property
    def total_text(self):
        return f'{fmt(self.total_mass_kg)} kg'


def _area(kind, dimensions, corner=None):
    if kind in ('Sac levha', 'Silme lama'):
        return dimensions['b'] * dimensions['t']
    if kind == 'Kare demir':
        return dimensions['b'] ** 2
    if kind == 'Mil':
        return math.pi / 4 * dimensions['d'] ** 2
    if kind == 'Altıköşe':
        return math.sqrt(3) / 2 * dimensions['s'] ** 2
    if kind == 'Boru':
        d, t = dimensions['d'], dimensions['t']
        if 2 * t >= d:
            raise ValueError('Boru et kalınlığının iki katı dış çaptan küçük olmalı.')
        return math.pi * t * (d - t)
    if kind in ('Kutu profil', 'Köşebent'):
        b, h, t = (dimensions[field] for field in ('b', 'h', 't'))
        if kind == 'Kutu profil':
            if 2 * t >= min(b, h):
                raise ValueError('Kutu profil et kalınlığının iki katı genişlik ve yükseklikten küçük olmalı.')
            # Equivalent to b*h-(b-2*t)*(h-2*t), with less cancellation for thin walls.
            outer, inner = box_radii(t, corner or BOX_CORNERS[0])
            if 2 * outer > min(b, h):
                raise ValueError('Köşe yarıçapı bu kesit için çok büyük; Keskin köşe seçin veya ölçüleri kontrol edin.')
            return 2 * t * (b + h - 2 * t) - (4 - math.pi) * (outer ** 2 - inner ** 2)
        if t >= min(b, h):
            raise ValueError('Köşebent kalınlığı iki kol ölçüsünden de küçük olmalı.')
        root, _ = angle_root_radius(b, h, corner or ANGLE_CORNERS[0])
        return t * (b + h - t) + (4 - math.pi) / 4 * (root ** 2 - 2 * (root / 2) ** 2)
    b, h, tw, tf = (dimensions[field] for field in ('b', 'h', 'tw', 'tf'))
    if tw >= b:
        raise ValueError('Gövde kalınlığı başlık genişliğinden küçük olmalı.')
    flange_count = 1 if kind == 'T profil' else 2
    if flange_count * tf >= h:
        raise ValueError('Başlık kalınlıkları toplamı profil yüksekliğinden küçük olmalı.')
    return flange_count * b * tf + (h - flange_count * tf) * tw


def calculate(*, kind='Sac levha', material='Demir / Çelik', density=None,
              unit='mm', length='1000', count='1', method='Ölçülerden',
              area_cm2=None, box_corner=None, angle_corner=None, **dimensions):
    """Compute one-piece and total weight; parse only the selected method's fields."""
    material = MATERIAL_ALIASES.get(material, material)
    if kind not in KINDS:
        raise ValueError('Geçerli bir ürün türü seçin.')
    if material not in MATERIALS:
        raise ValueError('Geçerli bir malzeme seçin.')
    if unit not in UNITS:
        raise ValueError('Ölçü birimi mm, cm veya m olmalı.')
    if method not in METHODS:
        raise ValueError('Geçerli bir hesaplama yöntemi seçin.')
    preset_density = MATERIALS[material]
    if density is not None and _number(density, 'Yoğunluk') != preset_density:
        raise ValueError('Yoğunluk seçilen malzemeye göre sabittir ve değiştirilemez.')
    density = float(preset_density)
    number_of_pieces = _positive(count, 'Adet')
    if not number_of_pieces.is_integer() or number_of_pieces > 1000000:
        raise ValueError('Adet 1–1.000.000 arasında bir tam sayı olmalı.')
    number_of_pieces = int(number_of_pieces)
    length_mm = _positive(length, 'Boy / uzunluk') * UNITS[unit]
    dimensions_mm = {}
    approximate = False
    corner_radii = ()
    try:
        if method == 'Katalog alanından':
            area_mm2 = _positive(area_cm2, 'Katalog kesit alanı (cm²)') * 100
        else:
            dimensions_mm = {
                field: _positive(dimensions.get(field, DEFAULT_DIMENSIONS[field]), FIELD_LABELS[field]) * UNITS[unit]
                for field in FIELDS[kind]
            }
            corner = box_corner if kind == 'Kutu profil' else angle_corner if kind == 'Köşebent' else None
            if corner is not None and corner not in (BOX_CORNERS if kind == 'Kutu profil' else ANGLE_CORNERS):
                raise ValueError('Geçerli bir köşe biçimi seçin.')
            area_mm2 = _area(kind, dimensions_mm, corner)
            if kind == 'Kutu profil':
                corner_radii = box_radii(dimensions_mm['t'], corner or BOX_CORNERS[0])
            elif kind == 'Köşebent':
                root, _ = angle_root_radius(dimensions_mm['b'], dimensions_mm['h'], corner or ANGLE_CORNERS[0])
                corner_radii = (root, root / 2)
            if kind == 'Kutu profil':
                approximate = (corner or BOX_CORNERS[0]) == 'Keskin köşe'
            elif kind == 'Köşebent':
                chosen = corner or ANGLE_CORNERS[0]
                approximate = chosen == 'Keskin köşe' or not angle_root_radius(
                    dimensions_mm['b'], dimensions_mm['h'], chosen)[1]
            else:
                approximate = kind in ('T profil', *_BEAM_KINDS)
        volume_m3 = (area_mm2 / 1000000) * (length_mm / 1000)
        mass_kg = volume_m3 * density
        total_volume_m3 = volume_m3 * number_of_pieces
        total_mass_kg = mass_kg * number_of_pieces
        kg_per_m = (area_mm2 / 1000000) * density
    except OverflowError:
        raise ValueError('Ölçüler hesaplama sınırını aşıyor; daha küçük değerler girin.') from None
    values = (length_mm, area_mm2, volume_m3, mass_kg, total_volume_m3, total_mass_kg, kg_per_m,
              *dimensions_mm.values())
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError('Ölçüler hesaplama sınırını aşıyor; değerleri kontrol edin.')
    return Result(kind=kind, material=material, density=density, unit=unit,
                  count=number_of_pieces, length_mm=length_mm, area_mm2=area_mm2,
                  volume_m3=volume_m3, mass_kg=mass_kg, total_volume_m3=total_volume_m3,
                  total_mass_kg=total_mass_kg, kg_per_m=kg_per_m,
                  dimensions_mm=dimensions_mm, method=method, approximate=approximate,
                  corner_radii=corner_radii)
