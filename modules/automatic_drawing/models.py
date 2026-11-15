"""Plain worker/UI contracts. CAD lengths are metres; these records use millimetres."""

from dataclasses import asdict, dataclass, field
import math
from pathlib import Path

SCHEMA_VERSION = 1
SCALES = (5., 2., 1., .5, .4, .2, .1, .05, .02, .01)
PAPERS = {'A4': (297., 210.), 'A3': (420., 297.), 'A2': (594., 420.),
          'A1': (841., 594.), 'A0': (1189., 841.)}
STAGES = ('Ön kontrol', 'Model açılıyor', 'Geometri inceleniyor', 'Parça sınıflandırılıyor',
          'Resim planlanıyor', 'Şablon doğrulanıyor', 'Teknik resim oluşturuluyor',
          'Görünüşler oluşturuluyor', 'Model ölçüleri aktarılıyor', 'Ölçüler planlanıyor',
          'Yerleşim düzenleniyor', 'Resim ayrıntıları ekleniyor', 'Resim güncelleniyor',
          'Resim doğrulanıyor', 'SLDDRW kaydediliyor', 'Dışa aktarılıyor',
          'Kayıt kontrol ediliyor', 'Rapor hazırlanıyor')


def finite(value, name='Değer', *, minimum=None, maximum=None):
    if isinstance(value, bool):
        raise ValueError(name + ' sayı olmalı.')
    number = float(value)
    if not math.isfinite(number) or (minimum is not None and number < minimum) or (
            maximum is not None and number > maximum):
        raise ValueError(name + ' izin verilen aralıkta, sonlu bir sayı olmalı.')
    return number


def to_mm(metres):
    return finite(metres, 'API uzunluğu') * 1000.


def to_m(mm):
    return finite(mm, 'Uzunluk') / 1000.


def degrees(radians):
    return math.degrees(finite(radians, 'API açısı'))


def identity(path, configuration=''):
    # Windows file names are insensitive to case; configuration names are not.
    return str(path).replace('\\', '/').rstrip('/').casefold(), str(configuration)


class Cancelled(RuntimeError):
    pass


def checkpoint(stop):
    if stop is not None and stop.is_set():
        raise Cancelled('İşlem kullanıcı tarafından durduruldu.')


@dataclass(frozen=True)
class Source:
    path: str
    configuration: str = ''

    @property
    def key(self):
        return identity(self.path, self.configuration)


@dataclass
class Node:
    name: str
    source: Source
    kind: str = 'part'
    state: str = 'ready'
    hidden: bool = False
    excluded_bom: bool = False
    children: list = field(default_factory=list)
    detail: str = ''


@dataclass(frozen=True)
class FaceEvidence:
    kind: str
    area_mm2: float
    direction: tuple = ()
    radius_mm: float | None = None
    point_mm: tuple = ()


@dataclass
class ModelInfo:
    source: Source
    kind: str
    title: str
    size_mm: tuple
    properties: dict = field(default_factory=dict)
    feature_types: dict = field(default_factory=dict)
    faces: list = field(default_factory=list)
    body_count: int = 0
    sheet_body_count: int = 0
    configurations: tuple = ()
    flat_configurations: tuple = ()
    source_unit: str = 'unknown'
    mass_kg: float | None = None
    volume_m3: float | None = None
    thickness_mm: tuple = ()
    tree: Node | None = None
    warnings: list = field(default_factory=list)
    classification: str = 'general'
    classification_reason: str = ''
    revision: str = ''
    fingerprint: tuple = ()
    memory_stamp: int | None = None


