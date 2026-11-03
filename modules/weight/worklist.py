"""Calculation list (several parts, materials and sections) and material cost.

GUI-independent. Mass scales linearly with length, so a row keeps its kg/m and can be
edited (length, count, price) without re-running the section geometry.
Cost covers material only: labour, cutting and other production costs are excluded.
"""

from dataclasses import asdict, dataclass, replace
import math

from modules.weight.rules import parse_number

COST_NOTE = ('Tutar yalnız malzeme bedelidir; işçilik, kesim, nakliye ve diğer üretim giderleri dahil değildir.')


@dataclass(frozen=True)
class Item:
    name: str
    material: str
    density: float
    section: str
    dimensions: str
    length_mm: float
    count: int
    kg_per_m: float
    area_mm2: float
    method: str
    source: str = ''
    price_per_kg: float | None = None

    @property
    def unit_mass_kg(self):
        return self.kg_per_m * self.length_mm / 1000

    @property
    def total_mass_kg(self):
        return self.unit_mass_kg * self.count

    @property
    def total_price(self):
        return None if self.price_per_kg is None else self.total_mass_kg * self.price_per_kg

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        names = {f for f in cls.__dataclass_fields__}
        if not isinstance(data, dict) or not {'name', 'kg_per_m', 'length_mm', 'count'} <= set(data):
            raise ValueError('Liste satırı okunamadı.')
        item = cls(**{k: v for k, v in data.items() if k in names})
        return validated(item)


def validated(item):
    if not isinstance(item.count, int) or isinstance(item.count, bool) or not 1 <= item.count <= 1000000:
        raise ValueError('Adet 1–1.000.000 arasında bir tam sayı olmalı.')
    for value, label in ((item.length_mm, 'Boy'), (item.kg_per_m, 'kg/m')):
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{label} sıfırdan büyük olmalı.')
    if item.price_per_kg is not None and (not math.isfinite(item.price_per_kg) or item.price_per_kg < 0):
        raise ValueError('Birim fiyat negatif olamaz.')
    return item


def from_result(result, name='', price_per_kg=None):
    """A list row from a rules.Result (one calculation)."""
    title = name.strip() or result.section_text
    return validated(Item(title, result.material_label or result.material, result.density, result.section_text,
                          result.dimension_text(), result.length_mm, result.count, result.kg_per_m, result.area_mm2,
                          result.method, result.source, price_per_kg))


def edit(item, field, text):
    """Return a copy with one user-edited cell; raises ValueError with a Turkish message."""
    if field == 'name':
        value = str(text).strip()
        if not value:
            raise ValueError('Parça adı boş olamaz.')
        return replace(item, name=value)
    if field == 'count':
        number = parse_number(text, 'Adet')
        if not number.is_integer():
            raise ValueError('Adet tam sayı olmalı.')
        return validated(replace(item, count=int(number)))
    if field == 'length_mm':
        return validated(replace(item, length_mm=parse_number(text, 'Boy')))
    if field == 'price_per_kg':
        if str(text).strip() == '':
            return replace(item, price_per_kg=None)
        return validated(replace(item, price_per_kg=parse_number(text, 'Birim fiyat')))
    raise ValueError('Bu sütun düzenlenemez.')


@dataclass(frozen=True)
class Totals:
    count: int
    mass_kg: float
    scrap_percent: float
    mass_with_scrap_kg: float
    priced_mass_kg: float
    net: float
    vat_percent: float
    vat: float
    gross: float
    unpriced_rows: int


def totals(items, scrap_percent=0.0, vat_percent=0.0):
    """Sum mass and material cost. Scrap adds material (mass and cost); VAT applies to cost."""
    scrap = parse_number(scrap_percent, 'Fire oranı')
    vat = parse_number(vat_percent, 'KDV oranı')
    if not 0 <= scrap <= 100:
        raise ValueError('Fire oranı %0–100 aralığında olmalı.')
    if not 0 <= vat <= 100:
        raise ValueError('KDV oranı %0–100 aralığında olmalı.')
    factor = 1 + scrap / 100
    mass = math.fsum(i.total_mass_kg for i in items)
    priced = [i for i in items if i.price_per_kg is not None]
    net = math.fsum(i.total_mass_kg * factor * i.price_per_kg for i in priced)
    return Totals(sum(i.count for i in items), mass, scrap, mass * factor,
                  math.fsum(i.total_mass_kg for i in priced) * factor, net, vat, net * vat / 100,
                  net * (1 + vat / 100), len(items) - len(priced))


__all__ = ['Item', 'Totals', 'COST_NOTE', 'from_result', 'edit', 'totals', 'validated']
