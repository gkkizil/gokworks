"""Cylinder/cone intersections, solved in 3D before any development mapping."""
from dataclasses import dataclass
import math
from .common import add,sub,mul,dot,finish_part,check_cancel
from .development import adaptive,basis,circle,rectangle
from .source_extrusions import extrude,edge_allowances
from ..models import (Geometry2D,Polyline2D,Mesh3D,MappingPoint)
from ..geometry import outline,contour_area


def quadratic(a,b,c):
    if abs(a)<1e-12:
        if abs(b)<1e-12:raise ValueError('Kesişim üreteci yüzeye paralel/çakışık.')
        return (-c/b,)
    det=b*b-4*a*c
    if det < -1e-9*max(1.,b*b,abs(4*a*c)):return ()
    d=math.sqrt(max(0.,det));q=-.5*(b+math.copysign(d,b))
    if abs(q)<1e-14:return (-b/(2*a),)
    return (q/a,c/q)


@dataclass(frozen=True)
class Trunk:
    radius: float
    slope: float=0.
    skew: float=0.
    height: float=1e12
    def residual(self,p):
        x,y,z=p;r=self.radius+self.slope*z
        return ((x-self.skew*z)**2+y*y-r*r)/max(1.,2*abs(r))
    def roots(self,origin,direction):
        x,y,z=origin;dx,dy,dz=direction;x-=self.skew*z;dx-=self.skew*dz;r=self.radius+self.slope*z;dr=self.slope*dz
        return quadratic(dx*dx+dy*dy-dr*dr,2*(x*dx+y*dy-r*dr),x*x+y*y-r*r)
    def point(self,theta,z):
        r=self.radius+self.slope*z
        return (self.skew*z+r*math.cos(theta),r*math.sin(theta),z)
    def angle(self,v):return math.atan2(v[1],v[0]-self.skew*v[2])
    def mapping(self,seam):
        if abs(self.slope)<1e-12:
            if self.skew:raise ValueError('Eğik eşit çaplı ana boru açınımı uygulanmadı.')
            return lambda theta,z:(self.radius*(theta-seam),z)
        apex_z=-self.radius/self.slope;apex=(self.skew*apex_z,0.,apex_z)
        # Integrate spherical generator rotation, not projected azimuth, for skew cones.
        if not self.skew:
            factor=abs(self.slope)/math.hypot(1.,self.slope)
            return lambda theta,z:((self.radius+self.slope*z)/factor*math.cos((theta-seam)*factor),
                                   (self.radius+self.slope*z)/factor*math.sin((theta-seam)*factor))
        count=4096;step=math.tau/count;angles=[0.]
        def speed(theta):
            v=sub(self.point(theta,0.),apex);d=(-self.radius*math.sin(theta),self.radius*math.cos(theta),0.)
            return math.sqrt(max(0.,dot(v,v)*dot(d,d)-dot(v,d)**2))/dot(v,v)
        for i in range(count):
            a=seam+i*step;b=a+step;angles.append(angles[-1]+step*(speed(a)+4*speed((a+b)/2)+speed(b))/6)
        def mapper(theta,z):
            index=(theta-seam)/step;i=max(0,min(count-1,math.floor(index)));f=max(0.,min(1.,index-i));psi=angles[i]+(angles[i+1]-angles[i])*f
            rho=math.dist(self.point(theta,z),apex)
            return rho*math.cos(psi),rho*math.sin(psi)
        return mapper