@dataclass(frozen=True)
class Options:
    template: str = ''
    sheet_format: str = ''
    paper: str = 'A3'
    custom_width_mm: float = 420.
    custom_height_mm: float = 297.
    scales: tuple = SCALES
    manual_scale: float | None = None
    projection: str = 'first'
    main_view: str = 'auto'
    classification: str = 'auto'
    top: bool = True
    side: bool = True
    isometric: bool = True
    model_dimensions: bool = True
    include_unmarked: bool = False
    geometry_dimensions: bool = False
    arrange_dimensions: bool = True
    center_marks: bool = True
    flat_pattern: bool = True
    bend_lines: bool = True
    bom: bool = True
    bom_type: str = 'parts'
    bom_template: str = ''
    balloons: bool = False
    assembly_scope: str = 'assembly'
    pdf: bool = True
    dxf: bool = False
    output_dir: str = ''
    naming: str = '{name}-{configuration}'
    existing: str = 'unique'
    property_map: tuple = (('PartNumber', 'PartNumber'), ('Description', 'Description'),
                           ('Material', 'Material'), ('Revision', 'Revision'),
                           ('DrawnBy', 'DrawnBy'))
    margin_mm: float = 10.
    title_height_mm: float = 40.
    annotation_padding_mm: float = 15.
    gap_mm: float = 16.

    def validate(self):
        if self.paper not in (*PAPERS, 'auto', 'custom'):
            raise ValueError('Geçersiz pafta boyutu.')
        for name in ('custom_width_mm', 'custom_height_mm'):
            finite(getattr(self, name), name, minimum=100, maximum=5000)
        for name in ('margin_mm', 'title_height_mm', 'annotation_padding_mm', 'gap_mm'):
            finite(getattr(self, name), name, minimum=0, maximum=250)
        if self.projection not in ('first', 'third'):
            raise ValueError('İzdüşüm birinci veya üçüncü açı olmalı.')
        if not self.scales or len(self.scales) > 100:
            raise ValueError('En az bir, en çok 100 tercih edilen ölçek girin.')
        for scale in self.scales:
            finite(scale, 'Ölçek', minimum=.0001, maximum=1000)
        if self.manual_scale is not None:
            finite(self.manual_scale, 'Manuel ölçek', minimum=.0001, maximum=1000)
        if self.existing not in ('unique', 'skip'):
            raise ValueError('Mevcut çıktı için atla veya yeni ad üret seçin.')
        if self.bom_type not in ('parts', 'top', 'indented'):
            raise ValueError('Geçersiz BOM türü.')
        if self.assembly_scope not in ('assembly', 'parts', 'all'):
            raise ValueError('Geçersiz montaj işleme kapsamı.')
        if self.main_view not in ('auto', 'front', 'back', 'top', 'bottom', 'right', 'left'):
            raise ValueError('Geçersiz ana görünüş.')
        if self.classification not in ('auto', 'general', 'sheet', 'plate', 'block', 'shaft',
                                        'flange', 'bushing', 'weldment', 'multibody', 'freeform'):
            raise ValueError('Geçersiz parça sınıfı.')
        if not isinstance(self.naming, str) or not self.naming.strip() or len(self.naming) > 200:
            raise ValueError('Dosya adlandırma şablonu geçersiz.')
        if len(self.property_map) > 50:
            raise ValueError('En çok 50 antet alanı eşleştirilebilir.')
        targets = set()
        for pair in self.property_map:
            if len(pair) != 2 or not all(isinstance(s, str) and s.strip() for s in pair):
                raise ValueError('Antet eşleştirmesinde kaynak ve hedef alanı girin.')
            if pair[1].casefold() in targets:
                raise ValueError('Aynı antet hedef alanına iki model özelliği atanamaz: '+pair[1])
            targets.add(pair[1].casefold())
        for path, suffix in ((self.template, '.drwdot'), (self.sheet_format, '.slddrt'),
                             (self.bom_template, '.sldbomtbt')):
            if path and (Path(path).suffix.casefold() != suffix or not Path(path).is_file()):
                raise ValueError('Şablon bulunamadı veya türü yanlış: ' + str(path))
        return self


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self):
        for n in ('x', 'y', 'width', 'height'):
            finite(getattr(self, n), 'Sınır kutusu', minimum=0 if n in ('width', 'height') else None)

    @property
    def right(self): return self.x + self.width

    @property
    def top(self): return self.y + self.height

    @property
    def center(self): return self.x + self.width / 2, self.y + self.height / 2

    def contains(self, other, tolerance=.05):
        return (other.x >= self.x-tolerance and other.y >= self.y-tolerance and
                other.right <= self.right+tolerance and other.top <= self.top+tolerance)

    def overlaps(self, other, gap=0.):
        return not (self.right+gap <= other.x or other.right+gap <= self.x or
                    self.top+gap <= other.y or other.top+gap <= self.y)

    def grow(self, pad):
        return Box(self.x-pad, self.y-pad, self.width+2*pad, self.height+2*pad)

    def shifted(self, dx, dy):
        return Box(self.x+dx, self.y+dy, self.width, self.height)


@dataclass(frozen=True)
class ViewPlan:
    role: str
    model_view: str
    footprint: tuple
    center: tuple = (0., 0.)
    parent: str = ''


@dataclass
class SheetPlan:
    name: str
    paper: str
    width_mm: float
    height_mm: float
    scale: float
    views: list
    usable: Box


@dataclass
class Finding:
    severity: str
    code: str
    text: str
    sheet: str = ''
    view: str = ''


@dataclass
class DrawingResult:
    source: Source
    status: str = 'FAIL'
    stage: str = ''
    outputs: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    analysis: ModelInfo | None = None
    sheets: list = field(default_factory=list)
    measurements: dict = field(default_factory=dict)
    completed_stages: list = field(default_factory=list)
    elapsed_s: float = 0.
    api_revision: str = ''
    schema_version: int = SCHEMA_VERSION

    def warn(self, code, text, sheet='', view=''):
        self.findings.append(Finding('WARNING', code, text, sheet, view))

    def fail(self, code, text, sheet='', view=''):
        self.findings.append(Finding('FAIL', code, text, sheet, view))

    def classify(self):
        self.status = ('FAIL' if any(f.severity == 'FAIL' for f in self.findings) else
                       'WARNING' if self.findings else 'PASS')
        return self.status

    def as_dict(self):
        return asdict(self)
