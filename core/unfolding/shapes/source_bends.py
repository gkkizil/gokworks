"""Miter and segmented bends with shared joint planes and actual local surfaces."""
import math
from .development import circle,stadium,Profile,basis,unit,adaptive
from .common import add,mul,dot
from .source_extrusions import extrude
from .source_intersections import mapped_part,quadratic


def seam_layout(cut,index):
    if cut=='2_seams_sides':return 2,math.pi/2
    if cut=='2_seams_inside_outside':return 2,0.
    if cut in ('1_seam_staggered','1_seam_alternating'):return 1,math.pi*(index%2)
    if cut=='1_seam_staggered_sides':return 1,math.pi/2+math.pi*(index%2)
    if cut=='1_seam_same_side':return 1,math.pi/2
    if cut=='1_seam_inside':return 1,math.pi
    return 1,0.


def plane_height(origin,axis,rx,ry,plane,x,y):
    point=add(origin,add(mul(rx,x),mul(ry,y)));normal,constant=plane;den=dot(normal,axis)
    if abs(den)<1e-10:raise ValueError('Kesim düzlemi boru eksenine paralel.')
    return (constant-dot(normal,point))/den


def cone_segment(identifier,origin,axis,rx,ry,radius,slope,length,lower,upper,start,span,n,material,options,token):
    if abs(slope)<1e-12:
        return extrude(identifier,circle(2*radius),lambda x,y:plane_height(origin,axis,rx,ry,lower,x,y),
            lambda x,y:plane_height(origin,axis,rx,ry,upper,x,y),n,material,options,token,
            start=start*radius,span=span*radius,origin=origin,axis=axis,radial_x=rx,radial_y=ry)
    factor=abs(slope)/math.hypot(1.,slope)
    def at(theta,plane):
        radial=add(mul(rx,math.cos(theta)),mul(ry,math.sin(theta)));normal,constant=plane
        den=dot(normal,add(axis,mul(radial,slope)))
        if abs(den)<1e-10:raise ValueError('Düzlem koni üretecine paralel.')
        u=(constant-dot(normal,add(origin,mul(radial,radius))))/den;r=radius+slope*u
        if r<=0:raise ValueError('Koni kesimi tepeyi aşıyor.')
        v=add(origin,add(mul(axis,u),mul(radial,r)));psi=(theta-start)*factor;rho=r/factor
        return (rho*math.cos(psi),rho*math.sin(psi)),v,u
    def curves(theta):
        lo,v0,u0=at(theta,lower);hi,v1,u1=at(theta,upper)
        if u1-u0<=options.geometry_tolerance_mm:raise ValueError('Konik segmentin uç kesimleri kesişiyor.')
        return lo+hi+v0+v1
    sampled,e=adaptive(curves,start,start+span,options.chord_error_mm,options.max_samples,[start+span*i/24 for i in range(25)],token)
    low=[(v[:2],v[4:7]) for t,v in sampled];high=[(v[2:4],v[7:10]) for t,v in sampled]
    part=mapped_part(identifier,low+high[::-1],(),n,material,options,token)
    from .common import with_generators
    guides=[];count=n['model_options']['helper_divisions']
    for j in range(count+1):
        theta=start+span*j/count;aa,va,_=at(theta,lower);bb,vb,_=at(theta,upper);guides.append((aa,bb,va,vb))
    part=with_generators(part,guides,n)
    from .source_extrusions import edge_allowances
    part=edge_allowances(part,dict(bottom=[q for q,v in low],top=[q for q,v in high[::-1]],left=(high[0][0],low[0][0]),right=(low[-1][0],high[-1][0])),n,material,options)
    return part,e


