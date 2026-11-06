"""Analytic plane/ruling intersections for pipe/plate and trimmed cones."""
from dataclasses import replace
import math
from .common import add,mul,dot,sub
from .development import circle,basis,unit,adaptive
from .source_extrusions import extrude
from .source_intersections import Trunk,mapped_part
from ..models import SurfacePatch,FrozenMap


def build_plate_pipe(m,n,material,options,token):
    p=n['parameters'];s=m['source_id'];r=p['D']/2
    if s.startswith('two-'):
        turn=math.radians(p['T']);axes=[];lengths=[]
        for suffix,sign,anglekey in [('A',-1,'A'),('B',1,'B')]:
            if 'L'+suffix in p:
                length=p['L'+suffix];angle=math.radians(p[anglekey]);x=sign*math.cos(angle);z=math.sin(angle)
            else:
                x=sign*p['X'+suffix];z=p['H'+suffix];length=math.hypot(x,z);x/=length;z/=length
            axes.append((x,z*math.sin(turn),z*math.cos(turn)));lengths.append(length)
        out=[];error=0.
        for i,a in enumerate(axes):
            a,rx,ry=basis(a);other=axes[1-i]
            def lower(x,y):
                v=add(mul(rx,x),mul(ry,y));plane=-v[2]/a[2];bisector=dot(v,sub(other,a))/(1-dot(a,other))
                return max(plane,bisector)
            part,e=extrude(f'{s}-{i+1}',circle(2*r),lower,lambda x,y:lengths[i],n,material,options,token,axis=a,radial_x=rx,radial_y=ry)
            out.append(part);error=max(error,e)
        return tuple(out),dict(measured_curve_residual_mm=error,real_pipe_count=2)
    if 'X' in p:axis=unit((p['X'],p['Y'],p['H']));length=math.sqrt(p['X']**2+p['Y']**2+p['H']**2)
    else:
        angle=math.radians(p['A']);plan=math.radians(p.get('P',0.));axis=(math.cos(angle)*math.cos(plan),math.cos(angle)*math.sin(plan),math.sin(angle));length=p.get('L',0.)
    axis,rx,ry=basis(axis)
    if axis[2]<=1e-6:raise ValueError('Boru sac düzlemine paralel olamaz; saca açı pozitif olmalı.')
    if s.startswith('pipe-'):
        def lower(x,y):return -(rx[2]*x+ry[2]*y)/axis[2]
        part,e=extrude(s,circle(2*r),lower,lambda x,y:length,n,material,options,token,axis=axis,radial_x=rx,radial_y=ry)
        return (part,),dict(measured_curve_residual_mm=e,axis_length_mm=length)
    width,depth=p['W'],p['Dp'];cx,cy=p['Cx'],p['Cy']
    def hole(t):
        angle=math.tau*t;radial=add(mul(rx,r*math.cos(angle)),mul(ry,r*math.sin(angle)));u=-radial[2]/axis[2]
        v=add((cx,cy,0.),add(radial,mul(axis,u)));return v[:2]+v
    samples,e=adaptive(hole,0.,1.,options.chord_error_mm,options.max_samples,[i/16 for i in range(17)],token)
    outer=[((x,y),(x,y,0.)) for x,y in ((0.,0.),(width,0.),(width,depth),(0.,depth))]
    part=mapped_part(s,outer,[[(v[:2],v[2:]) for t,v in samples[:-1]]],n,material,options,token)
    from ..models import Line2D,TrueLength
    count=n['model_options']['helper_divisions'];guides=[];lengths=[]
    for j in range(count):
        v=hole(j/count);guides.append(Line2D(v[:2],(cx,cy),f'G{j}'))
        lengths.append(TrueLength(f'G{j}',v[2:],(cx,cy,0.),math.dist(v[2:],(cx,cy,0.))))
    part=replace(part,construction_lines=tuple(guides),true_lengths=tuple(lengths))
    patches=tuple(SurfacePatch('triangle',FrozenMap(dict(vertices=tuple(part.mesh_3d.vertices[i] for i in tri)))) for tri in part.mesh_3d.triangles)
    return (replace(part,surface_patches=patches),),dict(measured_curve_residual_mm=e,hole_major_diameter_mm=2*r/axis[2],hole_minor_diameter_mm=2*r)


def build_cut_cone(m,n,material,options,token):
    p=n['parameters'];s=m['source_id'];R=p['D']/2
    if 'Ha' in p:apex=p['Ha']
    elif 'A' in p:apex=R/math.tan(math.radians(p['A']/2))
    else:apex=p['H']*p['D']/(p['D']-p['d'])
    if apex<=0:raise ValueError('Koni tepe yüksekliği pozitif olmalı.')
    trunk=Trunk(R,-R/apex);seam=math.pi+math.radians(n['seam_options']['start_angle_deg']);mapper=trunk.mapping(seam)
    def intersect(theta,height,slope):
        q=slope*math.cos(theta);den=1-trunk.slope*q
        if abs(den)<1e-10:raise ValueError('Kesim düzlemi bir üretece paralel.')
        return (height+R*q)/den
    def bounds(theta):
        lo=0.;hi=p['H']
        if s in ('cone-cut-top','cone-cut-top-base'):hi=intersect(theta,p['H'],math.tan(math.radians(p['tilt'])))
        if s in ('cone-cut-base','cone-cut-top-base'):lo=intersect(theta,0.,math.tan(math.radians(p['baseTilt'])))
        if s in ('cone-cut-two-planes','cone-cut-base-two-planes'):
            x=p['X'];a=math.tan(math.radians(p['tilt']));b=math.tan(math.radians(p['tilt2']))
            if s=='cone-cut-two-planes':hi=min(intersect(theta,p['H']-x*a,a),intersect(theta,p['H']+x*b,-b))
            else:lo=max(intersect(theta,x*a,-a),intersect(theta,-x*b,b))
        if lo>=hi or hi>=apex or R+trunk.slope*lo<=0:raise ValueError('Kesim düzlemleri birbirini, koni tepesini veya açıklığı geçiyor.')
        return lo,hi
    def curves(t):
        theta=seam+math.tau*t;lo,hi=bounds(theta);return mapper(theta,lo)+mapper(theta,hi)+trunk.point(theta,lo)+trunk.point(theta,hi)
    sampled,e=adaptive(curves,0.,1.,options.chord_error_mm,options.max_samples,[i/32 for i in range(33)],token)
    low=[(v[:2],v[4:7]) for t,v in sampled];high=[(v[2:4],v[7:10]) for t,v in sampled]
    part=mapped_part(s,low+high[::-1],(),n,material,options,token)
    from .common import with_generators
    guides=[];count=n['model_options']['helper_divisions']
    for j in range(count+1):
        theta=seam+math.tau*j/count;lo,hi=bounds(theta)
        guides.append((mapper(theta,lo),mapper(theta,hi),trunk.point(theta,lo),trunk.point(theta,hi)))
    part=with_generators(part,guides,n)
    from .source_extrusions import edge_allowances
    part=edge_allowances(part,dict(bottom=[q for q,v in low],top=[q for q,v in high[::-1]],left=(high[0][0],low[0][0]),right=(low[-1][0],high[-1][0])),n,material,options)
    return (part,),dict(apex_height_mm=apex,measured_curve_residual_mm=e,plane_reference='D at untrimmed z=0 reference circle; H at axis; plane slopes in x-z')
