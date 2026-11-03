"""Weight engine: cross-section × length × density, independent of the GUI.

Three methods, never mixed:
* Ölçülerden       – geometric area of the selected section type (modules.weight.sections);
* Katalog alanından – a cross-section area the user takes from a catalogue (cm²);
* Standart katalog – a verified EN profile (modules.weight.catalog). Its kg/m is the
  manufacturer value for steel (7850 kg/m³); another density uses area × ρ and says so.

All internal values are SI-consistent: mm and mm² for geometry, kg/m³ for density,
kg for mass. Nothing is rounded before display.
"""

from dataclasses import dataclass, field
import math
import re

from modules.weight import catalog, sections
from modules.weight.materials import (CUSTOM_DENSITY_RANGE, CUSTOM_MATERIAL, MATERIAL_ALIASES, MATERIAL_GROUPS,
                                      MATERIAL_NOTES, MATERIAL_SOURCES, MATERIALS)

UNITS = {'mm': 1, 'cm': 10, 'm': 1000}
MASS_UNITS = {'kg': 1.0, 'g': 1000.0, 't': .001}
METHODS = ('Ölçülerden', 'Katalog alanından')
STANDARD_METHOD = 'Standart katalog'
STEEL_BASIS = 7850.0

# Standard families: user-facing kind → catalogue family code.
STANDARD_KINDS = {'IPE': 'IPE', 'HEA': 'HEA', 'HEB': 'HEB', 'HEM': 'HEM', 'HP': 'HP', 'HD': 'HD',
                  'UPE': 'UPE', 'UPN (NPU)': 'UPN', 'Eşit kollu köşebent · EN 10056-1': 'L',
                  'Farklı kollu köşebent · EN 10056-1': 'LU'}
KINDS = (*sections.SECTION_TYPES, *STANDARD_KINDS)
CATEGORY_KINDS = {category: tuple(k for k, s in sections.SECTION_TYPES.items() if s.category == category)
                  for category in sections.CATEGORIES[:-1]}
CATEGORY_KINDS['Standart profil'] = tuple(STANDARD_KINDS)
# Earlier GOKWORKS kind names (saved settings, old calls) → current kinds.
KIND_ALIASES = {'Kutu profil': 'Dikdörtgen kutu profil', 'Köşebent': 'Farklı kollu köşebent',
                'Kare demir': 'Kare dolu çubuk', 'Silme lama': 'Lama / dikdörtgen çubuk',
                'Altıköşe': 'Altıköşe çubuk', 'UPN': 'UPN (NPU)', 'HE': 'I profil', 'HL': 'I profil',
                'IPN': 'I profil'}
BOX_CORNERS = sections.BOX_CORNERS

_FIELDS = sections.all_fields()
FIELDS = {kind: tuple(f.key for f in section.fields) for kind, section in sections.SECTION_TYPES.items()}
FIELD_LABELS = {key: item.label for key, item in _FIELDS.items()}
FIELD_LABELS.update({'b': 'Genişlik', 'h': 'Yükseklik', 't': 'Kalınlık', 'd': 'Çap', 'length': 'Boy / uzunluk'})
DEFAULT_DIMENSIONS = {key: item.default for key, item in _FIELDS.items()}
DEFAULT_DIMENSIONS['length'] = 1000
OPTIONAL_FIELDS = frozenset(key for key, item in _FIELDS.items() if item.optional)

SCOPE = ('Ağırlık = kesit alanı × boy × yoğunluk. Ölçülerden hesapta geometrik model kullanılır; '
         'kutu profilde EN 10219-2 hesap yarıçapları, köşebent/U/I profilde girilen kök yarıçapı '
         'hesaba katılır. Standart profillerde doğrulanmış üretici veri sayfasındaki kg/m (çelik, '
         '7850 kg/m³) esas alınır. Üretim toleransları, kaplama ve kesim firesi dahil değildir.')


