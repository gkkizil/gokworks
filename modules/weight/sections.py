"""Cross-section types for the weight calculator: fields, validation and area (mm²).

GUI-independent. Each section type is one registry entry, so a new family is added
by writing its area function and listing its fields. Dimensions are in millimetres.
"""

from dataclasses import dataclass, field
import math

CATEGORIES = ('Dolu malzeme', 'İçi boş kesit', 'Açık profil', 'Standart profil')

# Box-section corners (EN 10219-2, cold formed). The calculation radii are the middle
# of the external-corner tolerance bands 1.6T–2.4T, 2.0T–3.0T, 2.4T–3.6T, with
# ri = ro − T; section area A = 2T(B+H−2T) − (4−π)(ro² − ri²).
BOX_CORNERS = ('Soğuk şekillendirilmiş · EN 10219-2', 'Elle yarıçap', 'Keskin köşe')


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    default: float
    optional: bool = False  # zero allowed (radii)


@dataclass(frozen=True)
class SectionType:
    key: str
    category: str
    fields: tuple
    area: object                   # callable(dims) -> (area_mm², notes)
    drawing: str
    approximate_note: str = ''     # shown when the geometric model omits real features
    options: tuple = field(default_factory=tuple)

    def defaults(self):
        return {f.key: f.default for f in self.fields}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


# ---- area functions ---------------------------------------------------------------
def round_bar(d):
    return math.pi / 4 * d['d'] ** 2, []


def square_bar(d):
    return d['b'] ** 2, []


def flat_bar(d):
    return d['b'] * d['t'], []


def hexagon(d):
    return math.sqrt(3) / 2 * d['s'] ** 2, []


def tube(d):
    outer, t = d['d'], d['t']
    _require(2 * t < outer, 'Boru et kalınlığının iki katı dış çaptan küçük olmalı.')
    inner = outer - 2 * t
    # π(D² − d²)/4 written as πt(D − t): no cancellation for thin walls.
    return math.pi * t * (outer - t), [f'İç çap d = D − 2t = {inner:g} mm']


def box_radii(t, corner, ro=0.0, ri=0.0):
    """(outer, inner) corner radius in mm used for the area."""
    if corner == BOX_CORNERS[0]:
        outer = 2.0 * t if t <= 6 else 2.5 * t if t <= 10 else 3.0 * t
        return outer, outer - t
    if corner == BOX_CORNERS[1]:
        return float(ro), float(ri)
    return 0.0, 0.0


def box(d, corner=BOX_CORNERS[0]):
    b, h, t = d['b'], d['h'], d['t']
    _require(2 * t < min(b, h), 'Kutu profil et kalınlığının iki katı genişlik ve yükseklikten küçük olmalı.')
    outer, inner = box_radii(t, corner, d.get('ro', 0), d.get('ri', 0))
    _require(outer <= min(b, h) / 2, 'Dış köşe yarıçapı kenarın yarısından büyük olamaz.')
    _require(inner <= outer, 'İç köşe yarıçapı dış köşe yarıçapından büyük olamaz.')
    _require(inner <= min(b, h) / 2 - t, 'İç köşe yarıçapı iç boşluğa sığmıyor.')
    notes = []
    if outer:
        notes.append(f'Köşe yarıçapı rₒ = {outer:g} mm, rᵢ = {inner:g} mm')
    # b·h − (b−2t)(h−2t) without cancellation, minus the rounded-corner areas.
    return 2 * t * (b + h - 2 * t) - (4 - math.pi) * (outer ** 2 - inner ** 2), notes


def square_box(d, corner=BOX_CORNERS[0]):
    return box(dict(d, h=d['b']), corner)


