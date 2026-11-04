"""Immutable specifications and nominal results. mm, kW, rpm, N and N·m."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .geometry import BeltPath


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    message: str
    field: str = ''
    severity: str = 'ERROR'  # ERROR / WARNING / INFO / NOT_EVALUATED


class SpecificationError(ValueError):
    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__('\n'.join(item.message for item in self.issues))


@dataclass(frozen=True, slots=True)
class BeltSpecification:
    family: str = 'v'
    profile: str = 'A'
    pitch_mm: float | None = None
    count: int = 1  # Explicit user choice, never a capacity-based recommendation.


@dataclass(frozen=True, slots=True)
class PulleySpecification:
    datum_diameter_mm: float | None = 100.
    teeth: int | None = None


@dataclass(frozen=True, slots=True)
class LoadSpecification:
    input_rpm: float = 1450.
    power_kw: float | None = 5.
    torque_nm: float | None = None
    efficiency: float | None = None
    service_factor: float | None = None


@dataclass(frozen=True, slots=True)
class CenterSpecification:
    mode: str = 'center'  # center → theoretical length; length → physical center.
    distance_mm: float | None = 400.
    length_mm: float | None = None  # V datum length only.
    belt_teeth: int | None = None  # Timing: integer N, pitch length = N*p.
    driver_x_mm: float = 0.
    driver_y_mm: float = 0.
    axis_angle_deg: float = 0.


@dataclass(frozen=True, slots=True)
class BeltDriveSpecification:
    belt: BeltSpecification = field(default_factory=BeltSpecification)
    driver: PulleySpecification = field(default_factory=PulleySpecification)
    driven: PulleySpecification = field(default_factory=lambda: PulleySpecification(200.))
    load: LoadSpecification = field(default_factory=LoadSpecification)
    center: CenterSpecification = field(default_factory=CenterSpecification)
    pretension_per_belt_n: float | None = None
    rotation: str = 'ccw'
    drive_type: str = 'open'


@dataclass(frozen=True, slots=True)
class LengthMetrics:
    center_mm: float
    alpha_rad: float  # Signed: driven radius minus driver radius.
    straight_mm: float
    driver_wrap_rad: float
    driven_wrap_rad: float
    exact_mm: float
    approximate_mm: float


@dataclass(frozen=True, slots=True)
class CenterSolution:
    center_mm: float
    residual_mm: float
    iterations: int


@dataclass(frozen=True, slots=True)
class ShaftForces:
    initial_per_belt_n: float
    tight_per_belt_n: float
    slack_per_belt_n: float
    driver_fx_n: float
    driver_fy_n: float
    driven_fx_n: float
    driven_fy_n: float
    resultant_n: float
    model: str = 'F1=F0+Ft/(2*count); F2=F0-Ft/(2*count); massless equal-load belts'


@dataclass(frozen=True, slots=True)
class BeltDriveResult:
    specification: BeltDriveSpecification
    reference_line: str
    driver_reference_diameter_mm: float
    driven_reference_diameter_mm: float
    pitch_mm: float | None
    ratio: float
    nominal_output_rpm: float
    input_power_kw: float
    input_torque_nm: float
    ideal_output_torque_nm: float
    efficiency_output_power_kw: float | None
    efficiency_output_torque_nm: float | None
    design_power_kw: float | None
    speed_m_s: float
    effective_force_delta_n: float
    design_force_delta_n: float | None
    center_mm: float
    length_exact_mm: float
    length_approximate_mm: float
    approximation_minus_exact_mm: float
    selected_length_mm: float | None
    inverse_residual_mm: float | None
    driver_wrap_deg: float
    driven_wrap_deg: float
    theoretical_belt_teeth: float | None
    selected_belt_teeth: int | None
    engaged_driver_teeth_estimate: float | None
    engaged_driven_teeth_estimate: float | None
    shaft_forces: ShaftForces | None
    geometry: 'BeltPath'
    checks: tuple[Issue, ...]
    assumptions: tuple[str, ...]
    geometry_valid: bool = field(default=True, init=False)
    power_capacity_verified: bool = field(default=False, init=False)
    production_approved: bool = field(default=False, init=False)
    cad_available: bool = field(default=False, init=False)
