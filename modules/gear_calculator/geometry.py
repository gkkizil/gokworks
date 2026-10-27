"""Analytic involutes, bounded cubic approximation, exact tip/root circle arcs.

The root below the base circle is a radial straight connector, NOT a generated
trochoid or a manufacturing fillet. All consumers share these segments.
"""

from dataclasses import dataclass
from functools import lru_cache
from math import acos, atan, ceil, cos, hypot, pi, radians, sin, sqrt, tan
from .calculation import calculate_gear, calculate_pair
from .validation import require_manufacturable

Point = tuple[float, float]


def rotate(p, angle, center=(0.,0.)):
    c,s=cos(angle),sin(angle)
    return (p[0]*c-p[1]*s+center[0],p[0]*s+p[1]*c+center[1])


def involute(base_radius, t):
    return (base_radius*(cos(t)+t*sin(t)),base_radius*(sin(t)-t*cos(t)))


def involute_derivative(base_radius, t):
    return (base_radius*t*cos(t),base_radius*t*sin(t))


def _blend(a,b,u):
    return (a[0]*(1-u)+b[0]*u,a[1]*(1-u)+b[1]*u)


@dataclass(frozen=True)
class Segment:
    kind: str
    controls: tuple[Point, ...] = ()
    radius: float = 0.
    start_angle: float = 0.
    end_angle: float = 0.
    tooth: int = 0

    def point(self,u):
        if self.kind=='arc':
            a=self.start_angle+(self.end_angle-self.start_angle)*u
            return (self.radius*cos(a),self.radius*sin(a))
        points=self.controls
        while len(points)>1:
            points=tuple(_blend(a,b,u) for a,b in zip(points,points[1:]))
        return points[0]

    def sampled(self,tolerance):
        if self.kind=='line':
            return self.controls
        if self.kind=='arc':
            step=2*acos(max(-1.,1-min(tolerance/self.radius,1.)))
            n=max(1,ceil(abs(self.end_angle-self.start_angle)/step))
        else:
            p=self.controls
            second=max(hypot(p[i+2][0]-2*p[i+1][0]+p[i][0],
                             p[i+2][1]-2*p[i+1][1]+p[i][1]) for i in (0,1))*6
            n=max(1,ceil(sqrt(second/(8*tolerance))))
        return tuple(self.point(i/n) for i in range(n+1))


@dataclass(frozen=True)
class GearProfile:
    specification: object
    segments: tuple[Segment, ...]
    curve_tolerance_mm: float

    def points(self, tolerance_mm):
        if not .000001<=tolerance_mm<=1:
            raise ValueError('Kontur toleransı 0,000001–1 mm aralığında olmalı.')
        points=[]
        for segment in self.segments:
            samples=segment.sampled(tolerance_mm)
            points.extend(samples if not points else samples[1:])
        # Exact closure also removes trigonometric round-off on the final root arc.
        points[-1]=points[0]
        return tuple(points)


def cad_tolerance(spec):
    return min(.001,spec.module_mm/2000)


