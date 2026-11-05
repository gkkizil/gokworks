"""Millimetre curves, topology checks and exact planar measurements."""
import math
from .models import Line2D, Arc2D, Circle2D, Polyline2D, Geometry2D, PartMetrics


def arc_point(arc, angle_deg):
    a = math.radians(angle_deg)
    # Stable coordinates for a shallow cone sector translated near the origin.
    x = -2*arc.radius*math.sin(a/2)**2 if arc.center[0] == -arc.radius else arc.center[0]+arc.radius*math.cos(a)
    return x, arc.center[1]+arc.radius*math.sin(a)


def sample_count(radius, span_rad, tolerance, maximum=4096):
    if radius <= 0 or tolerance <= 0: raise ValueError('Yarıçap ve kord hata sınırı pozitif olmalı.')
    step = 2*math.acos(max(-1., 1-tolerance/radius)) if tolerance < radius else math.pi
    count = max(1, math.ceil(abs(span_rad)/max(step, 1e-12)))
    if count > maximum: raise ValueError('İstenen eğri hatası örnekleme üst sınırını aşıyor.')
    return count


def curve_points(curve, tolerance=.02, maximum=4096):
    if isinstance(curve, Line2D): return (curve.start, curve.end)
    if isinstance(curve, Polyline2D): return curve.points + ((curve.points[0],) if curve.closed else ())
    if isinstance(curve, Circle2D):
        curve = Arc2D(curve.center, curve.radius, 0., 360.)
    n = sample_count(curve.radius, math.radians(curve.sweep_deg), tolerance, maximum)
    return tuple(arc_point(curve, curve.start_angle_deg+curve.sweep_deg*i/n) for i in range(n+1))


def contour_points(contour, tolerance=.02, maximum=4096):
    points = []
    for curve in contour:
        p = curve_points(curve, tolerance, maximum)
        if points and math.dist(points[-1], p[0]) > 1e-5:
            raise ValueError('Kontur elemanları uç uca bağlanmıyor.')
        points.extend(p if not points else p[1:])
    if len(points) < 4 or math.dist(points[-1], points[0]) > 1e-5:
        raise ValueError('Kesim konturu kapalı değil.')
    return tuple(points[:-1])


def curve_length(curve):
    if isinstance(curve, Line2D): return math.dist(curve.start, curve.end)
    if isinstance(curve, Circle2D): return 2*math.pi*curve.radius
    if isinstance(curve, Arc2D): return curve.radius*abs(math.radians(curve.sweep_deg))
    p = curve.points + ((curve.points[0],) if curve.closed else ())
    return sum(math.dist(a, b) for a, b in zip(p, p[1:]))


def _theta_minus_sin(theta):
    if abs(theta) > .01: return theta-math.sin(theta)
    return theta**3*(1/6-theta**2/120+theta**4/5040-theta**6/362880)


def contour_area(contour):
    ends = []; corrections = []
    for curve in contour:
        if isinstance(curve, Circle2D): return math.pi*curve.radius**2
        if isinstance(curve, Arc2D):
            ends.extend((arc_point(curve, curve.start_angle_deg), arc_point(curve, curve.start_angle_deg+curve.sweep_deg)))
            corrections.append(.5*curve.radius**2*_theta_minus_sin(math.radians(curve.sweep_deg)))
        elif isinstance(curve, Line2D): ends.extend((curve.start, curve.end))
        else: ends.extend(curve.points+((curve.points[0],) if curve.closed else ()))
    # Translate to reduce cancellation for layouts away from the origin.
    x0, y0 = ends[0]
    p = [(x-x0, y-y0) for x, y in ends]
    return .5*math.fsum(a[0]*b[1]-b[0]*a[1] for a, b in zip(p, p[1:]+p[:1]))+math.fsum(corrections)


def contour_bounds(contour):
    points = []
    for c in contour:
        if isinstance(c, Circle2D): points.extend(((c.center[0]-c.radius,c.center[1]-c.radius),(c.center[0]+c.radius,c.center[1]+c.radius)))
        elif isinstance(c, Arc2D):
            angles=[c.start_angle_deg,c.start_angle_deg+c.sweep_deg]
            for angle in (0.,90.,180.,270.):
                delta=(angle-c.start_angle_deg)%360 if c.sweep_deg>0 else (c.start_angle_deg-angle)%360
                if delta<=abs(c.sweep_deg): angles.append(angle)
            points.extend(arc_point(c,a) for a in angles)
        elif isinstance(c, Line2D): points.extend((c.start,c.end))
        else: points.extend(c.points)
    return min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points)


def polygon(geometry, tolerance=.02, maximum=4096):
    from shapely.geometry import Polygon
    outer=contour_points(geometry.outer,tolerance,maximum)
    holes=[contour_points(h,tolerance,maximum) for h in geometry.holes]
    p=Polygon(outer,holes)
    if not p.is_valid or p.is_empty or p.area<=0:
        raise ValueError('Kontur kendini kesiyor, dejenere veya delikler dış konturla çakışıyor.')
    return p


def measure(geometry, net_area, thickness, material, tolerance=.02, maximum=4096):
    polygon(geometry,tolerance,maximum)
    if contour_area(geometry.outer)<=0 or any(contour_area(h)>=0 and not (len(h)==1 and isinstance(h[0],Circle2D)) for h in geometry.holes):
        raise ValueError('Dış kontur CCW, delikler CW yönünde olmalı.')
    area=contour_area(geometry.outer)-sum(abs(contour_area(h)) for h in geometry.holes)
    bounds=contour_bounds(geometry.outer)
    length=sum(curve_length(c) for ring in (geometry.outer,*geometry.holes) for c in ring)
    mass=area*thickness*1e-9*material.density_kg_m3 if thickness>0 and material.density_kg_m3 is not None else None
    price=None
    if material.unit_price is not None:
        amount=mass if material.price_unit=='kg' else area/1e6 if material.price_unit=='m2' else length/1000
        if amount is not None: price=amount*material.unit_price
    return PartMetrics(net_area,area,(bounds[2]-bounds[0])*(bounds[3]-bounds[1]),length,bounds,mass,price)


def outline(points):
    return Geometry2D((Polyline2D(tuple(points),True),))


def bend_allowance(angle_deg, inside_radius_mm, thickness_mm, k_factor):
    values=(angle_deg,inside_radius_mm,thickness_mm,k_factor)
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in values): raise ValueError('Sonlu sayılar gerekli.')
    if not 0<abs(angle_deg)<180 or inside_radius_mm<0 or thickness_mm<=0 or not 0<=k_factor<=1:
        raise ValueError('Açı (0,180), R≥0, t>0 ve kullanıcı K∈[0,1] gerekli.')
    return abs(math.radians(angle_deg))*(inside_radius_mm+k_factor*thickness_mm)
