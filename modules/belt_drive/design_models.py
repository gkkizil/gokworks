"""Immutable automatic-search inputs and auditable, explicitly partial results."""

from dataclasses import dataclass, field
from ._numbers import positive, finite, integer
from .catalog.products import text, sequence, BeltProduct, PulleyProduct, ProductSource
from .catalog.profiles import get_profile
from .models import BeltDriveResult, Issue
from .engineering.ratings import CapacityEvaluation

CRITERIA = ('speed', 'compact', 'fewest_belts', 'capacity', 'center', 'balanced')
METRICS = ('speed', 'center', 'area', 'belts', 'width', 'capacity', 'source')


@dataclass(frozen=True, slots=True)
class DesignRequest:
    power_kw: float
    input_rpm: float
    target_rpm: float
    family: str = 'v'
    profile: str | None = None
    manufacturer: str | None = None
    series_id: str | None = None
    mode: str = 'auto'  # auto / fixed / range
    center_target_mm: float | None = None
    center_min_mm: float | None = None
    center_max_mm: float | None = None
    center_tolerance_mm: float | None = None  # fixed only; no assumed adjustment travel.
    diameter_min_mm: float | None = None
    diameter_max_mm: float | None = None
    outside_diameter_max_mm: float | None = None
    teeth_min: int | None = None
    teeth_max: int | None = None
    rpm_error_max_percent: float | None = None
    system_width_max_mm: float | None = None
    max_belts: int | None = None
    available_installation_travel_mm: float | None = None
    available_tensioning_travel_mm: float | None = None
    service_factor: float | None = None
    daily_hours: float | None = None
    load_characteristic: str = ''
    starting_conditions: str = ''
    priority: str = 'speed'
    weights: tuple[tuple[str, float], ...] = ()
    include_unverified: bool = False
    result_limit: int = 200
    work_limit: int = 50000  # pair visits + length evaluations; computational, not physical.

    def __post_init__(self):
        for name in ('power_kw', 'input_rpm', 'target_rpm'):
            positive(getattr(self, name), name)
        positive(self.input_rpm / self.target_rpm, 'Hedef oran')
        if self.family not in ('v', 'timing'):
            raise ValueError('Otomatik tasarım yalnız V/triger-senkron aileyi destekler.')
        if self.profile is not None:
            profile = get_profile(self.profile)
            if not profile.nominal_supported or profile.family != self.family:
                raise ValueError('Arama profili/aile desteklenmiyor veya uyuşmuyor.')
        for name in ('manufacturer', 'series_id'):
            if getattr(self, name) is not None:
                text(getattr(self, name), name)
        for name in ('center_target_mm', 'center_min_mm', 'center_max_mm', 'diameter_min_mm',
                     'diameter_max_mm', 'outside_diameter_max_mm', 'system_width_max_mm', 'service_factor', 'daily_hours'):
            if getattr(self, name) is not None:
                positive(getattr(self, name), name)
        if self.daily_hours is not None and self.daily_hours > 24:
            raise ValueError('Günlük süre 24 saati aşamaz.')
        for name in ('center_tolerance_mm', 'rpm_error_max_percent', 'available_installation_travel_mm', 'available_tensioning_travel_mm'):
            if getattr(self, name) is not None and finite(getattr(self, name), name) < 0:
                raise ValueError(name + ': negatif olamaz.')
        for name in ('teeth_min', 'teeth_max', 'max_belts', 'result_limit', 'work_limit'):
            if getattr(self, name) is not None:
                integer(getattr(self, name), name)
        if self.result_limit > 5000 or self.work_limit > 1000000:
            raise ValueError('En çok 5000 sonuç / 1000000 iş adımı.')
        for low, high in (('center_min_mm', 'center_max_mm'), ('diameter_min_mm', 'diameter_max_mm'), ('teeth_min', 'teeth_max')):
            a, b = getattr(self, low), getattr(self, high)
            if a is not None and b is not None and a > b:
                raise ValueError(low + ' üst sınırı aşamaz.')
        if self.mode not in ('auto', 'fixed', 'range'):
            raise ValueError('Tasarım modu auto/fixed/range olmalı.')
        if self.mode == 'fixed':
            if self.center_target_mm is None or self.center_tolerance_mm is None or self.center_min_mm is not None or self.center_max_mm is not None:
                raise ValueError('Sabit C modunda hedef ve açık tolerans gerekli; ayrıca C aralığı verilmez.')
        elif self.center_tolerance_mm is not None:
            raise ValueError('Ayar toleransı yalnız sabit C modunda kullanılır.')
        if self.mode == 'range' and (self.center_min_mm is None or self.center_max_mm is None):
            raise ValueError('Aralık modunda C min/max gerekli.')
        if self.mode != 'fixed' and self.center_target_mm is not None:
            if self.center_min_mm is not None and self.center_target_mm < self.center_min_mm or \
               self.center_max_mm is not None and self.center_target_mm > self.center_max_mm:
                raise ValueError('C hedefi belirtilen aralık içinde olmalı.')
        if self.priority not in CRITERIA or self.priority == 'center' and self.center_target_mm is None:
            raise ValueError('Sıralama önceliği veya C hedefi geçersiz.')
        for name in ('load_characteristic', 'starting_conditions'):
            text(getattr(self, name), name, optional=True)
        if type(self.include_unverified) is not bool:
            raise ValueError('include_unverified bool olmalı.')
        weights = tuple(sequence(item, 'Ağırlık çifti', maximum=2) for item in sequence(self.weights, 'Ağırlıklar', maximum=len(METRICS)))
        if any(len(item) != 2 or item[0] not in METRICS for item in weights) or len({x[0] for x in weights}) != len(weights):
            raise ValueError('Bilinmeyen/tekrarlanan sıralama ölçütü.')
        for _, weight in weights:
            if finite(weight, 'Ağırlık') < 0:
                raise ValueError('Sıralama ağırlığı negatif olamaz.')
        if weights and not any(weight > 0 for _, weight in weights):
            raise ValueError('En az bir pozitif ağırlık gerekli.')
        if weights and self.priority != 'balanced':
            raise ValueError('Kullanıcı ağırlıkları yalnız balanced önceliğinde kullanılır.')
        object.__setattr__(self, 'weights', weights)