def _number(value, label):
    """Parse a number; decimal comma or point. Ambiguous thousands groups are refused."""
    if isinstance(value, bool) or value is None:
        raise ValueError(f'{label} için geçerli bir sayı girin.')
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace(' ', '').replace(' ', '')
        if ',' in text and '.' in text:
            if text.rfind(',') > text.rfind('.') and re.fullmatch(r'[+-]?\d{1,3}(\.\d{3})+,\d+', text):
                text = text.replace('.', '').replace(',', '.')   # 1.234,5
            else:
                raise ValueError(f'{label}: “{value}” anlaşılamadı. Ondalık için yalnız virgül kullanın (ör. 1234,5).')
        elif ',' in text:
            text = text.replace(',', '.')
        elif re.fullmatch(r'[+-]?\d{1,3}(\.\d{3})+', text):
            raise ValueError(f'{label}: “{value}” belirsiz (bin mi, ondalık mı?). '
                             'Ondalık için virgül kullanın, binlik ayırıcı yazmayın.')
        try:
            number = float(text)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f'{label} için geçerli bir sayı girin.') from None
    if not math.isfinite(number):
        raise ValueError(f'{label} sonlu bir sayı olmalı.')
    return number


def parse_number(value, label='Değer'):
    return _number(value, label)


def _positive(value, label):
    number = _number(value, label)
    if number <= 0:
        raise ValueError(f'{label} sıfırdan büyük olmalı.')
    return number


def _non_negative(value, label):
    number = _number(value, label)
    if number < 0:
        raise ValueError(f'{label} negatif olamaz.')
    return number


def fmt(value, digits=3):
    """Display a number with a decimal comma and no unnecessary zeroes."""
    number = _number(value, 'Değer')
    if not isinstance(digits, int) or isinstance(digits, bool) or not 0 <= digits <= 12:
        raise ValueError('Ondalık basamak sayısı 0–12 arasında olmalı.')
    result = f'{number:.{digits}f}'
    if '.' in result:
        result = result.rstrip('0').rstrip('.')
    if result in ('-0', '0') and number != 0:
        return f'{number:.3g}'.replace('.', ',')
    return result.replace('.', ',')


def fmt_fixed(value, digits=3):
    """Fixed decimals with a decimal comma and thousands points (for reports)."""
    text = f'{float(value):,.{digits}f}'
    return text.replace(',', '\0').replace('.', ',').replace('\0', '.')


def mass_in(kg, unit):
    if unit not in MASS_UNITS:
        raise ValueError('Kütle birimi kg, g veya t olmalı.')
    return kg * MASS_UNITS[unit]


def normalise_kind(kind):
    return KIND_ALIASES.get(kind, kind)


def category_of(kind):
    kind = normalise_kind(kind)
    if kind in STANDARD_KINDS:
        return 'Standart profil'
    return sections.SECTION_TYPES[kind].category


def profiles_for(kind):
    return catalog.profiles(STANDARD_KINDS[normalise_kind(kind)])


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
    corner_radii: tuple = ()           # box: (outer, inner); angle: (root, toe) in mm
    category: str = ''
    profile: str = ''
    source: str = ''
    standard: str = ''
    catalog_kg_m: float | None = None  # manufacturer kg/m (steel) for standard profiles
    geometric_area_mm2: float | None = None
    notes: tuple = field(default_factory=tuple)
    drawing: str = ''
    material_label: str = ''

    @property
    def piece_text(self):
        return f'{fmt(self.mass_kg)} kg'

    @property
    def total_text(self):
        return f'{fmt(self.total_mass_kg)} kg'

    @property
    def section_text(self):
        """Short description for lists and reports, e.g. 'Boru Ø60 × 3'."""
        if self.profile:
            return self.profile
        d = self.dimensions_mm
        if self.method == 'Katalog alanından':
            return f'{self.kind} · A = {fmt(self.area_mm2 / 100)} cm²'
        if self.kind == 'Mil':
            return f'Mil Ø{fmt(d["d"])}'
        if self.kind == 'Boru':
            return f'Boru Ø{fmt(d["d"])} × {fmt(d["t"])}'
        if self.kind == 'Altıköşe çubuk':
            return f'Altıköşe SW{fmt(d["s"])}'
        order = ('b', 'h', 't') if 'kutu' in self.kind or 'köşebent' in self.kind else ('h', 'b', 't', 'tw', 'tf')
        keys = [k for k in order if k in d]
        if self.kind == 'Kare kutu profil' or self.kind == 'Kare dolu çubuk' or self.kind == 'Eşit kollu köşebent':
            keys = [k for k in ('b', 't') if k in d]
        return f'{self.kind} ' + ' × '.join(fmt(d[k]) for k in keys)

    def dimension_text(self):
        labels = sections.SECTION_TYPES[self.kind].fields if self.kind in sections.SECTION_TYPES else ()
        names = {f.key: f.label for f in labels}
        names.update({'h': 'h', 'b': 'b', 'tw': 'tw', 'tf': 'tf', 'r': 'r'} if self.profile else {})
        return ', '.join(f'{names.get(k, k)} {fmt(v)}' for k, v in self.dimensions_mm.items())