@dataclass(frozen=True)
class Branch:
    origin: tuple
    axis: tuple
    radial_x: tuple
    radial_y: tuple
    profile: object
    radius: float
    slope: float
    end: float
    def ray(self,t):
        x,y=self.profile.point(t*self.profile.perimeter)
        start=add(self.origin,add(mul(self.radial_x,x),mul(self.radial_y,y)))
        dr=add(mul(self.radial_x,self.slope*x/self.radius),mul(self.radial_y,self.slope*y/self.radius)) if self.slope else (0.,0.,0.)
        return start,add(self.axis,dr)
    def point(self,t,u):
        a,b=self.ray(t);return add(a,mul(b,u))
    def intersection(self,t,trunk):
        origin,direction=self.ray(t);roots=trunk.roots(origin,direction)
        candidates=[u for u in roots if trunk.radius+trunk.slope*(origin[2]+direction[2]*u)>0 and self.radius+self.slope*u>0]
        if not candidates:raise ValueError('Kolun bütün çevresi ana yüzeyle kesişmiyor; çap/kaçıklık/açı uyumsuz.')
        u=max(candidates)
        v=self.point(t,u)
        if abs(trunk.residual(v))>1e-5:raise ValueError('Kesişim noktası ana yüzey üzerinde değil.')
        if u>=self.end:raise ValueError('Branşman ağzı kesişim yüzeyinin içinde kalıyor.')
        return u,v
    def flat(self,t,u,start=0.):
        if not self.slope:return ((t-start)*self.profile.perimeter,u)
        factor=abs(self.slope)/math.hypot(1.,self.slope);rho=(self.radius+self.slope*u)/factor;psi=math.tau*(t-start)*factor
        return rho*math.cos(psi),rho*math.sin(psi)


def mapped_part(identifier,outer,holes,n,material,options,token):
    """2D polygon+holes with a one-to-one supplied 3D boundary map."""
    from shapely.geometry import Polygon
    from shapely import constrained_delaunay_triangles
    outer=list(outer);holes=[list(h) for h in holes]
    if contour_area(outline([q for q,v in outer]).outer)<0:outer.reverse()
    for h in holes:
        if contour_area(outline([q for q,v in h]).outer)>0:h.reverse()
    geo=Geometry2D((Polyline2D(tuple(q for q,v in outer),True),),tuple((Polyline2D(tuple(q for q,v in h),True),) for h in holes))
    poly=Polygon([q for q,v in outer],[[q for q,v in h] for h in holes])
    if not poly.is_valid or poly.area<=0:raise ValueError('Delik dış konturu/dikişi aşıyor veya kendiyle kesişiyor.')
    pairs=outer+[p for h in holes for p in h];flat=[p for p,v in pairs];vertices=[v for p,v in pairs];lookup={q:i for i,q in enumerate(flat)};triangles=[];area=0.
    for tri in constrained_delaunay_triangles(poly).geoms:
        check_cancel(token)
        
        coords=list(tri.exterior.coords)[:3];idx=tuple(lookup[tuple(q)] for q in coords)
        if len(set(idx))<3:continue
        triangles.append(idx);area+=tri.area
    if not math.isclose(area,poly.area,rel_tol=1e-8,abs_tol=1e-5):raise ValueError('Delikli yüzey üçgenlemesi bütün alanı kapsamıyor.')
    maps=tuple(MappingPoint(q,v,str(i)) for i,(q,v) in enumerate(pairs))
    # Smooth curved patches require trimmed analytic B-Rep; explicitly no STEP yet.
    return finish_part(identifier,geo,Mesh3D(tuple(vertices),tuple(triangles)),(),poly.area,n,material,options,mappings=maps)


