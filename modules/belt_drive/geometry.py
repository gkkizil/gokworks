"""One analytic route shared by calculation, future drawing and animation.

Coordinates are millimetres, +Y up. Positive route distance traverses the
upper span driver→driven and turns both pulleys clockwise. No splines/ellipse.
"""

from dataclasses import dataclass
import math

from ._numbers import finite, positive
from .engineering.belt_length import length_metrics
from .models import LengthMetrics


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float

    def __post_init__(self):
        finite(self.x, 'X koordinatı'); finite(self.y, 'Y koordinatı')

    def __add__(self, other):
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, scale):
        return Point(self.x * scale, self.y * scale)

    def dot(self, other):
        return self.x * other.x + self.y * other.y

    @property
    def norm(self):
        return math.hypot(self.x, self.y)


@dataclass(frozen=True, slots=True)
class Line:
    start: Point
    end: Point
    kind: str = 'line'

    @property
    def length_mm(self):
        return (self.end - self.start).norm

    def point(self, fraction):
        return self.start + (self.end - self.start) * fraction

    def tangent(self, fraction=0.):
        return (self.end - self.start) * (1. / positive(self.length_mm, 'Teğet kol uzunluğu'))


@dataclass(frozen=True, slots=True)
class Arc:
    center: Point
    radius_mm: float
    start_rad: float
    sweep_rad: float
    kind: str = 'arc'

    @property
    def length_mm(self):
        return self.radius_mm * abs(self.sweep_rad)

    @property
    def start(self):
        return self.point(0.)

    @property
    def end(self):
        return self.point(1.)

    def point(self, fraction):
        angle = self.start_rad + fraction * self.sweep_rad
        return self.center + Point(math.cos(angle), math.sin(angle)) * self.radius_mm

    def tangent(self, fraction):
        angle = self.start_rad + fraction * self.sweep_rad
        sign = math.copysign(1., self.sweep_rad)
        return Point(-math.sin(angle) * sign, math.cos(angle) * sign)


@dataclass(frozen=True, slots=True)
class BeltPath:
    driver_center: Point
    driven_center: Point
    driver_radius_mm: float
    driven_radius_mm: float
    metrics: LengthMetrics
    segments: tuple[Line | Arc, ...]  # upper, driven arc, lower, driver arc

    @property
    def length_mm(self):
        return math.fsum(segment.length_mm for segment in self.segments)

    @property
    def upper_direction(self):
        return self.segments[0].tangent()

    @property
    def lower_direction(self):
        # Force at the driver points toward the driven on BOTH spans.
        return self.segments[2].tangent() * -1.

    def point_at_distance(self, distance_mm):
        distance = finite(distance_mm, 'Güzergâh mesafesi') % self.length_mm
        for segment in self.segments:
            length = segment.length_mm
            if distance <= length:
                fraction = distance / positive(length, 'Güzergâh parçası')
                return segment.point(fraction)
            distance -= length
        return self.segments[0].start


def open_belt_path(driver_diameter_mm, driven_diameter_mm, center_mm, *, origin=Point(0., 0.), angle_rad=0.):
    metrics = length_metrics(driver_diameter_mm, driven_diameter_mm, center_mm)
    r1, r2 = driver_diameter_mm / 2., driven_diameter_mm / 2.
    if center_mm <= r1 + r2:
        raise ValueError('Referans çemberleri kesişmemeli: C > (D₁ + D₂)/2 gerekli.')
    if not isinstance(origin, Point):
        raise ValueError('Kasnak merkezi Point olmalı.')
    phi = math.remainder(finite(angle_rad, 'Eksen açısı'), 2. * math.pi)
    c1 = origin
    c2 = origin + Point(math.cos(phi), math.sin(phi)) * center_mm
    upper = phi + math.pi / 2. + metrics.alpha_rad
    lower = phi - math.pi / 2. - metrics.alpha_rad
    n1, n2 = Point(math.cos(upper), math.sin(upper)), Point(math.cos(lower), math.sin(lower))
    segments = (Line(c1 + n1 * r1, c2 + n1 * r2), Arc(c2, r2, upper, -metrics.driven_wrap_rad),
                Line(c2 + n2 * r2, c1 + n2 * r1), Arc(c1, r1, lower, -metrics.driver_wrap_rad))
    path = BeltPath(c1, c2, r1, r2, metrics, segments)
    positive(path.length_mm, 'Güzergâh uzunluğu')
    if not math.isclose(path.length_mm, metrics.exact_mm, rel_tol=1e-11, abs_tol=1e-9):
        raise ValueError('Koordinatlar geometrik hassasiyet için çok büyük; düzeni orijine yaklaştırın.')
    return path


def path_between_centers(driver_diameter_mm, driven_diameter_mm, driver_center, driven_center):
    offset = driven_center - driver_center
    return open_belt_path(driver_diameter_mm, driven_diameter_mm, offset.norm, origin=driver_center,
                          angle_rad=math.atan2(offset.y, offset.x))
