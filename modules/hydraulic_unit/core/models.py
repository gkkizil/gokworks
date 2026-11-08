"""Değişmez HPU modelleri. Bütün sayısal fiziksel girdiler SI birimindedir."""
from dataclasses import dataclass, field
from .catalogs import (DEFAULT_E, CYLINDER_EFFICIENCY, DEFAULT_DENSITY,
                       RELIEF_FACTOR, OVERLOAD)


@dataclass(frozen=True)
class Cylinder:
    id: str = 'C1'
    bore: float = .063
    rod: float = .036
    stroke: float = .3
    efficiency: float = CYLINDER_EFFICIENCY
    effective_length: float = .8
    mounting: str = 'pinned_pinned'
    young_modulus: float = DEFAULT_E
    initial_position: float = 0.


@dataclass(frozen=True)
class CylinderOperatingPoint:
    pressure: float = 160e5
    force: float = 35000.
    kind: str = 'extend'
    speed: float | None = .04
    duration: float | None = None
    travel: float = .3
    back_pressure: float = 0.


@dataclass(frozen=True)
class Phase:
    name: str = 'İtme'
    cylinder_id: str = 'C1'
    kind: str = 'extend'
    force: float = 35000.
    stroke: float = .3
    speed: float | None = .04
    duration: float | None = None
    back_pressure: float = 0.


@dataclass(frozen=True)
class Pump:
    kind: str = 'gear'
    displacement: float = 16e-6
    angular_speed: float = 1450 * 2 * 3.141592653589793 / 60
    volumetric_efficiency: float = .95
    mechanical_efficiency: float = .90
    max_pressure: float = 250e5
    control: str = 'fixed'
    compensator_pressure: float = 160e5
    power_limit: float = 7500.
    leakage_flow: float = 0.
    idle_pressure: float = 5e5


@dataclass(frozen=True)
class Pipe:
    role: str = 'pressure'
    target_velocity: float = 4.
    min_velocity: float = 3.
    max_velocity: float = 6.
    length: float = 5.
    diameter: float | None = None
    zeta: tuple[float, ...] = (1., 1.)
    hose_laminar: bool = False


@dataclass(frozen=True)
class Oil:
    grade: str = 'ISO VG 46'
    nu40: float = 46e-6
    nu100: float = 6.8e-6
    temperature: float = 313.15
    density: float = DEFAULT_DENSITY
    source: str = 'Örnek yağ: 40/100 °C değerleri üretici ürünü değildir.'


@dataclass(frozen=True)
class Thermal:
    installation: str = 'stationary'
    residence_time: float = 240.
    length: float = .8
    width: float = .5
    height: float = .5
    fill_fraction: float = .8
    heat_transfer: float = 12.
    ambient: float = 293.15
    target: float = 323.15


@dataclass(frozen=True)
class Accumulator:
    enabled: bool = False
    minimum_pressure: float = 100e5
    maximum_pressure: float = 160e5
    precharge_pressure: float | None = None
    delivery_volume: float = .001
    exponent: float = 1.4
    atmospheric_pressure: float = 101325.


@dataclass(frozen=True)
class Project:
    name: str = 'Hidrolik pres ünitesi'
    cylinders: tuple[Cylinder, ...] = field(default_factory=lambda: (Cylinder(),))
    phases: tuple[Phase, ...] = field(default_factory=lambda: (
        Phase('Hızlı yaklaşma', kind='regenerate', force=5000., speed=.12, stroke=.25),
        Phase('Presleme', force=35000., speed=.025, stroke=.05),
        Phase('Basınçta bekleme', kind='hold', force=35000., speed=None, duration=3.),
        Phase('Geri dönüş', kind='retract', force=3000., speed=.1)))
    pump: Pump = field(default_factory=Pump)
    pipe: Pipe = field(default_factory=Pipe)
    oil: Oil = field(default_factory=Oil)
    thermal: Thermal = field(default_factory=Thermal)
    accumulator: Accumulator = field(default_factory=Accumulator)
    overload: float = OVERLOAD
    relief_factor: float = RELIEF_FACTOR
    relief_pressure: float | None = None
    selected_motor: float | None = None
    display_units: str = 'metric'
