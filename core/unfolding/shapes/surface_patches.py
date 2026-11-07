"""Authoritative analytic surface trims, independent of the display mesh."""
import math

from ..models import FrozenMap, SurfacePatch
from ..geometry import polygon
from .common import add, sub, mul, dot


def round_patches(outer, holes=(), *, radius, slope=0., skew=(0.,0.),
                  origin=(0.,0.,0.), axis=(0.,0.,1.),
                  radial_x=(1.,0.,0.), radial_y=(0.,1.,0.)):
    """Trim a circular cylinder/cone or an exact ruled, offset-circle surface.

    Boundary points come from the intersection equations, never preview
    triangles. Angular unwrapping preserves both sides of the physical seam.
    """
    def coordinates(ring):
        out=[]
        for _, point in ring:
            local=sub(point,origin);z=dot(local,axis)
            angle=math.atan2(dot(local,radial_y)-skew[1]*z,
                             dot(local,radial_x)-skew[0]*z)
            if out:angle+=math.tau*round((out[-1][0]-angle)/math.tau)
            out.append((angle,z))
        return out
    boundary=coordinates(outer);internal=[coordinates(h) for h in holes]
    center=(min(t for t,z in boundary)+max(t for t,z in boundary))/2
    for ring in internal:
        shift=math.tau*round((center-sum(t for t,z in ring)/len(ring))/math.tau)
        ring[:]=[(t+shift,z) for t,z in ring]
    data=dict(origin=origin,axis=axis,radial_x=radial_x,radius=radius)
    if any(skew):
        # A rational quadratic circle, swept linearly between circular sections,
        # exactly represents oblique cones and oblique circular cylinders.
        theta0=min(t for t,z in boundary)
        def uv(q):
            angle=max(0.,min(math.tau,q[0]-theta0));quadrant=min(3,math.floor(angle/(math.pi/2)))
            half=math.tan((angle-quadrant*math.pi/2)/2);w=math.sqrt(.5)
            return quadrant+half/(w+half*(1-w)),q[1]
        data.update(slope=slope,skew=skew,theta0=theta0,
                    zmin=min(z for t,z in boundary),zmax=max(z for t,z in boundary))
        kind='trimmed_ruled_round'
    else:
        scale=math.hypot(1.,slope)
        uv=lambda q:(q[0],q[1]*scale)
        kind='trimmed_cone' if slope else 'trimmed_cylinder'
        if slope:data['semi_angle']=math.atan(slope)
    data.update(outer=[uv(q) for q in boundary],holes=[[uv(q) for q in h] for h in internal])
    return (SurfacePatch(kind,FrozenMap(data)),)


def extrusion_patches(profile, geometry, start=0., *, origin=(0.,0.,0.), axis=(0.,0.,1.),
                      radial_x=(1.,0.,0.), radial_y=(0.,1.,0.)):
    """Clip a developed contour at exact generating-curve boundaries."""
    from shapely.geometry import box
    if not profile.cad_segments:return ()
    poly=polygon(geometry);xmin,ymin,xmax,ymax=poly.bounds
    first=math.floor((start+xmin)/profile.perimeter)-1
    last=math.ceil((start+xmax)/profile.perimeter)+1
    out=[]
    for period in range(first,last+1):
        for segment in profile.cad_segments:
            a=segment.start_mm+period*profile.perimeter-start
            b=segment.end_mm+period*profile.perimeter-start
            if b<=xmin+1e-10 or a>=xmax-1e-10:continue
            piece=poly.intersection(box(a,ymin-1.,b,ymax+1.))
            if piece.is_empty:continue
            pieces=(piece,) if piece.geom_type=='Polygon' else getattr(piece,'geoms',())
            for area in pieces:
                if area.geom_type!='Polygon' or area.area<=1e-10:continue
                rings=[tuple(r.coords)[:-1] for r in (area.exterior,*area.interiors)]
                if segment.kind=='arc':
                    center=add(origin,add(mul(radial_x,segment.center[0]),mul(radial_y,segment.center[1])))
                    uv=lambda q:(segment.start_angle+(q[0]-a)/segment.radius_mm,q[1])
                    out.append(SurfacePatch('trimmed_cylinder',FrozenMap(dict(
                        origin=center,axis=axis,radial_x=radial_x,radius=segment.radius_mm,
                        outer=[uv(q) for q in rings[0]],holes=[[uv(q) for q in h] for h in rings[1:]]))))
                else:
                    def point(q):
                        f=(q[0]-a)/(b-a)
                        x,y=(v+f*(w-v) for v,w in zip(segment.start,segment.end))
                        return add(origin,add(add(mul(radial_x,x),mul(radial_y,y)),mul(axis,q[1])))
                    out.append(SurfacePatch('planar_3d',FrozenMap(dict(
                        outer=[point(q) for q in rings[0]],holes=[[point(q) for q in h] for h in rings[1:]]))))
    return tuple(out)
