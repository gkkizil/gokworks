"""Explicit units and capabilities, independent of Qt and CAD imports."""
from dataclasses import dataclass, field
from ..models import LoadSpecification


@dataclass(frozen=True)
class Capability:
    title: str
    geometry: bool
    note: str


CATALOG = {
    'rack': Capability('Kremayer – pinyon', True, 'Düz kremayer; sonlu strok; radyal pinyon dip bağlantısı.'),
    'helical': Capability('Helisel dişli çifti', True, 'Normal modül/açı; eşit ve ters helis; eksenel kuvvet dahil.'),
    'herringbone': Capability('Çift helisel dişli çifti', True, 'Ortada boşluksuz V birleşimi; simetrik iki yarı; ideal eksenel dengeleme.'),
    'internal': Capability('İç dişli – pinyon', True, '20° düz iç dişli; düzlemsel evolvent; kesici trokoidi modellenmez.'),
    'planetary': Capability('Planet dişli sistemi', True, 'Düz; sabit halka, güneş giriş, taşıyıcı çıkış; eşit aralıklı planetler.'),
    'bevel': Capability('Ayna – mahruti · düz konik', False, 'Nominal koni/boyut hesabı. Eşlenik küresel yüzey CAD doğrulaması henüz yok.'),
    'spiral_bevel': Capability('Ayna – mahruti · spiral konik', False, 'Sıfır ofsetli bölüm konileri ve ideal kinematik. Gleason/Klingelnberg kesici yüzeyi henüz yok.'),
    'hypoid': Capability('Ayna – mahruti · hipoid', False, 'Yalnız diş sayısı oranı/ideal güç kinematiği. Ofsetli eşlenik yüzey çözücüsü henüz yok.'),
    'worm': Capability('Sonsuz vida – çark', False, 'Eksenel modül; ağız sayısı, çap katsayısı ve nominal boyutlar. Zarflanmış çark yüzeyi henüz yok.'),
    'cycloidal': Capability('Sikloid pimli redüktör', True, 'N pim / N−1 loblu disk; analitik pim zarfı; taşıyıcı/çıkış pimleri bu modelde yok.'),
}


@dataclass(frozen=True)
class MechanismSpecification:
    kind: str = 'rack'
    module_mm: float = 2.
    teeth1: int = 20
    teeth2: int = 40
    pressure_angle_deg: float = 20.
    width_mm: float = 15.
    bore1_mm: float = 8.
    bore2_mm: float = 12.
    helix_deg: float = 20.
    rack_teeth: int = 16
    rack_base_mm: float = 10.
    rim_mm: float = 5.
    planets: int = 3
    shaft_angle_deg: float = 90.
    offset_mm: float = 10.
    worm_starts: int = 2
    diameter_quotient: float = 10.
    eccentricity_mm: float = .5
    roller_radius_mm: float = 1.5
    load: LoadSpecification = field(default_factory=LoadSpecification)


@dataclass(frozen=True)
class MechanismResult:
    specification: MechanismSpecification
    values: tuple[tuple[str, float, str], ...]
    warnings: tuple[str, ...]
    cad_available: bool

    def value(self, symbol):
        return next(value for key, value, unit in self.values if key == symbol)
