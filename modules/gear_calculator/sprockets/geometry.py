"""Circular roller seats and tangent convex flanks, never an involute.

Independent analytic circle construction; no third-party implementation copied.
The root radius is Rp-ri, retaining the explicit roller seating clearance.
"""
from dataclasses import dataclass
from functools import lru_cache
from math import acos,atan2,ceil,cos,hypot,pi,radians,sin
from .calculation import calculate,dimensions,validate_sprocket
from ..geometry import rotate


@dataclass(frozen=True)
class Arc:
    center: tuple[float,float]
    radius: float
    start: float
    end: float
    tooth: int
    role: str

    def point(self,u):
        a=self.start+(self.end-self.start)*u
        return (self.center[0]+self.radius*cos(a),self.center[1]+self.radius*sin(a))

    def sampled(self,tolerance):
        if not 1e-6<=tolerance<=.1:raise ValueError('Profil toleransı 0,000001–0,1 mm olmalı.')
        step=2*acos(max(-1.,1-min(tolerance/self.radius,1.)))
        n=max(1,ceil(abs(self.end-self.start)/step))
        return tuple(self.point(i/n) for i in range(n+1))

    def contains_angle(self,a):
        delta=(a-self.start)%(2*pi) if self.end>=self.start else (self.start-a)%(2*pi)
        return delta<=abs(self.end-self.start)+1e-12

    def distance(self,p):
        d=(p[0]-self.center[0],p[1]-self.center[1]);a=atan2(d[1],d[0])
        if self.contains_angle(a):return abs(hypot(*d)-self.radius)
        return min(hypot(p[0]-q[0],p[1]-q[1]) for q in (self.point(0),self.point(1)))


@lru_cache(maxsize=32)
def profile(s):
    validate_sprocket(s);g=dimensions(s);r=g.pitch_diameter_mm/2
    ri,re=g.seat_radius_mm,g.flank_radius_mm;half=radians(g.seat_angle_deg/2);pitch=2*pi/s.teeth
    fc=(r-(ri+re)*cos(half),(ri+re)*sin(half));d=hypot(*fc);ra=g.outside_diameter_mm/2
    value=(ra*ra-d*d-re*re)/(2*d*re)
    if not -1<=value<=1:raise ValueError('Yanak yayı diş üstü dairesiyle kesişmiyor.')
    beta=atan2(fc[1],fc[0])-acos(value)
    tip=(fc[0]+re*cos(beta),fc[1]+re*sin(beta));psi=atan2(tip[1],tip[0])
    if not -half<beta<pi or not 0<psi<pitch/2:
        raise ValueError('Diş tepesi sivriliyor veya komşu yanaklar çakışıyor.')
    template=(Arc((r,0),ri,pi+half,pi-half,0,'seat'),
        Arc(fc,re,-half,beta,0,'flank'),Arc((0.,0.),ra,psi,pitch-psi,0,'tip'),
        Arc(rotate((fc[0],-fc[1]),pitch),re,pitch-beta,pitch+half,0,'flank'))
    arcs=tuple(Arc(rotate(a.center,j*pitch),a.radius,a.start+j*pitch,a.end+j*pitch,j,a.role)
        for j in range(s.teeth) for a in template)
    for a,b in zip(arcs,arcs[1:]+arcs[:1]):
        if hypot(*(x-y for x,y in zip(a.point(1),b.point(0))))>1e-8:
            raise ValueError('Zincir dişi yayları kesintisiz kapalı kontur oluşturmuyor.')
    return arcs


def points(s,tolerance=.001):
    result=[]
    for arc in profile(s):result.extend(arc.sampled(tolerance) if not result else arc.sampled(tolerance)[1:])
    result[-1]=result[0];return tuple(result)


def polygon(s,tolerance=.001,bore=True):
    from shapely.geometry import Polygon,Point
    holes=[Point(0,0).buffer(s.bore_mm/2,quad_segs=128).exterior.coords] if bore and s.bore_mm else []
    p=Polygon(points(s,tolerance),holes)
    if not p.is_valid or p.area<=0:raise ValueError('Zincir dişi konturu kendini kesiyor veya alanı geçersiz.')
    return p


def poses(s,angle=0.):
    r=calculate(s)
    return ((0,angle,0.,0.),(1,angle*s.driver.teeth/s.driven.teeth,r.corrected_center_mm,0.))


def chain_route(s):
    """Continuous pitch-circle reference only; not a discrete roller-chain solver."""
    r=calculate(s);r1=r.driver.pitch_diameter_mm/2;r2=r.driven.pitch_diameter_mm/2;C=r.corrected_center_mm
    nx=(r1-r2)/C;ny=(1-nx*nx)**.5
    return ((r1*nx,r1*ny),(C+r2*nx,r2*ny),(C+r2*nx,-r2*ny),(r1*nx,-r1*ny))


@lru_cache(maxsize=16)
def verify(s,samples=64):
    """Exact arc clearance at sampled roller release positions, plus topology.
    Rotational symmetry reduces each wheel to one link articulation interval.
    This does not certify loaded contact, wear, side relief or moving-chain physics.
    """
    if type(samples) is not int or not 16<=samples<=256:raise ValueError('Geometri örnek sayısı 16–256 olmalı.')
    result=calculate(s);minimum=float('inf')
    for wheel in (s.driver,s.driven):
        arcs=profile(wheel);p=polygon(wheel,.0005,bore=False)
        r=dimensions(wheel).pitch_diameter_mm/2;c=wheel.chain
        for j in range(samples+1):
            a=(pi/2+pi/wheel.teeth)*(1-j/samples)
            center=(r+c.pitch_mm*cos(a),c.pitch_mm*sin(a))
            from shapely.geometry import Point
            if p.contains(Point(*center)):raise ValueError('Makara merkezi profilin içine giriyor.')
            clearance=min(arc.distance(center) for arc in arcs)-c.roller_diameter_mm/2
            minimum=min(minimum,clearance)
        if minimum < -1e-7:raise ValueError(f'Makara giriş/çıkış taramasında girişim: {-minimum:.6g} mm.')
    return dict(samples=samples+1,minimum_roller_clearance_mm=minimum,
        center_distance_mm=result.corrected_center_mm,profile_reference=s.driver.profile_reference,
        manufacturing_approved=False,chain_motion_verified=False)