def build_branch(m,n,material,options,token):
    p=n['parameters'];s=m['source_id'];isrect=s.startswith('rectangle-');iscone=s.startswith('cone-');trunkcone='to-cone-' in s or 'to-oblique-cone-' in s
    oblique='to-oblique-cone-' in s
    if trunkcone:
        trunk=Trunk(p['D']/2,(p['d']-p['D'])/(2*p['H']),p.get('X',0.)/p['H'] if oblique else 0.,p['H'])
    else:trunk=Trunk(p['Dt']/2,height=p.get('H',1e12))
    vertical='-vertical-' in s;horizontal='-horizontal-' in s or '-90-' in s or '-tangent-90-' in s
    if vertical:angle=0.
    elif horizontal:angle=90.
    elif iscone:angle=90-p.get('B',45.)
    elif trunkcone:angle=90-p.get('A',45.)
    else:angle=p.get('A',45.)
    azimuth=math.radians(p.get('B',0.) if oblique and not iscone else 0.)
    angle=math.radians(angle);axis=(math.sin(angle)*math.cos(azimuth),math.sin(angle)*math.sin(azimuth),math.cos(angle));axis,rx,ry=basis(axis)
    z0=p.get('Hb',0.);x0=0.
    if vertical:x0=p.get('Xb',p.get('X',0.));z0=0.
    zoffset=p.get('Z',0.)
    if '-tangent-' in s:zoffset=trunk.radius-p['W']/2
    origin=(x0,zoffset,z0);end=p.get('L',p.get('Ls',p.get('Ht',1e6)))
    if vertical:end=p.get('Ht',p.get('L',1e6))
    if isrect:
        profile=rectangle(p['W'],p.get('Hr',p.get('B',0.)),p['r']);radius=1.;slope=0.
    elif iscone:
        if 'db' in p:
            radius=p['Db']/2;slope=(p['db']-p['Db'])/(2*p['Ht']);end=p['Ht']
        else:
            end=p.get('Ls',p.get('Ht',0.));slope=-math.tan(math.radians(p['A']/2));radius=p.get('Db',p.get('d'))/2-slope*end
        profile=circle(2*radius)
    else:radius=p['Db']/2;slope=0.;profile=circle(2*radius)
    branch=Branch(origin,axis,rx,ry,profile,radius,slope,end)
    cuts=[q/profile.perimeter for q in profile.breaks]+[i/24 for i in range(25)]
    def intersection(t):
        u,v=branch.intersection(t,trunk);flat=branch.flat(t,u);return flat+v
    samples,residual=adaptive(intersection,0.,1.,options.chord_error_mm,options.max_samples,cuts,token)
    intersection_vertices=[v[2:] for t,v in samples[:-1]]
    if not s.endswith('-trunk') and trunk.height<1e11 and any(v[2]<-options.geometry_tolerance_mm or v[2]>trunk.height+options.geometry_tolerance_mm for v in intersection_vertices):
        raise ValueError('Kol kesişimi ana gövdenin sonlu yükseklik sınırını aşıyor.')
    quality=dict(intersection_max_trunk_residual_mm=max(abs(trunk.residual(v)) for v in intersection_vertices),
                 intersection_points_3d=intersection_vertices,measured_curve_residual_mm=residual,
                 assumptions='All branch and trunk dimensions refer to their common geometric midsurface; branch angle is documented in family notes.')
    if s.endswith('-branch'):
        lower=[(v[:2],v[2:]) for t,v in samples]
        upper=[(branch.flat(t,end),branch.point(t,end)) for t,v in samples]
        part=mapped_part(s,lower+upper[::-1],(),n,material,options,token)
        from .common import with_generators
        guides=[];count=n['model_options']['helper_divisions']
        for j in range(count+1):
            t=j/count;u,v=branch.intersection(t,trunk)
            guides.append((branch.flat(t,u),branch.flat(t,end),v,branch.point(t,end)))
        part=with_generators(part,guides,n)
        part=edge_allowances(part,dict(bottom=[q for q,v in lower],top=[q for q,v in upper[::-1]],left=(upper[0][0],lower[0][0]),right=(lower[-1][0],upper[-1][0])),n,material,options)
        if n['model_options'].get('heel'):
            raise ValueError('Topuk düzeltmesinin kaynak ölçü tanımı doğrulanmadı; heel=false kullanın.')
        return (part,),quality
    # Trunk opening and shell use the exact same intersection curve, with the seam on the back.
    seam=math.pi+math.radians(n['seam_options']['start_angle_deg']);mapper=trunk.mapping(seam)
    def wrap(theta):return seam+(theta-seam)%math.tau
    hole=[]
    for v in intersection_vertices:
        if not options.geometry_tolerance_mm<v[2]<trunk.height-options.geometry_tolerance_mm:raise ValueError('Branşman deliği ana gövdenin açık ucuna taşıyor.')
        theta=wrap(trunk.angle(v));hole.append((mapper(theta,v[2]),v))
    if max(wrap(trunk.angle(v)) for v in intersection_vertices)-min(wrap(trunk.angle(v)) for v in intersection_vertices)>math.pi:
        raise ValueError('Delik ana parça dikişini kesiyor; dikiş açısını değiştirin.')
    def shell(t):
        theta=seam+math.tau*t;lo=trunk.point(theta,0.);hi=trunk.point(theta,trunk.height)
        return mapper(theta,0.)+mapper(theta,trunk.height)+lo+hi
    outer,e=adaptive(shell,0.,1.,options.chord_error_mm,options.max_samples,[i/16 for i in range(17)],token)
    bottom=[(v[:2],v[4:7]) for t,v in outer];top=[(v[2:4],v[7:10]) for t,v in outer]
    part=mapped_part(s,bottom+top[::-1],[hole],n,material,options,token)
    from .common import with_generators
    count=n['model_options']['helper_divisions']
    part=with_generators(part,[(mapper(seam+math.tau*j/count,0.),mapper(seam+math.tau*j/count,trunk.height),
                              trunk.point(seam+math.tau*j/count,0.),trunk.point(seam+math.tau*j/count,trunk.height)) for j in range(count+1)],n,clip_holes=True)
    part=edge_allowances(part,dict(bottom=[q for q,v in bottom],top=[q for q,v in top[::-1]],left=(top[0][0],bottom[0][0]),right=(bottom[-1][0],top[-1][0])),n,material,options)
    quality['measured_curve_residual_mm']=max(residual,e)
    return (part,),quality


