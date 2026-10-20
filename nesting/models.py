"""Millimetre-only domain model, independent of Qt and SolidWorks."""

from dataclasses import dataclass, field, asdict
import hashlib
import json
import math
import uuid

from shapely.geometry import shape, mapping


def uid():
    return uuid.uuid4().hex


def number(value, name='Değer', *, minimum=0, positive=False):
    try:
        value = float(str(value).replace(',', '.'))
    except (ValueError, TypeError):
        raise ValueError(f'{name}: geçerli bir sayı girin.') from None
    if not math.isfinite(value) or value < minimum or (positive and value == 0):
        raise ValueError(f'{name}: sonlu ve {"pozitif" if positive else "negatif olmayan"} bir sayı girin.')
    return value


def integer(value, name, *, minimum=1, maximum=10000):
    n = number(value, name, minimum=minimum)
    if not n.is_integer() or n > maximum:
        raise ValueError(f'{name}: {minimum}–{maximum} arasında tam sayı girin.')
    return int(n)


@dataclass
class Material:
    id: str
    name: str
    density: float
    source: str = 'Kullanıcı tanımı'


@dataclass
class Part:
    id: str
    code: str
    geometry: dict
    material: str
    thickness: float
    quantity: int = 1
    description: str = ''
    source: str = ''
    source_sha256: str = ''
    source_unit: str = 'mm'
    curve_tolerance: float = 0
    join_tolerance: float = .001
    original_dxf: str = ''
    notes: list[str] = field(default_factory=list)
    grain_locked: bool = False
    endpoint_error: float = 0

    @property
    def polygon(self):
        return shape(self.geometry)

    @property
    def area(self):
        return self.polygon.area

    @property
    def geometry_error(self):
        return self.curve_tolerance+self.endpoint_error

    @classmethod
    def create(cls, code, polygon, material='S235JR', thickness=2, **kwargs):
        return cls(uid(), code, mapping(polygon), material, thickness, **kwargs)


@dataclass
class Sheet:
    id: str
    name: str
    width: float = 1250
    height: float = 2500
    thickness: float = 2
    material: str = 'S235JR'
    stock: int = 100
    price_kg: float = 0
    price_sheet: float = 0
    pricing: str = 'kg'


@dataclass
class Options:
    gap: float = 3
    margin: float = 10
    kerf: float = .2
    rotation: bool = True
    angles: list[float] = field(default_factory=lambda: [0, 90, 180, 270])
    grain_locked: bool = False
    seconds: float = 15
    quality: str = 'Dengeli'
    seed: int = 42


@dataclass
class Operations:
    cut_price_m: float = 0
    piercing_price: float = 0
    setup: float = 0
    fixed: float = 0
    profit_percent: float = 0
    vat_percent: float = 0


@dataclass
class Placement:
    part_id: str
    instance: int
    sheet_id: str
    sheet_number: int
    x: float
    y: float
    angle: float


@dataclass
class Result:
    digest: str
    placements: list[Placement]
    unplaced: list[str]
    engine: str
    engine_version: str
    elapsed: float
    iterations: int
    timestamp: str
    stopped: bool = False


@dataclass
class Project:
    name: str = 'Yeni nesting projesi'
    materials: list[Material] = field(default_factory=list)
    parts: list[Part] = field(default_factory=list)
    sheets: list[Sheet] = field(default_factory=list)
    options: Options = field(default_factory=Options)
    operations: Operations = field(default_factory=Operations)

    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), ensure_ascii=False, sort_keys=True,
                                         allow_nan=False).encode()).hexdigest()

    def placement_fingerprint(self):
        """Costs, labels and densities do not change where contours may be placed."""
        data = asdict(self)
        data.pop('name'); data.pop('operations'); data['materials'] = [m.id for m in self.materials]
        for part in data['parts']:
            for key in ('code','description','notes','source','source_sha256','source_unit'):
                part.pop(key,None)
        for sheet in data['sheets']:
            for key in ('name','price_kg','price_sheet','pricing'):
                sheet.pop(key,None)
        return hashlib.sha256(json.dumps(data,sort_keys=True,allow_nan=False).encode()).hexdigest()

    def material(self, key):
        return next(m for m in self.materials if m.id == key)

    def part(self, key):
        return next(p for p in self.parts if p.id == key)

    def sheet(self, key):
        return next(s for s in self.sheets if s.id == key)

    def validate(self, *, require_work=True):
        if require_work and (not self.parts or not self.sheets):
            raise ValueError('En az bir DXF parçası ve bir sac tanımlayın.')
        for title, items in [('Malzeme', self.materials), ('Parça', self.parts), ('Sac', self.sheets)]:
            ids = [item.id for item in items]
            if len(ids) != len(set(ids)) or any(not k for k in ids):
                raise ValueError(f'{title} kimlikleri benzersiz olmalı.')
        for m in self.materials:
            number(m.density, 'Yoğunluk', positive=True)
        for item in [*self.parts, *self.sheets]:
            if item.material not in {m.id for m in self.materials}:
                raise ValueError('Parça veya sac malzemesi kütüphanede yok.')
            number(item.thickness, 'Kalınlık', positive=True)
        for p in self.parts:
            if type(p.quantity) is not int or type(p.grain_locked) is not bool:
                raise ValueError('Parça adedi tam sayı, hadde kilidi doğru/yanlış olmalı.')
            integer(p.quantity, 'Parça adedi')
            g = p.polygon
            if g.geom_type not in ('Polygon', 'MultiPolygon') or not g.is_valid or g.is_empty or g.area <= 0:
                raise ValueError(p.code + ': geçerli kapalı kontur gerekli.')
            if any(not math.isfinite(v) for v in g.bounds):
                raise ValueError('Sonlu olmayan geometri.')
            number(p.curve_tolerance, 'Kontur toleransı')
            number(p.join_tolerance, 'Birleştirme toleransı', positive=True)
            number(p.endpoint_error,'Uç birleştirme hata payı')
        if sum(p.quantity for p in self.parts) > 10000:
            raise ValueError('Bir projede en fazla 10000 parça örneği desteklenir.')
        for s in self.sheets:
            if type(s.stock) is not int:
                raise ValueError('Sac stok adedi tam sayı olmalı.')
            for name in ('width', 'height'):
                number(getattr(s, name), 'Sac ölçüsü', positive=True)
            integer(s.stock, 'Stok adedi', minimum=0)
            number(s.price_kg, 'TL/kg'); number(s.price_sheet, 'TL/levha')
            if s.pricing not in ('kg', 'sheet'):
                raise ValueError('Fiyatlandırma kg veya sheet olmalı.')
        o = self.options
        if type(o.rotation) is not bool or type(o.grain_locked) is not bool:
            raise ValueError('Döndürme ve hadde kilidi doğru/yanlış olmalı.')
        for key in ('gap', 'margin', 'kerf'):
            number(getattr(o, key), key)
        number(o.seconds, 'Optimizasyon süresi', positive=True)
        if o.seconds > 600 or o.quality not in ('Hızlı', 'Dengeli', 'Yüksek'):
            raise ValueError('Süre en fazla 600 saniye; kalite Hızlı, Dengeli veya Yüksek olmalı.')
        if not o.angles or len(o.angles) > 360 or any(not math.isfinite(a) for a in o.angles):
            raise ValueError('1–360 geçerli dönüş açısı tanımlayın.')
        integer(o.seed, 'Seed', minimum=0, maximum=2**32-1)
        for key, value in asdict(self.operations).items():
            number(value, key)