@lru_cache(maxsize=16)
def gear_profile(spec):
    g=calculate_gear(spec)
    rb,ra,rf=g.base_radius_mm,g.outside_radius_mm,g.root_radius_mm
    alpha=radians(spec.pressure_angle_deg)
    t0=sqrt(max(0.,(rf/rb)**2-1));t1=sqrt((ra/rb)**2-1)
    delta=pi/(2*spec.teeth)+tan(alpha)-alpha
    tip_angle=delta-(t1-atan(t1))
    if tip_angle<=0:
        raise ValueError('Diş üstü kalınlığı pozitif değil; bu profil üretilemiyor.')
    root_angle=delta-(t0-atan(t0))
    tolerance=cad_tolerance(spec)
    # Cubic Hermite error <= h^4/384 * max ||f''''||.
    # Here ||f''''(t)|| = rb*sqrt(9+t^2), so this is a conservative vector bound.
    n=max(1,ceil((t1-t0)*(rb*sqrt(9+t1*t1)/(384*tolerance))**.25))
    template=[]
    if rf<rb:
        template.append(Segment('line',((rf*cos(delta),-rf*sin(delta)),rotate(involute(rb,t0),-delta))))
    flanks=[]
    for j in range(n):
        a=t0+(t1-t0)*j/n;b=t0+(t1-t0)*(j+1)/n;h=b-a
        p0,p3=involute(rb,a),involute(rb,b)
        d0,d1=involute_derivative(rb,a),involute_derivative(rb,b)
        controls=(p0,(p0[0]+h*d0[0]/3,p0[1]+h*d0[1]/3),
                  (p3[0]-h*d1[0]/3,p3[1]-h*d1[1]/3),p3)
        flank=Segment('bezier',tuple(rotate(p,-delta) for p in controls))
        flanks.append(flank)
    template.extend(flanks)
    template.append(Segment('arc',radius=ra,start_angle=-tip_angle,end_angle=tip_angle))
    for flank in reversed(flanks):
        template.append(Segment('bezier',tuple((p[0],-p[1]) for p in reversed(flank.controls))))
    if rf<rb:
        template.append(Segment('line',((rb*cos(delta),rb*sin(delta)),(rf*cos(delta),rf*sin(delta)))))
    template.append(Segment('arc',radius=rf,start_angle=root_angle,end_angle=2*pi/spec.teeth-root_angle))
    segments=[]
    for tooth in range(spec.teeth):
        a=2*pi*tooth/spec.teeth
        for s in template:
            segments.append(Segment(s.kind,tuple(rotate(p,a) for p in s.controls),s.radius,
                                    s.start_angle+a,s.end_angle+a,tooth))
    return GearProfile(spec,tuple(segments),tolerance)


def pair_angles(spec, input_angle_rad=0.):
    """Gear 1 has a tooth towards +X; gear 2 has a gap towards -X."""
    return (input_angle_rad,pi-pi/spec.wheel.teeth-input_angle_rad*spec.pinion.teeth/spec.wheel.teeth)


def polygon(spec,tolerance_mm=None):
    from shapely.geometry import Polygon
    profile=gear_profile(spec)
    points=profile.points(tolerance_mm or min(.002,spec.module_mm*.001))
    p=Polygon(points)
    if not p.is_valid or p.area<=0:
        raise ValueError('Dişli konturu kapalı, basit ve pozitif alanlı değil.')
    return p


@dataclass(frozen=True)
class MeshCheck:
    samples: int
    maximum_overlap_mm2: float
    overlap_tolerance_mm2: float


@lru_cache(maxsize=12)
def verify_mesh(spec, samples=48):
    """Sweep one entire tooth pitch; analytic contact limits checked separately.

    Polygon intersections are a numerical screening, not proof of loaded contact.
    Absolute area tolerance scales as m² and accommodates bounded curve/chord error.
    """
    from shapely.affinity import rotate as shape_rotate,translate
    result=calculate_pair(spec);require_manufacturable(result)
    if type(samples) is not int or not 16<=samples<=240:
        raise ValueError('Kavraşma taraması 16–240 örnek gerektirir.')
    m=spec.pinion.module_mm
    p1,p2=polygon(spec.pinion,min(.0005,m*.00025)),polygon(spec.wheel,min(.0005,m*.00025))
    maximum=0.
    for i in range(samples):
        a,b=pair_angles(spec,2*pi/spec.pinion.teeth*i/samples)
        a1=shape_rotate(p1,a,origin=(0,0),use_radians=True)
        a2=translate(shape_rotate(p2,b,origin=(0,0),use_radians=True),xoff=result.center_distance_mm)
        maximum=max(maximum,a1.intersection(a2).area)
    allowed=m*m*2e-5
    if maximum>allowed:
        raise ValueError(f'Diş girişimi bulundu: {maximum:.6g} mm²; sınır {allowed:.6g} mm².')
    return MeshCheck(samples,maximum,allowed)
