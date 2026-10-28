"""Separate immutable millimetre contract; existing gear v1 records are untouched."""
from dataclasses import dataclass,field
from ..models import LoadSpecification

PROFILE='iso606_public_arcs_v1'


@dataclass(frozen=True)
class ChainSpecification:
    standard: str = 'ISO 606:2015'
    series: str = '08B-1'
    pitch_mm: float = 12.7
    roller_diameter_mm: float = 8.51
    inner_width_mm: float = 7.75
    strands: int = 1


@dataclass(frozen=True)
class SprocketSpecification:
    chain: ChainSpecification = field(default_factory=ChainSpecification)
    teeth: int = 20
    width_mm: float = 7.
    bore_mm: float = 10.
    hub_diameter_mm: float = 0.
    hub_length_mm: float = 0.  # Total axial length, including the toothed plate.
    material: str | None = None  # Descriptive only; no strength calculation.
    profile_reference: str = PROFILE


@dataclass(frozen=True)
class SprocketPairSpecification:
    driver: SprocketSpecification = field(default_factory=SprocketSpecification)
    driven: SprocketSpecification = field(default_factory=lambda:SprocketSpecification(teeth=40,bore_mm=15.))
    mounting_mode: str = 'center'
    center_distance_mm: float | None = 300.
    link_count: int | None = None
    load: LoadSpecification = field(default_factory=LoadSpecification)


@dataclass(frozen=True)
class SprocketDimensions:
    pitch_diameter_mm: float
    nominal_root_diameter_mm: float
    profile_root_diameter_mm: float
    outside_diameter_mm: float
    maximum_outside_diameter_mm: float
    seat_radius_mm: float
    flank_radius_mm: float
    seat_angle_deg: float
    angular_pitch_deg: float

    @property
    def pitch_radius_mm(self):return self.pitch_diameter_mm/2


@dataclass(frozen=True)
class SprocketPairResult:
    specification: SprocketPairSpecification
    driver: SprocketDimensions
    driven: SprocketDimensions
    ratio: float
    output_rpm: float
    power_kw: float
    input_torque_nm: float
    ideal_output_torque_nm: float
    chain_speed_m_s: float
    effective_force_n: float
    theoretical_links: float
    selected_links: int
    corrected_center_mm: float
    chain_length_mm: float
    small_wrap_deg: float
    large_wrap_deg: float
    warnings: tuple[str,...]
    cad_available: bool = True

    @property
    def values(self):
        s=self.specification;c=s.driver.chain
        return (('P',self.power_kw,'kW'),('n₁',s.load.input_rpm,'dev/dak'),('T₁',self.input_torque_nm,'N·m'),
            ('p',c.pitch_mm,'mm'),('dᵣ',c.roller_diameter_mm,'mm'),('b₁',c.inner_width_mm,'mm'),
            ('Dp₁',self.driver.pitch_diameter_mm,'mm'),('Dp₂',self.driven.pitch_diameter_mm,'mm'),
            ('Rp₁',self.driver.pitch_radius_mm,'mm'),('Rp₂',self.driven.pitch_radius_mm,'mm'),
            ('θ₁',self.driver.angular_pitch_deg,'°'),('θ₂',self.driven.angular_pitch_deg,'°'),
            ('Df₁ nominal',self.driver.nominal_root_diameter_mm,'mm'),('Df₂ nominal',self.driven.nominal_root_diameter_mm,'mm'),
            ('Df₁ profil',self.driver.profile_root_diameter_mm,'mm'),('Df₂ profil',self.driven.profile_root_diameter_mm,'mm'),
            ('Do₁ profil',self.driver.outside_diameter_mm,'mm'),('Do₂ profil',self.driven.outside_diameter_mm,'mm'),
            ('rᵢ',self.driver.seat_radius_mm,'mm'),('rₑ₁',self.driver.flank_radius_mm,'mm'),('rₑ₂',self.driven.flank_radius_mm,'mm'),
            ('i',self.ratio,''),('n₂',self.output_rpm,'dev/dak'),('T₂ ideal',self.ideal_output_torque_nm,'N·m'),
            ('v ortalama',self.chain_speed_m_s,'m/s'),('Ft etkin',self.effective_force_n,'N'),
            *((('C girilen',s.center_distance_mm,'mm'),) if s.mounting_mode=='center' else ()),
            ('L teorik',self.theoretical_links,'adım'),('L seçilen',float(self.selected_links),'bakla'),
            ('C düzeltilmiş',self.corrected_center_mm,'mm'),('Zincir uzunluğu',self.chain_length_mm,'mm'),
            ('Küçük sarılma',self.small_wrap_deg,'°'),('Büyük sarılma',self.large_wrap_deg,'°'))

    def value(self,symbol):return next(v for k,v,u in self.values if k==symbol)