def angle(d):
    """EN 10056-1 geometry; r1 = 0 gives the sharp-corner approximation."""
    b, h, t, r1 = d['b'], d.get('h', d['b']), d['t'], d.get('r1', 0.0)
    _require(t < min(b, h), 'Köşebent kalınlığı iki kol ölçüsünden de küçük olmalı.')
    r2 = r1 / 2
    _require(r1 <= min(b, h) - t, 'Kök yarıçapı kol iç uzunluğundan büyük olamaz.')
    notes = [f'Kök yarıçapı r₁ = {r1:g} mm, uç yarıçapı r₂ = r₁/2 = {r2:g} mm'] if r1 else []
    return t * (b + h - t) + (1 - math.pi / 4) * (r1 ** 2 - 2 * r2 ** 2), notes


def tee(d):
    b, h, tw, tf = d['b'], d['h'], d['tw'], d['tf']
    _require(tw < b, 'Gövde kalınlığı başlık genişliğinden küçük olmalı.')
    _require(tf < h, 'Başlık kalınlığı profil yüksekliğinden küçük olmalı.')
    return b * tf + (h - tf) * tw, []


def i_section(d):
    """EN 10365 parallel-flange I/H: A = 2b·tf + (h − 2tf)·tw + (4 − π)·r²."""
    h, b, tw, tf, r = d['h'], d['b'], d['tw'], d['tf'], d.get('r', 0.0)
    _require(tw < b, 'Gövde kalınlığı başlık genişliğinden küçük olmalı.')
    _require(2 * tf < h, 'Başlık kalınlıkları toplamı profil yüksekliğinden küçük olmalı.')
    _require(r <= (b - tw) / 2 and r <= h / 2 - tf, 'Kök yarıçapı başlık ile gövde arasına sığmıyor.')
    return 2 * b * tf + (h - 2 * tf) * tw + (4 - math.pi) * r ** 2, []


def channel(d):
    """Parallel-flange U (UPE type): A = 2b·tf + (h − 2tf)·tw + (4 − π)/2·r²."""
    h, b, tw, tf, r = d['h'], d['b'], d['tw'], d['tf'], d.get('r', 0.0)
    _require(tw < b, 'Gövde kalınlığı başlık genişliğinden küçük olmalı.')
    _require(2 * tf < h, 'Başlık kalınlıkları toplamı profil yüksekliğinden küçük olmalı.')
    _require(r <= b - tw and r <= h / 2 - tf, 'Kök yarıçapı başlık ile gövde arasına sığmıyor.')
    return 2 * b * tf + (h - 2 * tf) * tw + (4 - math.pi) / 2 * r ** 2, []


def bent_channel(d):
    """Press-brake U from sheet: straight legs plus two quarter rings (inner radius r)."""
    h, b, t, r = d['h'], d['b'], d['t'], d.get('r', 0.0)
    outer = r + t
    _require(b > outer, 'Başlık genişliği büküm yarıçapı + kalınlıktan büyük olmalı.')
    _require(h > 2 * outer, 'Yükseklik iki büküm (r + t) toplamından büyük olmalı.')
    straight = (h - 2 * outer) + 2 * (b - outer)
    return t * straight + 2 * (math.pi / 4) * (outer ** 2 - r ** 2), [f'İç büküm yarıçapı r = {r:g} mm, dış = {outer:g} mm']


# ---- registry ---------------------------------------------------------------------
F = Field
_ROOT = 'r1'
SECTION_TYPES = {}


def _add(section):
    SECTION_TYPES[section.key] = section


_add(SectionType('Mil', 'Dolu malzeme', (F('d', 'Çap', 50),), round_bar, 'round'))
_add(SectionType('Kare dolu çubuk', 'Dolu malzeme', (F('b', 'Kenar', 40),), square_bar, 'square'))
_add(SectionType('Lama / dikdörtgen çubuk', 'Dolu malzeme', (F('b', 'Genişlik', 60), F('t', 'Kalınlık', 10)),
                 flat_bar, 'flat'))