def _density(material, density):
    material = MATERIAL_ALIASES.get(material, material)
    if material == CUSTOM_MATERIAL:
        value = _positive(density, 'Yoğunluk (kg/m³)')
        low, high = CUSTOM_DENSITY_RANGE
        if not low <= value <= high:
            raise ValueError(f'Yoğunluk {fmt(low, 0)}–{fmt(high, 0)} kg/m³ aralığında olmalı.')
        return material, value
    if material not in MATERIALS:
        raise ValueError('Geçerli bir malzeme seçin.')
    preset = float(MATERIALS[material])
    if density not in (None, '') and _number(density, 'Yoğunluk') != preset:
        raise ValueError('Yoğunluk seçilen malzemeye göre sabittir; farklı bir değer için “Özel malzeme” seçin.')
    return material, preset


def calculate(*, kind='Sac levha', material='Demir / Çelik', density=None, unit='mm', length='1000',
              count='1', method='Ölçülerden', area_cm2=None, profile=None, corner=None, box_corner=None,
              material_name='', **dimensions):
    """Compute one-piece and total weight; parse only the selected method's fields."""
    kind = normalise_kind(kind)
    if kind not in KINDS:
        raise ValueError('Geçerli bir kesit türü seçin.')
    material, density = _density(material, density)
    if unit not in UNITS:
        raise ValueError('Ölçü birimi mm, cm veya m olmalı.')
    standard = kind in STANDARD_KINDS
    if not standard and method not in METHODS:
        raise ValueError('Geçerli bir hesaplama yöntemi seçin.')
    number_of_pieces = _positive(count, 'Adet')
    if not number_of_pieces.is_integer() or number_of_pieces > 1000000:
        raise ValueError('Adet 1–1.000.000 arasında bir tam sayı olmalı.')
    number_of_pieces = int(number_of_pieces)
    length_mm = _positive(length, 'Boy / uzunluk') * UNITS[unit]
    dimensions_mm, notes, corner_radii = {}, [], ()
    approximate, catalog_kg_m, geometric, source, standard_text, profile_name = False, None, None, '', '', ''
    drawing = ''
    try:
        if standard:
            family = STANDARD_KINDS[kind]
            items = catalog.profiles(family)
            item = items[0] if profile in (None, '') else catalog.profile(family, profile)
            profile_name, method = item.title, STANDARD_METHOD
            info = catalog.family_info(family)
            drawing = {'I': 'i', 'U': 'channel', 'U_tapered': 'channel', 'L': 'angle'}[info['shape']]
            area_mm2 = item.area_cm2 * 100
            dimensions_mm = {k: v for k, v in (('h', item.h), ('b', item.b), ('tw', item.tw), ('tf', item.tf),
                                                ('r', item.r)) if v}
            if info['shape'] == 'L':
                dimensions_mm = {'h': item.h, 'b': item.b, 't': item.tf, 'r1': item.r}
                corner_radii = (item.r, item.r2)
            catalog_kg_m = item.mass_kg_m
            geometric = item.geometric_area_mm2()
            source, standard_text = catalog.source_text(item), info['standard']
            if info['shape'] == 'U_tapered':
                notes.append('Eğimli başlık: geometrik alan paralel başlık varsayımıyla yaklaşıktır; katalog alanı esastır.')
            notes.extend(f'Diğer üretici değeri — {text}' for text in item.differences)
            kg_per_m = catalog_kg_m if density == STEEL_BASIS else area_mm2 * 1e-6 * density
            if density != STEEL_BASIS:
                notes.append(f'Katalog {fmt(catalog_kg_m)} kg/m çelik (7850 kg/m³) içindir; seçili yoğunlukla '
                             f'A × ρ = {fmt(kg_per_m)} kg/m hesaplandı.')
        elif method == 'Katalog alanından':
            area_mm2 = _positive(area_cm2, 'Katalog kesit alanı (cm²)') * 100
            kg_per_m = area_mm2 * 1e-6 * density
            drawing = sections.SECTION_TYPES[kind].drawing
        else:
            section = sections.SECTION_TYPES[kind]
            chosen = None
            if section.options:
                chosen = corner or box_corner or section.options[0]
                if chosen not in section.options:
                    raise ValueError('Geçerli bir köşe biçimi seçin.')
            for item in section.fields:
                if item.key in ('ro', 'ri') and chosen != sections.BOX_CORNERS[1]:
                    continue
                reader = _non_negative if item.optional else _positive
                raw = dimensions.get(item.key, item.default)
                dimensions_mm[item.key] = reader(raw, item.label) * UNITS[unit]
            area_mm2, extra = sections.area(kind, dimensions_mm, chosen)
            notes.extend(extra)
            kg_per_m = area_mm2 * 1e-6 * density
            drawing = section.drawing
            if section.options:
                corner_radii = sections.box_radii(dimensions_mm['t'], chosen, dimensions_mm.get('ro', 0),
                                                  dimensions_mm.get('ri', 0))
                approximate = chosen == sections.BOX_CORNERS[2]
                if approximate:
                    notes.append('Keskin köşeli yaklaşık model; standart kutu profiller köşe yarıçaplıdır.')
            elif kind in ('Eşit kollu köşebent', 'Farklı kollu köşebent'):
                root = dimensions_mm.get('r1', 0)
                corner_radii = (root, root / 2)
                approximate = root == 0
            elif section.approximate_note:
                approximate = kind in ('T profil',) or not dimensions_mm.get('r')
            if approximate and section.approximate_note:
                notes.append(section.approximate_note)
        volume_m3 = (area_mm2 / 1e6) * (length_mm / 1000)
        mass_kg = kg_per_m * (length_mm / 1000)
        total_volume_m3 = volume_m3 * number_of_pieces
        total_mass_kg = mass_kg * number_of_pieces
    except OverflowError:
        raise ValueError('Ölçüler hesaplama sınırını aşıyor; daha küçük değerler girin.') from None
    values = (length_mm, area_mm2, volume_m3, mass_kg, total_volume_m3, total_mass_kg, kg_per_m)
    if any(not math.isfinite(value) or value <= 0 for value in values) or \
            any(not math.isfinite(v) for v in dimensions_mm.values()):
        raise ValueError('Ölçüler hesaplama sınırını aşıyor; değerleri kontrol edin.')
    label = (material_name or '').strip() if material == CUSTOM_MATERIAL else ''
    return Result(kind=kind, material=material, density=density, unit=unit, count=number_of_pieces,
                  length_mm=length_mm, area_mm2=area_mm2, volume_m3=volume_m3, mass_kg=mass_kg,
                  total_volume_m3=total_volume_m3, total_mass_kg=total_mass_kg, kg_per_m=kg_per_m,
                  dimensions_mm=dimensions_mm, method=method, approximate=approximate,
                  corner_radii=tuple(corner_radii), category=category_of(kind), profile=profile_name,
                  source=source, standard=standard_text, catalog_kg_m=catalog_kg_m,
                  geometric_area_mm2=geometric, notes=tuple(notes), drawing=drawing,
                  material_label=label or material)


__all__ = ['calculate', 'Result', 'KINDS', 'CATEGORY_KINDS', 'STANDARD_KINDS', 'KIND_ALIASES', 'UNITS',
           'MASS_UNITS', 'METHODS', 'STANDARD_METHOD', 'MATERIALS', 'MATERIAL_GROUPS', 'MATERIAL_NOTES',
           'MATERIAL_SOURCES', 'MATERIAL_ALIASES', 'CUSTOM_MATERIAL', 'FIELDS', 'FIELD_LABELS',
           'DEFAULT_DIMENSIONS', 'SCOPE', 'fmt', 'fmt_fixed', 'mass_in', 'parse_number', 'profiles_for',
           'category_of', 'normalise_kind', 'BOX_CORNERS']
