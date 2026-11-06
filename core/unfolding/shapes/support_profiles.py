"""Convex sections parameterised by matching outward normals and actual flats.

A flat section edge is an interval of support points at one normal. Matching
that interval to a point on a round section creates a real triangular fan;
matching perimeter percentages instead would twist corners and side walls.
"""
from dataclasses import dataclass
import math
from .common import add,sub,mul,dot,norm
from .development import Profile,unit


@dataclass(frozen=True)
class SupportSection:
    centers: tuple
    radius: float=0.
    ellipse_axes: tuple=()
    kind: str='polygon'

    @property
    def flat_angles(self):
        if self.ellipse_axes or len(self.centers)<2:return ()
        out=[]
        for a,b in zip(self.centers,self.centers[1:]+self.centers[:1]):
            d=sub(b,a)
            if norm(d)>1e-9:out.append(math.atan2(-d[0],d[1])%math.tau)
        return tuple(out)

    def point(self,theta,side=0):
        n=(math.cos(theta),math.sin(theta))
        if self.ellipse_axes:
            a,b=self.ellipse_axes;den=math.hypot(a*n[0],b*n[1])
            return a*a*n[0]/den,b*b*n[1]/den
        values=[dot(v,n) for v in self.centers];maximum=max(values)
        if side:
            tolerance=1e-12*max(1.,max(norm(v) for v in self.centers));tangent=(-n[1],n[0])
            tied=[v for v,value in zip(self.centers,values) if maximum-value<=tolerance]
            center=(min if side<0 else max)(tied,key=lambda v:dot(v,tangent))
        else:center=self.centers[values.index(maximum)]
        return add(center,mul(n,self.radius))


def round_section(d):
    if d<=0:raise ValueError('Çap pozitif olmalı.')
    return SupportSection(((0.,0.),),d/2,kind='circle')


def oval_section(length,width):
    if not length>=width>0:raise ValueError('Oval boyu ≥ genişliği > 0 olmalı.')
    a=(length-width)/2
    return SupportSection(((-a,0.),(a,0.)) if a else ((0.,0.),),width/2,kind='stadium')


def ellipse_section(length,width):
    if min(length,width)<=0:raise ValueError('Elips eksenleri pozitif olmalı.')
    return SupportSection((),ellipse_axes=(length/2,width/2),kind='ellipse')


def polygon_section(points,radius=0.):
    if radius<0:raise ValueError('Köşe yarıçapı negatif olamaz.')
    points=list(points)
    area=sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(points,points[1:]+points[:1]))
    if area<0:points.reverse()
    centers=[];tangents=[]
    for i,b in enumerate(points):
        a,c=points[i-1],points[(i+1)%len(points)];u=unit(sub(a,b));v=unit(sub(c,b))
        turn=(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
        if turn<=0:raise ValueError('Geçiş kesiti dışbükey ve köşe sırası tutarlı olmalı.')
        angle=math.acos(max(-1.,min(1.,dot(u,v))));tangent=radius/math.tan(angle/2);tangents.append(tangent)
        center=add(b,mul(unit(add(u,v)),radius/math.sin(angle/2))) if radius else tuple(b)
        centers.append(center)
    for i,a in enumerate(points):
        if tangents[i]+tangents[(i+1)%len(points)]>math.dist(a,points[(i+1)%len(points)])+1e-8:
            raise ValueError('Köşe yarıçapları aynı kenarda birbirini geçiyor.')
    unique=[]
    for center in centers:
        if not unique or math.dist(unique[-1],center)>1e-8:unique.append(center)
    if len(unique)>1 and math.dist(unique[0],unique[-1])<=1e-8:unique.pop()
    return SupportSection(tuple(unique),radius)


def rectangular_section(width,length,radius=0.):
    if min(width,length)<=0:raise ValueError('Dikdörtgen ölçüleri pozitif olmalı.')
    return polygon_section([(-length/2,-width/2),(length/2,-width/2),(length/2,width/2),(-length/2,width/2)],radius)


def matched_profiles(a,b):
    angles=[]
    for angle in sorted((0.,math.pi/2,math.pi,3*math.pi/2,*a.flat_angles,*b.flat_angles)):
        if not angles or angle-angles[-1]>1e-10:angles.append(angle)
    if angles[-1]>math.tau-1e-10:angles.pop()
    features=[];normal_locations={};flat_locations=[];curve_locations=[]
    def is_flat(section,angle):return any(abs(math.remainder(angle-v,math.tau))<1e-10 for v in section.flat_angles)
    for i,angle in enumerate(angles):
        normal_locations[angle]=len(features)
        if is_flat(a,angle) or is_flat(b,angle):
            if is_flat(a,angle):flat_locations.append(len(features)+.5)
            features.append(('flat',angle,angle))
        curve_locations.append(len(features)+.5)
        end=angles[i+1] if i+1<len(angles) else math.tau
        features.append(('curve',angle,end))
    extent=len(features)
    def wrap(section):
        def point(u):
            u%=extent;index=min(extent-1,int(u));f=u-index;kind,start,end=features[index]
            if kind=='flat':
                p,q=section.point(start,-1),section.point(start,1)
                return tuple(x+(y-x)*f for x,y in zip(p,q))
            theta=start+(end-start)*f
            return section.point(theta,1 if f==0 else -1 if f==1 else 0)
        flats=tuple(flat_locations);radii=tuple(curve_locations)
        if section.kind in ('stadium','ellipse','circle'):
            def location(angle):return normal_locations[min(normal_locations,key=lambda v:abs(math.remainder(v-angle,math.tau)))]
            radii=(location(0.),location(math.pi))
            if section.kind=='ellipse':flats=(location(math.pi/2),location(3*math.pi/2))
        return Profile(float(extent),point,tuple(float(i) for i in range(extent+1)),flats,radii)
    return wrap(a),wrap(b)