def build_segmented(m,n,material,options,token):
    p=n['parameters'];s=m['source_id'];count=p['segments'];angle=math.radians(p.get('angle',90.));delta=angle/(count-1);R=p['R'];v=math.tan(delta/2)
    if not 0<angle<math.pi:raise ValueError('Segmentli dirsek dönüşü (0,180)° olmalı.')
    if 'oval' in s:
        if '-opposite-' in s:profile=stadium(p['H'],p['W']);radial_radius=p['H']/2
        else:
            base=stadium(p['W'],p['H']);profile=Profile(base.perimeter,lambda q:(-base.point(q)[1],base.point(q)[0]),base.breaks);radial_radius=p['H']/2
    else:profile=circle(p.get('D',p.get('D1')));radial_radius=p.get('D',p.get('D1'))/2
    if R<=radial_radius:raise ValueError('Dirsek eksen yarıçapı iç cidarı sıfır/negatif yapıyor.')
    lengths=[R*v*(1 if i in (0,count-1) else 2)+(p.get('E1',0.) if i==0 else p.get('E2',0.) if i==count-1 else 0.) for i in range(count)]
    total=sum(lengths);k=(p['D2']-p['D1'])/(2*total) if 'D2' in p else 0.;r0=p.get('D',p.get('D1',0.))/2
    if count*(2 if n['model_options']['cut_type'].startswith('2_') else 1)>256:raise ValueError('Dirsek parça bütçesi 256 sınırını aşıyor.')
    axes=[(math.sin(i*delta),0.,math.cos(i*delta)) for i in range(count)];origins=[];position=(0.,0.,-p.get('E1',0.))
    for axis,length in zip(axes,lengths):origins.append(position);position=add(position,mul(axis,length))
    planes=[];distance=0.
    for i in range(count-1):
        distance+=lengths[i];joint=origins[i+1];normal=add(axes[i],axes[i+1]);rj=r0+k*distance
        offset=-2*rj*k/(1+k*k) if k else 0.
        planes.append((normal,dot(normal,joint)+offset))
    out=[];residual=0.;distance=0.
    for i,(origin,axis,length) in enumerate(zip(origins,axes,lengths)):
        rx=(math.cos(i*delta),0.,-math.sin(i*delta));ry=(0.,1.,0.)
        lo=planes[i-1] if i else (axis,dot(axis,origin));hi=planes[i] if i<count-1 else (axis,dot(axis,add(origin,mul(axis,length))))
        split,start=seam_layout(n['model_options']['cut_type'],i);start+=math.radians(n['seam_options']['start_angle_deg'])
        for j in range(split):
            ident=f'{s}-S{i+1:02}-P{j+1}'
            if k:
                part,e=cone_segment(ident,origin,axis,rx,ry,r0+k*distance,k,length,lo,hi,start+j*math.tau/split,math.tau/split,n,material,options,token)
            else:
                part,e=extrude(ident,profile,lambda x,y:plane_height(origin,axis,rx,ry,lo,x,y),lambda x,y:plane_height(origin,axis,rx,ry,hi,x,y),
                    n,material,options,token,start=(start/math.tau+j/split)*profile.perimeter,span=profile.perimeter/split,
                    origin=origin,axis=axis,radial_x=rx,radial_y=ry)
            out.append(part);residual=max(residual,e)
        distance+=length
    return tuple(out),dict(segment_count=count,measured_curve_residual_mm=residual,joint_planes=planes,
         conical_taper_per_axis_mm=k,real_piece_count=len(out),outlet_center=position)


def factor_joint(axis1,axis2,r1,k1,r2,k2):
    """Factor the difference of the two quadrics into its common miter planes.

    A shared planar joint exists only when the degenerate-conic condition holds.
    Choose the plane separating incoming and outgoing material half-spaces.
    """
    a=(axis1[0],axis1[2]);b=(axis2[0],axis2[2])
    qxx=(1+k2*k2)*b[0]**2-(1+k1*k1)*a[0]**2
    qxz=(1+k2*k2)*b[0]*b[1]-(1+k1*k1)*a[0]*a[1]
    qzz=(1+k2*k2)*b[1]**2-(1+k1*k1)*a[1]**2
    lx=r2*k2*b[0]-r1*k1*a[0];lz=r2*k2*b[1]-r1*k1*a[1];det=qxx*qzz-qxz*qxz
    if abs(det)<1e-12:raise ValueError('Dirsek eksenleri paralel veya ortak kesim tekil.')
    cx=(-qzz*lx+qxz*lz)/det;cz=(qxz*lx-qxx*lz)/det
    constant=r2*r2-r1*r1+lx*cx+lz*cz
    if abs(constant)>1e-7*max(1.,r1*r1,r2*r2):raise ValueError('Boru/koni yüzeyleri ortak düzlemde kesişmiyor.')
    slopes=quadratic(qzz,2*qxz,qxx);negative=[v for v in slopes if v<0]
    if not negative:raise ValueError('Gönye birleşimi için ayırıcı düzlem bulunamadı.')
    slope=max(negative);intercept=cz-slope*cx
    return (-slope,0.,1.),intercept


