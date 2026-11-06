"""Version 1 immutable, JSON-compatible sheet development contracts (mm output)."""
from collections.abc import Mapping
from dataclasses import dataclass, fields, field, is_dataclass
import math
from uuid import uuid4

ENGINE_VERSION = '1.1.0'


@dataclass(frozen=True)
class FrozenMap(Mapping):
    entries: tuple = ()

    def __init__(self, value=()):
        items = value.items() if isinstance(value, Mapping) else value
        object.__setattr__(self, 'entries', tuple(sorted((str(k), freeze(v)) for k, v in items)))
        if len({k for k, _ in self.entries}) != len(self.entries):
            raise ValueError('Tekrarlanan alan adı.')

    def __iter__(self): return (k for k, _ in self.entries)
    def __len__(self): return len(self.entries)
    def __getitem__(self, key):
        for k, value in self.entries:
            if k == key: return value
        raise KeyError(key)


def freeze(value):
    if isinstance(value, FrozenMap): return value
    if isinstance(value, Mapping): return FrozenMap(value)
    if isinstance(value, (list, tuple)): return tuple(freeze(v) for v in value)
    if value is None or type(value) in (str, bool, int): return value
    if type(value) is float and math.isfinite(value): return value
    raise ValueError('Veri yalnız sonlu JSON değerleri içermeli.')


