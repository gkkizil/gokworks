"""Bend-zone lengths for explicit shop inputs, independent of fitting developments.

Adapted from hermes98761234/sheet-metal-unfold, src/lib/bend.ts,
commit 2ad13f96ba83fb0e20a7b0c7f3bc201b8ef1b540 (MIT).
Copyright (c) 2026 Volodymyr Kopytsia. Full notice:
packaging/licenses/unfolding/sheet-metal-unfold-MIT.txt.

Python adaptation adds immutable results, per-bend radii/K, strict domains and
rejection of impossible tangent lengths. No generic material K table is used.
These helpers do not silently change the geometric mid-surface of any fitting.
"""
from dataclasses import dataclass
import math

from .geometry import bend_allowance


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{name}: sonlu sayı gerekli.')
    return float(value)


@dataclass(frozen=True)
class BendInput:
    """Signed turn in degrees; radius and thickness are always inside dimensions.

    Positive/negative turn preserves the caller's up/down convention. K is the
    neutral-axis distance from the inside divided by thickness (ANSI convention).
    """
    angle_deg: float
    inside_radius_mm: float
    k_factor: float


@dataclass(frozen=True)
class BendZone:
    angle_deg: float
    inside_radius_mm: float
    k_factor: float
    allowance_mm: float
    deduction_mm: float
    outside_setback_mm: float
    inside_setback_mm: float
    start_mm: float
    end_mm: float
    line_at_mm: float


@dataclass(frozen=True)
class FlatProfile:
    straight_lengths_mm: tuple[float, ...]
    bends: tuple[BendZone, ...]
    flat_length_mm: float
    entered_length_mm: float
    total_deduction_mm: float
    dimension_reference: str
    production_process_verified: bool = False


def develop_profile(lengths_mm, bends, thickness_mm, *, dimension_reference):
    """Unfold consecutive flanges using outside/inside virtual-sharp or tangent lengths.

    One bend is required between each pair of flanges. The bend line is at the
    centre of its neutral-axis arc. This returns a 1D development, not an arbitrary
    B-Rep unfolder, a collision check, or press-brake/process approval.
    """
    if dimension_reference not in ('outside', 'inside', 'tangent'):
        raise ValueError('Ölçü türü outside, inside veya tangent olmalı.')
    thickness = _finite(thickness_mm, 'Kalınlık')
    if thickness <= 0:
        raise ValueError('Kalınlık pozitif olmalı.')
    lengths = tuple(_finite(v, 'Flanş boyu') for v in lengths_mm)
    bends = tuple(bends)
    if not lengths or any(v <= 0 for v in lengths) or len(bends) != len(lengths)-1:
        raise ValueError('Pozitif flanş boyları ve her birleşimde bir büküm gerekli.')
    values = []
    for bend in bends:
        if not isinstance(bend, BendInput):
            raise ValueError('Bükümler BendInput olmalı.')
        allowance = bend_allowance(bend.angle_deg, bend.inside_radius_mm, thickness, bend.k_factor)
        tangent = math.tan(abs(math.radians(bend.angle_deg))/2)
        outer = tangent*(bend.inside_radius_mm+thickness)
        inner = tangent*bend.inside_radius_mm
        values.append((allowance, outer, inner))
    setbacks = [v[1] if dimension_reference == 'outside' else v[2]
                if dimension_reference == 'inside' else 0. for v in values]
    straights = tuple(length-(setbacks[i-1] if i else 0.)
                      -(setbacks[i] if i < len(bends) else 0.) for i, length in enumerate(lengths))
    if any(not math.isfinite(v) or v < -1e-9 for v in straights):
        raise ValueError('Flanş boyu komşu bükümlerin teğet mesafelerine yetmiyor.')
    straights = tuple(max(0., v) for v in straights)
    zones = []
    position = 0.
    for i, length in enumerate(straights):
        position += length
        if i < len(bends):
            bend = bends[i]
            allowance, outer, inner = values[i]
            zones.append(BendZone(bend.angle_deg, bend.inside_radius_mm, bend.k_factor,
                                  allowance, 2*outer-allowance, outer, inner,
                                  position, position+allowance, position+allowance/2))
            position += allowance
    entered = math.fsum(lengths)
    if not math.isfinite(position) or not math.isfinite(entered):
        raise ValueError('Büküm hesabı sayısal aralığı aştı.')
    return FlatProfile(straights, tuple(zones), position, entered, entered-position,
                       dimension_reference)


def calibrate_k(outside_first_mm, outside_second_mm, measured_flat_mm,
                angle_deg, inside_radius_mm, thickness_mm):
    """Recover K from a measured single-bend coupon, never a material default.

    Both flange lengths must reach the outside virtual sharp; angle is the turn
    from straight, not the included angle. One test does not validate other
    materials, thicknesses, radii, grain directions or forming processes.
    """
    # Validate the bend domain without introducing an assumed material K.
    bend_allowance(angle_deg, inside_radius_mm, thickness_mm, 0.)
    first = _finite(outside_first_mm, 'Birinci dış boy')
    second = _finite(outside_second_mm, 'İkinci dış boy')
    flat = _finite(measured_flat_mm, 'Ölçülen açınım boyu')
    angle = abs(math.radians(angle_deg))
    setback = math.tan(angle/2)*(inside_radius_mm+thickness_mm)
    if min(first, second, flat) <= 0 or min(first, second) < setback:
        raise ValueError('Numune boyları pozitif ve dış teğet mesafesinden büyük olmalı.')
    allowance = flat-(first-setback)-(second-setback)
    k = (allowance/angle-inside_radius_mm)/thickness_mm
    if not math.isfinite(k) or not 0 <= k <= 1:
        raise ValueError('Numune K∈[0,1] vermiyor; ölçü türünü, açıyı ve numuneyi kontrol edin.')
    return k