@dataclass(frozen=True, slots=True)
class DesignCandidate:
    identifier: str
    manufacturer: str
    series_id: str
    driver: PulleyProduct
    driven: PulleyProduct
    belt: BeltProduct
    result: BeltDriveResult
    rpm_deviation: float
    rpm_error_percent: float
    theoretical_length_at_target_mm: float | None
    center_deviation_mm: float | None
    belt_count: int | None
    system_width_mm: float | None
    reference_area_mm2: float
    capacity: CapacityEvaluation
    source_statuses: tuple[str, ...]
    checks: tuple[Issue, ...]
    status: str
    ranking_key: tuple
    system_width_lower_bound_mm: float | None = None
    engineering_approved: bool = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class RejectedCombination:
    driver_code: str
    driven_code: str
    belt_code: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class DesignSearchReport:
    request: DesignRequest
    catalog_id: str
    catalog_revision: str
    catalog_sha256: str
    target_ratio: float
    capacity_verified: tuple[DesignCandidate, ...]
    unverified: tuple[DesignCandidate, ...]
    rejections: tuple[RejectedCombination, ...]
    pairs_visited: int
    lengths_evaluated: int
    geometry_solved: int
    capacity_verified_count: int
    unverified_count: int
    rejection_counts: tuple[tuple[str, int], ...]
    excluded_products: int
    search_complete: bool
    results_limited: bool
    cancelled: bool
    stop_reason: str
    assumptions: tuple[str, ...]
    sources: tuple[ProductSource, ...] = ()