def to_data(value):
    if isinstance(value, Mapping): return {k: to_data(v) for k, v in value.items()}
    if is_dataclass(value): return {f.name: to_data(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (list, tuple)): return [to_data(v) for v in value]
    return value


@dataclass(frozen=True)
class Material:
    name: str = ''
    density_kg_m3: float | None = None
    unit_price: float | None = None
    price_unit: str = 'kg'  # kg / m2 / m (cut length)
    currency: str = ''


@dataclass(frozen=True)
class SeamOptions:
    start_angle_deg: float = 0.


@dataclass(frozen=True)
class SplitOptions:
    count: int = 1


@dataclass(frozen=True)
class JointOptions:
    kind: str = 'butt'
    overlap: float = 0.  # input length unit; only the end seam receives it


@dataclass(frozen=True)
class DevelopmentOptions:
    geometry_tolerance_mm: float = 1e-6
    chord_error_mm: float = .02
    mesh_error_mm: float = .5
    max_samples: int = 4096
    kerf_mm: float = 0.  # nonzero is explicitly refused in v1; CAM owns kerf


@dataclass(frozen=True)
class UnfoldRequest:
    shape_id: str = 'cylinder'
    variant_id: str = 'straight'
    parameters: FrozenMap = field(default_factory=FrozenMap)
    schema_version: int = 1
    request_id: str = field(default_factory=lambda: uuid4().hex)
    revision: int = 0
    input_units: str = 'mm'
    thickness: float = 0.
    dimension_reference: str = 'mid'
    material: Material = field(default_factory=Material)
    seam_options: SeamOptions = field(default_factory=SeamOptions)
    split_options: SplitOptions = field(default_factory=SplitOptions)
    joint_options: JointOptions = field(default_factory=JointOptions)
    development_options: DevelopmentOptions = field(default_factory=DevelopmentOptions)
    model_options: FrozenMap = field(default_factory=FrozenMap)

    def __post_init__(self):
        object.__setattr__(self, 'parameters', FrozenMap(self.parameters))
        object.__setattr__(self, 'model_options', FrozenMap(self.model_options))
        for name, cls in (('material', Material), ('seam_options', SeamOptions), ('split_options', SplitOptions),
                          ('joint_options', JointOptions), ('development_options', DevelopmentOptions)):
            value = getattr(self, name)
            if isinstance(value, Mapping): object.__setattr__(self, name, cls(**dict(value)))
            elif not isinstance(value, cls): raise ValueError(f'{name}: yanlış veri türü.')


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    severity: str = 'ERROR'
    field_ids: tuple[str, ...] = ()
    part_id: str | None = None


@dataclass(frozen=True)
class FieldSchema:
    id: str
    label: str
    description: str
    type: str = 'number'
    unit: str = 'length'
    default: float = 100.
    minimum: float | None = 0.
    maximum: float | None = 1e7
    required: bool = True
    choices: tuple = ()
    dimension_id: str = ''


@dataclass(frozen=True)
class ShapeSummary:
    shape_id: str
    label: str
    variants: tuple[str, ...]
    method: str
    category: str = ''
    variant_labels: FrozenMap = field(default_factory=FrozenMap)
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ShapeSchema:
    shape_id: str
    variant_id: str
    label: str
    fields: tuple[FieldSchema, ...]
    constraints: tuple[str, ...]
    seam_supported: bool
    split_supported: bool
    joint_kinds: tuple[str, ...]
    output_kinds: tuple[str, ...]
    supported_dimension_references: tuple[str, ...] = ('inner', 'mid', 'outer')
    source_id: str = ''
    model_options: FrozenMap = field(default_factory=FrozenMap)


@dataclass(frozen=True)
class ValidationReport:
    errors: tuple[Issue, ...] = ()
    warnings: tuple[Issue, ...] = ()
    normalized_inputs: FrozenMap = field(default_factory=FrozenMap)

    @property
    def valid(self): return not self.errors


Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


@dataclass(frozen=True)
class Line2D:
    start: Point2
    end: Point2
    id: str = ''
    kind: str = field(default='line', init=False)


@dataclass(frozen=True)
class Arc2D:
    center: Point2
    radius: float
    start_angle_deg: float
    sweep_deg: float
    kind: str = field(default='arc', init=False)


@dataclass(frozen=True)
class Circle2D:
    center: Point2
    radius: float
    kind: str = field(default='circle', init=False)


@dataclass(frozen=True)
class Polyline2D:
    points: tuple[Point2, ...]
    closed: bool = False
    kind: str = field(default='polyline', init=False)


Curve2D = Line2D | Arc2D | Circle2D | Polyline2D


@dataclass(frozen=True)
class Geometry2D:
    outer: tuple[Curve2D, ...]
    holes: tuple[tuple[Curve2D, ...], ...] = ()


@dataclass(frozen=True)
class Mesh3D:
    vertices: tuple[Point3, ...]
    triangles: tuple[tuple[int, int, int], ...]
    purpose: str = 'preview_only; not STEP geometry'


@dataclass(frozen=True)
class SurfacePatch:
    """Authoritative analytic/planar definition, independent of preview tessellation."""
    kind: str
    data: FrozenMap


@dataclass(frozen=True)
class DimensionAnnotation:
    id: str
    value: float
    unit: str
    parameter_id: str
    start: Point2
    end: Point2
    text_position: Point2
    extension: float = 5.
    arrows: str = 'both'


@dataclass(frozen=True)
class DrawingView:
    id: str
    label: str
    geometry: tuple[Curve2D, ...]


@dataclass(frozen=True)
class MappingPoint:
    developed: Point2
    assembled: Point3
    id: str


@dataclass(frozen=True)
class TrueLength:
    id: str
    start: Point3
    end: Point3
    length_mm: float


@dataclass(frozen=True)
class PartMetrics:
    net_area_mm2: float
    cutting_area_mm2: float
    rectangle_area_mm2: float
    cutting_length_mm: float
    bounds_mm: tuple[float, float, float, float]
    mass_kg: float | None
    material_cost: float | None


@dataclass(frozen=True)
class UnfoldPart:
    id: str
    code: str
    assembly_id: str
    quantity: int
    geometry_2d: Geometry2D
    mesh_3d: Mesh3D
    surface_patches: tuple[SurfacePatch, ...]
    drawing_views: tuple[DrawingView, ...]
    dimension_annotations: tuple[DimensionAnnotation, ...]
    bending_lines: tuple = ()
    construction_lines: tuple[Line2D, ...] = ()
    seams: tuple[Line2D, ...] = ()
    labels: tuple[tuple[str, Point2], ...] = ()
    true_lengths: tuple[TrueLength, ...] = ()
    mappings: tuple[MappingPoint, ...] = ()
    metrics: PartMetrics | None = None


@dataclass(frozen=True)
class UnfoldResult:
    request_id: str
    revision: int
    input_hash: str
    engine_version: str
    normalized_inputs: FrozenMap
    calculation_method: str
    status: str
    parts: tuple[UnfoldPart, ...] = ()
    metrics: FrozenMap = field(default_factory=FrozenMap)
    warnings: tuple[Issue, ...] = ()
    errors: tuple[Issue, ...] = ()
    capabilities: FrozenMap = field(default_factory=FrozenMap)
    quality_metrics: FrozenMap = field(default_factory=FrozenMap)


@dataclass(frozen=True)
class ExportOptions:
    path: str
    format: str = 'dxf'
    part_ids: tuple[str, ...] = ()
    overwrite: bool = False
    page_size: str = 'A4'
    include_pdf: bool = True
    include_step: bool = False
    expected_revision: int | None = None
    expected_input_hash: str | None = None
    project_name: str = ''
    project_code: str = ''
    project_revision: str = ''
    quantity_multiplier: int = 1


@dataclass(frozen=True)
class ExportedFile:
    path: str
    format: str
    sha256: str
    part_id: str | None = None


@dataclass(frozen=True)
class ExportResult:
    status: str
    request_id: str
    revision: int
    input_hash: str
    files: tuple[ExportedFile, ...] = ()
    errors: tuple[Issue, ...] = ()


@dataclass(frozen=True)
class ProjectItem:
    code: str
    request: UnfoldRequest
    quantity: int = 1


@dataclass(frozen=True)
class UnfoldProject:
    items: tuple[ProjectItem, ...]
    name: str = 'Sac açınımı'
    code: str = ''
    revision: str = ''
    quantity: int = 1
    engine_version: str = ENGINE_VERSION

    @property
    def needs_recalculation(self): return self.engine_version != ENGINE_VERSION