_add(SectionType('Altıköşe çubuk', 'Dolu malzeme', (F('s', 'Anahtar ağzı', 30),), hexagon, 'hexagon'))
_add(SectionType('Sac levha', 'Dolu malzeme', (F('b', 'En', 1000), F('t', 'Kalınlık', 5)), flat_bar, 'plate'))
_add(SectionType('Boru', 'İçi boş kesit', (F('d', 'Dış çap', 60), F('t', 'Et kalınlığı', 3)), tube, 'tube'))
_add(SectionType('Kare kutu profil', 'İçi boş kesit',
                 (F('b', 'Kenar', 100), F('t', 'Et kalınlığı', 5), F('ro', 'Dış köşe yarıçapı', 10, True),
                  F('ri', 'İç köşe yarıçapı', 5, True)), square_box, 'box', options=BOX_CORNERS))
_add(SectionType('Dikdörtgen kutu profil', 'İçi boş kesit',
                 (F('b', 'Genişlik', 100), F('h', 'Yükseklik', 60), F('t', 'Et kalınlığı', 4),
                  F('ro', 'Dış köşe yarıçapı', 8, True), F('ri', 'İç köşe yarıçapı', 4, True)),
                 box, 'box', options=BOX_CORNERS))
_add(SectionType('Eşit kollu köşebent', 'Açık profil',
                 (F('b', 'Kol', 50), F('t', 'Kalınlık', 5), F('r1', 'Kök yarıçapı r₁', 0, True)), angle, 'angle',
                 'r₁ = 0 ise keskin köşeli yaklaşık model; hadde köşebentlerinde r₁ girin veya Standart profilden seçin.'))
_add(SectionType('Farklı kollu köşebent', 'Açık profil',
                 (F('b', 'Kısa kol', 50), F('h', 'Uzun kol', 80), F('t', 'Kalınlık', 6), F('r1', 'Kök yarıçapı r₁', 0, True)),
                 angle, 'angle',
                 'r₁ = 0 ise keskin köşeli yaklaşık model; hadde köşebentlerinde r₁ girin veya Standart profilden seçin.'))
_add(SectionType('U profil', 'Açık profil',
                 (F('h', 'Yükseklik', 100), F('b', 'Başlık genişliği', 50), F('tw', 'Gövde kalınlığı', 6),
                  F('tf', 'Başlık kalınlığı', 8), F('r', 'Kök yarıçapı', 0, True)), channel, 'channel',
                 'Paralel başlıklı geometrik model; UPN gibi eğimli başlıklı profillerde Standart profilden seçin.'))
_add(SectionType('Bükme U profil (sac)', 'Açık profil',
                 (F('h', 'Yükseklik (A)', 100), F('b', 'Başlık genişliği (B)', 50), F('t', 'Sac kalınlığı', 3),
                  F('r', 'İç büküm yarıçapı', 3, True)), bent_channel, 'bent_channel'))
_add(SectionType('T profil', 'Açık profil',
                 (F('b', 'Başlık genişliği', 60), F('h', 'Yükseklik', 60), F('tw', 'Gövde kalınlığı', 7),
                  F('tf', 'Başlık kalınlığı', 7)), tee, 'tee',
                 'Kök ve uç yarıçapları olmayan geometrik model.'))
_add(SectionType('I profil', 'Açık profil',
                 (F('h', 'Yükseklik', 200), F('b', 'Başlık genişliği', 100), F('tw', 'Gövde kalınlığı', 5.6),
                  F('tf', 'Başlık kalınlığı', 8.5), F('r', 'Kök yarıçapı', 0, True)), i_section, 'i',
                 'Paralel başlıklı geometrik model; IPN gibi eğimli başlıklı profillerde sonuç yaklaşıktır.'))


def all_fields():
    """Every dimension key with its first label and default (for building forms)."""
    fields = {}
    for section in SECTION_TYPES.values():
        for item in section.fields:
            fields.setdefault(item.key, item)
    return fields


def area(kind, dimensions, corner=None):
    section = SECTION_TYPES[kind]
    if section.options:
        return section.area(dimensions, corner or section.options[0])
    return section.area(dimensions)


__all__ = ['CATEGORIES', 'BOX_CORNERS', 'Field', 'SectionType', 'SECTION_TYPES', 'all_fields', 'area',
           'box_radii', 'i_section', 'channel', 'angle', 'tube', 'box']
