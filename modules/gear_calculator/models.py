"""Immutable specifications. Lengths: mm; angles: degrees; loads: kW, rpm, N m."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FutureGearData:
    """Reserved contract, rejected by MVP validation when populated."""
    normal_module_mm: float | None = None
    normal_pressure_angle_deg: float | None = None
    quality_grade: str | None = None
    material: str | None = None
    heat_treatment: str | None = None
    surface_hardness: str | None = None
    roughness_um: float | None = None
    lubrication: str | None = None
    temperature_c: float | None = None


@dataclass(frozen=True)
class GearSpecification:
    module_mm: float = 2.0
    teeth: int = 20
    pressure_angle_deg: float = 20.0
    face_width_mm: float = 15.0
    bore_mm: float = 8.0
    gear_type: str = 'external_spur'
    profile_shift: float = 0.0
    helix_angle_deg: float = 0.0
    backlash_mm: float = 0.0
    future: FutureGearData = field(default_factory=FutureGearData)


@dataclass(frozen=True)
class LoadSpecification:
    mode: str = 'power'
    input_rpm: float = 1500.0
    power_kw: float | None = 1.5
    torque_nm: float | None = None
    application_factor: float = 1.0
    design_life_hours: float = 10000.0


@dataclass(frozen=True)
class GearPairSpecification:
    pinion: GearSpecification = field(default_factory=GearSpecification)
    wheel: GearSpecification = field(default_factory=lambda: GearSpecification(teeth=40, bore_mm=12.0))
    load: LoadSpecification = field(default_factory=LoadSpecification)


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    field: str = ''
    severity: str = 'error'


@dataclass(frozen=True)
class GearResult:
    pitch_diameter_mm: float
    outside_diameter_mm: float
    root_diameter_mm: float
    base_diameter_mm: float
    circular_pitch_mm: float
    tooth_thickness_mm: float
    addendum_mm: float
    dedendum_mm: float
    whole_depth_mm: float
    clearance_mm: float
    pitch_radius_mm: float
    base_radius_mm: float
    outside_radius_mm: float
    root_radius_mm: float
    base_pitch_mm: float
    undercut_limit_teeth: float


@dataclass(frozen=True)
class GearPairResult:
    specification: GearPairSpecification
    pinion: GearResult
    wheel: GearResult
    ratio: float
    center_distance_mm: float
    working_center_distance_mm: float
    output_rpm: float
    input_torque_nm: float
    output_torque_nm: float
    power_kw: float
    tangential_force_n: float
    radial_force_n: float
    approach_length_mm: float
    recess_length_mm: float
    path_of_contact_mm: float
    transverse_contact_ratio: float
    warnings: tuple[Issue, ...]