def multi_pipe_parts(m,n,material,options,token):
    """Each real arm is trimmed against every neighbour, not copied as one alias."""
    p=n['parameters'];s=m['source_id'];D=p.get('Db',p.get('D'));length=p.get('L',p.get('H',0.));trunk=None
    if s.startswith('breeches-'):
        count=int(s.split('-')[1]);angles=[0.]
        for i in range(1,count):angles.append(angles[-1]+math.radians(p[f'A{i}']))
        if angles[-1]>=math.tau:raise ValueError('Pantolon açıları toplamı 360° altında olmalı.')
        axes=[(math.sin(a),0.,math.cos(a)) for a in angles]
    else:
        trunk=Trunk(p['Dt']/2)
        if s.endswith('four-branches'):
            ab=math.radians(p['A']/2);pairs=[(p['B1'],ab),(p['B2'],-ab),(p['B1'],math.pi+ab),(p['B2'],math.pi-ab)]
        elif s.endswith('two-branches-along'):pairs=[(p['B1'],0.),(p['B2'],math.pi)]
        elif s.endswith('two-branches-angled'):pairs=[(p['B'],math.radians(p['A']/2)),(p['B'],-math.radians(p['A']/2))]
        else:pairs=[(90.,math.radians(p['A']/2)),(90.,-math.radians(p['A']/2))]
        axes=[(math.sin(math.radians(a))*math.cos(b),math.sin(math.radians(a))*math.sin(b),math.cos(math.radians(a))) for a,b in pairs]
    out=[];residual=0.;surface_residual=0.
    for j,axis in enumerate(axes):
        axis,rx,ry=basis(axis);profile=circle(D)
        def lower(x,y):
            nonlocal surface_residual
            radial=add(mul(rx,x),mul(ry,y));limits=[]
            if trunk:
                roots=trunk.roots(radial,axis)
                if not roots:raise ValueError('Ana boruyla kesişmeyen branşman üreteci.')
                limits.append(max(roots))
            for k,other in enumerate(axes):
                if j==k:continue
                den=1-dot(axis,other)
                if den<1e-9:raise ValueError('Kol eksenleri çakışıyor.')
                # Equal-radius cylinder intersection on the positive-axis bisector.
                u=dot(radial,other)/den
                # Negative generator offsets are required on the back of a
                # junction; replacing them with zero leaves an unmatched cap.
                limits.append(u)
            lo=max(limits,default=0.)
            if lo>=length:raise ValueError('Kol boyu birleşim kesiminden kısa.')
            return lo
        part,e=extrude(f'{s}-arm{j+1:02}',profile,lower,lambda x,y:length,n,material,options,token,
                       axis=axis,radial_x=rx,radial_y=ry)
        out.append(part);residual=max(residual,e)
    return tuple(out),dict(real_arm_count=len(axes),measured_curve_residual_mm=residual,
        intersection_method='positive-axis cylinder bisectors plus trunk quadric; maximum active trim')