def build_miter(m,n,material,options,token):
    p=n['parameters'];s=m['source_id'];cut=n['model_options']['cut_type'];out=[];residual=0.
    if '-double' in s:
        H,X,Y=p['H'],p['X'],p.get('Y',0.)
        if '-outside' in s:H-=p['D'];X-=p['D']
        if min(H,X)<=0:raise ValueError('Dış ölçüler boru çapından büyük olmalı.')
        axes=[(0.,0.,1.),unit((X,Y,H)),(0.,0.,1.)];lengths=[p['L1'],math.sqrt(H*H+X*X+Y*Y),p['L2']];radii=[p['D']/2]*3;slopes=[0.]*3
    else:
        if '-radius' in s:turn=math.radians(p['angle']);lengths=[p['R']*math.tan(turn/2)]*2
        else:turn=math.radians(180-p.get('A',90.));lengths=[p.get('L1',p.get('H')),p.get('L2',p.get('L'))]
        if not 0<turn<math.pi:raise ValueError('Dirsek dönüşü 0–180° arasında olmalı.')
        axes=[(0.,0.,1.),(math.sin(turn),0.,math.cos(turn))]
        if '-pipe-cone-' in s:
            rp=p['D']/2;small=p['d']/2;L=lengths[1]
            roots=quadratic(L*L-rp*rp,-2*small*L,small*small-rp*rp);ks=[k for k in roots if k<0 and small-k*L>0]
            if not ks:raise ValueError('Boru-koni için ortak eliptik gönye ölçüleri çözülemiyor.')
            k=max(ks);rj=small-k*L;radii=[rp,rj];slopes=[0.,k]
        elif '-cone-pipe-' in s:
            base=p['D']/2;rp=p['d']/2;H=lengths[0]
            roots=quadratic(H*H-rp*rp,2*base*H,base*base-rp*rp);ks=[k for k in roots if k<0 and base+k*H>0]
            if not ks:raise ValueError('Koni-boru için ortak eliptik gönye ölçüleri çözülemiyor.')
            k=max(ks);radii=[base, rp];slopes=[k,0.]
        elif '-cone-cone-' in s:
            k=(p['d']-p['D'])/(2*sum(lengths));radii=[p['D']/2,p['D']/2+k*lengths[0]];slopes=[k,k]
        else:radii=[p['D']/2]*2;slopes=[0.,0.]
    origins=[];position=(0.,0.,0.)
    for axis,length in zip(axes,lengths):origins.append(position);position=add(position,mul(axis,length))
    planes=[]
    for i in range(len(axes)-1):
        joint=origins[i+1]
        if not slopes[i] and not slopes[i+1]:normal=add(axes[i],axes[i+1]);constant=dot(normal,joint)
        else:
            normal,offset=factor_joint(axes[i],axes[i+1],radii[i]+slopes[i]*lengths[i],slopes[i],radii[i+1],slopes[i+1]);constant=dot(normal,joint)+offset
        planes.append((normal,constant))
    for i,(axis,length,origin,radius,k) in enumerate(zip(axes,lengths,origins,radii,slopes)):
        axis,rx,ry=basis(axis);lo=planes[i-1] if i else (axis,dot(axis,origin));hi=planes[i] if i<len(axes)-1 else (axis,dot(axis,add(origin,mul(axis,length))))
        split,start=seam_layout(cut,i);start+=math.radians(n['seam_options']['start_angle_deg'])
        part,e=cone_segment(f'{s}-arm{i+1}',origin,axis,rx,ry,radius,k,length,lo,hi,start,math.tau,n,material,options,token)
        out.append(part);residual=max(residual,e)
    return tuple(out),dict(real_arm_count=len(out),joint_planes=planes,measured_curve_residual_mm=residual,
         planar_joint_verified=True,conic_slopes=slopes,axis_end=position)
