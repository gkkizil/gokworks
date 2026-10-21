"""ANSI K faktörü, havada büküm takımları ve bağımsız BA ölçüm hesabı.

Tablolar genel başlangıç önerileridir. Uzunluklar mm, açı düz sactan dönülen
büküm açısıdır. Tablo hesabı, bağımsız üretim ölçümü yerine geçmez.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Material:
    key: str
    label: str
    hardness: str
    air_radius_ratio: float


MATERIALS = (
    Material("steel", "Düşük karbonlu çelik — genel", "medium", .16),
    Material("stainless", "Paslanmaz çelik — genel", "hard", .20),
    Material("aluminium", "Yumuşak alüminyum — genel", "soft", .16),
)
# Generic ANSI table: FreeCAD SheetMetal tools/README.md, sourced there from
# Bending (metalworking). Explicit bands, without invented interpolation.
AIR_K = {"soft": (.33, .40, .50), "medium": (.38, .43, .50),
         "hard": (.40, .45, .50)}
DIE_OPENINGS = (6, 8, 10, 12, 16, 20, 24, 32, 40, 50, 63, 80, 100)
PUNCH_RADII = (.5, .8, 1, 1.5, 2, 3, 4, 5, 6)
TOOL_ANGLES = (30, 60, 85, 88, 90)


def number(value, label, *, zero=False):
    """Ondalık virgül kabul et; NaN/inf, bool ve geçersiz ölçüleri reddet."""
    if isinstance(value, bool):
        raise ValueError(f"{label} geçersiz.")
    try:
        value = float(str(value).strip().replace(",", "."))
    except (ValueError, TypeError):
        raise ValueError(f"{label} için geçerli bir sayı girin.") from None
    if not math.isfinite(value) or value < 0 or (not zero and value == 0):
        raise ValueError(f"{label} için {'sıfır veya daha büyük' if zero else 'sıfırdan büyük'} bir sayı girin.")
    return value


def _geometry(thickness, radius, angle):
    t, r = number(thickness, "Sac kalınlığı"), number(radius, "İç yarıçap", zero=True)
    a = number(angle, "Büküm açısı")
    if a >= 180:
        raise ValueError("Büküm açısı 0°'den büyük, 180°'den küçük olmalıdır. Tam katlama (180°) desteklenmez.")
    return t, r, math.radians(a)


def bend_allowance(thickness, radius, k_factor, angle=90):
    t, r, a = _geometry(thickness, radius, angle)
    k = number(k_factor, "K faktörü", zero=True)
    if k > 1:
        raise ValueError("ANSI K faktörü 0–1 aralığında olmalı.")
    return a * (r + k * t)


def k_from_bend_allowance(thickness, radius, measured_ba, angle=90):
    """K=(BA/θ−R)/t. BA ayrı bir numuneden ölçülmelidir."""
    t, r, a = _geometry(thickness, radius, angle)
    k = (number(measured_ba, "Ölçülmüş BA") / a - r) / t
    if not math.isfinite(k) or not 0 <= k <= 1:
        raise ValueError("Ölçümden hesaplanan K faktörü 0–1 aralığının dışında. Açıyı, iç yarıçapı, sac kalınlığını ve büküm payını kontrol edin.")
    return k


def bend_deduction(thickness, radius, k_factor, angle=90):
    t, r, a = _geometry(thickness, radius, angle)
    return 2 * (r + t) * math.tan(a / 2) - bend_allowance(t, r, k_factor, angle)


def ba_from_outside_dimensions(thickness, radius, outside_a, outside_b,
                               flat_length, angle=90):
    """Tek büküm: dış sanal kesişime ölçülen A/B ve ölçülen düz boydan BA."""
    t, r, a = _geometry(thickness, radius, angle)
    outside_a, outside_b = number(outside_a, "Dış A"), number(outside_b, "Dış B")
    flat_length = number(flat_length, "Düz boy")
    setback = (r + t) * math.tan(a / 2)
    if min(outside_a, outside_b) <= setback:
        raise ValueError("Dış ölçüler büküm geri çekilmesinden büyük olmalı.")
    ba = flat_length - outside_a - outside_b + 2 * setback
    k_from_bend_allowance(t, r, ba, angle)
    return ba


def material_by_key(key):
    for material in MATERIALS:
        if key == material.key:
            return material
    raise ValueError("Tanımlı bir malzeme seçin.")


def recommended_k(material, thickness, radius):
    t, r, _ = _geometry(thickness, radius, 90)
    ratio = r / t
    return AIR_K[material_by_key(material).hardness][0 if ratio <= 1 else 1 if ratio <= 3 else 2]


@dataclass(frozen=True)
class Recipe:
    material: str = "steel"
    punch_radius_mm: float = 1
    die_opening_mm: float | None = None  # None: catalogue opening nearest 8t
    measured_radius_mm: float | None = None
    angle_deg: float = 90
    calibration_thickness_mm: float | None = None
    measured_ba_mm: float | None = None
    punch_angle_deg: float = 85
    die_angle_deg: float = 85
    all_bends: bool = False

    def validate(self):
        material_by_key(self.material)
        number(self.punch_radius_mm, "Üst bıçak yarıçapı R")
        _geometry(1, 1, self.angle_deg)
        for label, angle in (("Üst bıçak açısı", self.punch_angle_deg),
                             ("Alt kalıp açısı", self.die_angle_deg)):
            _geometry(1, 1, angle)
        if 180 - number(self.angle_deg, "Büküm açısı") < max(
                number(self.punch_angle_deg, "Üst bıçak açısı"),
                number(self.die_angle_deg, "Alt kalıp açısı")):
            raise ValueError("Hedef iç açı seçilen bıçak/kalıp açısından küçük; daha dar açılı takım seçin.")
        if self.die_opening_mm is not None:
            number(self.die_opening_mm, "Alt kalıp V")
        if self.measured_radius_mm is not None:
            number(self.measured_radius_mm, "Ölçülmüş iç R")
        if self.measured_ba_mm is not None:
            number(self.measured_ba_mm, "Ölçülmüş BA")
            number(self.calibration_thickness_mm, "Kalibrasyon kalınlığı")


@dataclass(frozen=True)
class Calculation:
    thickness_mm: float
    die_opening_mm: float
    radius_mm: float
    table_k: float
    k_factor: float
    ba_mm: float
    bd_mm: float
    angle_deg: float
    calibrated: bool
    notes: tuple[str, ...]


class ThicknessMismatch(ValueError):
    """Manuel atamada farklı kalınlığı olan saclar hata değil, atlamadır."""


THICKNESS_MATCH_TOLERANCE_MM = 1e-6


@dataclass(frozen=True)
class ManualAssignment:
    thickness_mm: float
    k_factor: float
    radius_mm: float
    all_bends: bool = False

    def validate(self):
        number(self.thickness_mm, "Hedef sac kalınlığı")
        k = number(self.k_factor, "Manuel K faktörü", zero=True)
        if k > 1:
            raise ValueError("ANSI K faktörü 0–1 aralığında olmalı.")
        number(self.radius_mm, "Manuel büküm yarıçapı")


@dataclass(frozen=True)
class AssignmentTable:
    """Kullanıcının kalınlığa göre verdiği, hesaplama içermeyen K/R satırları."""

    rows: tuple[ManualAssignment, ...]
    all_bends: bool = True

    def __post_init__(self):
        # A frozen dataclass must not retain a caller's mutable list.
        try:
            object.__setattr__(self, "rows", tuple(self.rows))
        except TypeError:
            raise ValueError("En az bir sac kalınlığı, K faktörü ve yarıçap satırı girin.") from None

    def validate(self):
        if not self.rows:
            raise ValueError("En az bir sac kalınlığı, K faktörü ve yarıçap satırı girin.")
        thicknesses = []
        for index, row in enumerate(self.rows, 1):
            if not isinstance(row, ManualAssignment):
                raise ValueError(f"{index}. satır için sac kalınlığı, K faktörü ve yarıçap girin.")
            try:
                row.validate()
            except ValueError as exc:
                raise ValueError(f"{index}. satır: {exc}") from None
            thicknesses.append((number(row.thickness_mm, "Sac kalınlığı"), index))
        thicknesses.sort()
        for (previous, previous_index), (current, current_index) in zip(thicknesses, thicknesses[1:]):
            # Reject overlapping match intervals, even for differently written
            # nominal values: no measured thickness may select two K/R rows.
            if math.isclose(current, previous, rel_tol=0,
                            abs_tol=2 * THICKNESS_MATCH_TOLERANCE_MM):
                raise ValueError(
                    f"{previous_index}. ve {current_index}. satırdaki sac kalınlıkları "
                    "aynı veya eşleştirme sınırında birbirine çok yakın. "
                    "Her kalınlık için tek K/R satırı girin.")


@dataclass(frozen=True)
class ManualCalculation:
    thickness_mm: float
    k_factor: float
    radius_mm: float
    notes: tuple[str, ...] = ("K/R kullanıcı tarafından doğrudan girildi; tablo veya takım tahmini kullanılmadı.",)
    ba_mm: None = None


def calculate(thickness_mm, recipe=Recipe()):
    recipe.validate()
    t = number(thickness_mm, "Sac kalınlığı")
    if isinstance(recipe, AssignmentTable):
        matches = [row for row in recipe.rows if math.isclose(
            t, number(row.thickness_mm, "Hedef sac kalınlığı"), rel_tol=0,
            abs_tol=THICKNESS_MATCH_TOLERANCE_MM)]
        if not matches:
            raise ThicknessMismatch(
                f"Sac kalınlığı {t:.12g} mm; girilen kalınlıklarla eşleşmedi, atlandı.")
        recipe = matches[0]
    if isinstance(recipe, ManualAssignment):
        target = number(recipe.thickness_mm, "Hedef sac kalınlığı")
        # A fixed 1 nm tolerance only absorbs unit-conversion floating error;
        # it must not grow with thickness or merge nominally different sheets.
        if not math.isclose(t, target, rel_tol=0, abs_tol=THICKNESS_MATCH_TOLERANCE_MM):
            raise ThicknessMismatch(f"Sac kalınlığı {t:.12g} mm; hedef {target:.12g} mm ile eşleşmedi, atlandı.")
        return ManualCalculation(t, number(recipe.k_factor, "Manuel K faktörü", zero=True),
                                 number(recipe.radius_mm, "Manuel büküm yarıçapı"))
    material = material_by_key(recipe.material)
    punch = number(recipe.punch_radius_mm, "Üst bıçak yarıçapı R")
    if recipe.die_opening_mm is None:
        candidates = [v for v in DIE_OPENINGS if 6 <= v / t <= 12]
        if not candidates:
            raise ValueError(f"{t:g} mm için katalogda uygun V yok; özel V girin (6–12 × t).")
        v = min(candidates, key=lambda opening: (abs(opening - 8*t), opening))
    else:
        v = number(recipe.die_opening_mm, "Alt kalıp V")
    if not 6 <= v / t <= 12:
        raise ValueError(f"V/t={v/t:g}: genel havada büküm modeli 6–12 × t aralığını destekler. Uygun V seçin.")
    if punch >= v / 2:
        raise ValueError("Üst bıçak yarıçapı R, V açıklığının yarısından küçük olmalı.")
    notes = ["Genel havada büküm önerisi; takım kapasitesi ve malzeme uygunluğunu üretimde kontrol edin."]
    natural_radius = material.air_radius_ratio * v
    r = (number(recipe.measured_radius_mm, "Ölçülmüş iç R")
         if recipe.measured_radius_mm is not None else max(punch, natural_radius))
    if r < punch:
        raise ValueError("Ölçülmüş iç R, seçilen üst bıçak uç R değerinden küçük olamaz.")
    if r >= v / 2:
        raise ValueError("İç R, V açıklığının yarısından küçük olmalı; büyük yarıçap için farklı takım/model gerekir.")
    if recipe.measured_radius_mm is None:
        notes.append(f"R ≈ max(bıçak R, {material.air_radius_ratio:g} × V); ölçülmüş R daha güvenilirdir.")
    if punch > natural_radius:
        notes.append("Yarıçap tahmininde bıçak yarıçapı baskındır; üretim ölçümüyle kontrol edin.")
    table_k = recommended_k(recipe.material, t, r)
    calibrated = recipe.measured_ba_mm is not None
    if calibrated:
        if recipe.measured_radius_mm is None:
            raise ValueError("BA kalibrasyonu için numunenin ölçülmüş iç R değerini de girin.")
        if not math.isclose(t, number(recipe.calibration_thickness_mm, "Kalibrasyon kalınlığı"),
                            rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError("BA kalibrasyonu yalnızca numuneyle aynı kalınlıktaki parçalara uygulanır.")
        k = k_from_bend_allowance(t, r, recipe.measured_ba_mm, recipe.angle_deg)
        notes.append("K, bağımsız BA ölçümünden hesaplandı; aynı malzeme/takım/açı koşulları gerekir.")
    else:
        k = table_k
        notes.append("Büküm payı hesabı tabloya dayalıdır; K faktörünü doğrulamak için üretim ölçümü gerekir.")
    if k > .5:
        notes.append("K > 0.5: ölçüm ve büküm koşulları ayrıca kontrol edilmeli.")
    return Calculation(t, v, r, table_k, k, bend_allowance(t, r, k, recipe.angle_deg),
                       bend_deduction(t, r, k, recipe.angle_deg), recipe.angle_deg,
                       calibrated, tuple(notes))
