from dataclasses import dataclass, field
import math

from shapely.geometry import shape
from modules.nesting.models import Part, Project, Result, integer, number


PROFILES = {'Hızlı': (3, 2.), 'Dengeli': (7, 3.), 'Detaylı': (13, 5.)}


@dataclass(frozen=True)
class SplitSettings:
    count: int = 6
    quantity: int = 1
    start_angle: float = 0.
    center: tuple[float, float] | None = None
    center_mode: str = 'bounds'
    min_width: float = 1.
    min_web: float = 0.
    hole_clearance: float = 0.
    forbidden: tuple = ()  # GeoJSON polygons, in normalized source millimetres.
    joining: str = 'Kaynak'
    weld_gap: float = 0.
    allowance: float = 0.
    sheet_width: float = 1500.
    sheet_height: float = 3000.
    thickness: float = 2.
    material: str = 'S235JR'
    gap: float = 3.
    margin: float = 10.
    kerf: float = .2
    rotation: bool = True
    angles: tuple = (0., 90., 180., 270.)
    profile: str = 'Hızlı'

    def validate(self):
        for name, value, low, high in (('Segment sayısı',self.count,2,64),('Parça adedi',self.quantity,1,10000)):
            if type(value) is not int: raise ValueError(name+': tam sayı gerekli.')
            integer(value,name,minimum=low,maximum=high)
        if self.count*self.quantity>10000: raise ValueError('Toplam segment adedi 10000 sınırını aşıyor.')
        for key in ('min_width','sheet_width','sheet_height','thickness'):
            number(getattr(self,key),key,positive=True)
        for key in ('min_web','hole_clearance','weld_gap','allowance','gap','margin','kerf'):
            number(getattr(self,key),key)
        if self.weld_gap and self.allowance:
            raise ValueError('Kaynak boşluğu ve işleme payını bu sürümde ayrı senaryolarda kullanın.')
        if (not math.isfinite(self.start_angle) or self.center_mode not in ('bounds','centroid')
                or self.profile not in PROFILES or type(self.rotation) is not bool
                or not self.angles or len(self.angles)>360 or any(not math.isfinite(a) for a in self.angles)):
            raise ValueError('Bölme merkezi, açı, rotasyon veya arama profili geçersiz.')
        if self.center is not None and (len(self.center)!=2 or any(not math.isfinite(v) for v in self.center)):
            raise ValueError('Bölme merkezi iki sonlu mm koordinatı olmalı.')
        for region in self.forbidden:
            polygon=shape(region)
            if polygon.geom_type!='Polygon' or polygon.is_empty or not polygon.is_valid:
                raise ValueError('Yasaklı bölge geçerli bir poligon olmalı.')
        if self.joining not in ('Kaynak','Cıvata','Diğer') or not self.material:
            raise ValueError('Birleştirme yöntemi veya malzeme geçersiz.')


@dataclass
class Segment:
    id: str
    number: int
    original_name: str
    nominal: object  # Polygon in assembly coordinates
    blank: object    # Polygon with optional joining gap or edge allowance
    minimum_width: float
    seam_length: float = 0.
    neighbors: list[int] = field(default_factory=list)
    seam_edges: list = field(default_factory=list)


@dataclass
class SplitSolution:
    source: Part
    settings: SplitSettings
    center: tuple
    angles: tuple
    segments: list[Segment]
    area_delta: float
    symmetric_difference: float
    seam_length: float
    warnings: list[str]
    elapsed: float = 0.


@dataclass
class CandidateResult:
    label: str
    status: str
    sheets: int | None = None
    gross_area: float | None = None
    waste_percent: float | None = None
    seam_length: float | None = None
    reusable_area: float | None = None
    elapsed: float = 0.


@dataclass
class OptimizationResult:
    solution: SplitSolution
    project: Project
    nesting: Result
    candidates: list[CandidateResult]
    best_label: str
    elapsed: float
    stopped: bool = False
