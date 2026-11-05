"""Concentric cones: exact annular sectors and a numerically stable cylinder limit."""
import math
from ..models import (Arc2D,Line2D,Geometry2D,Mesh3D,SurfacePatch,FrozenMap,MappingPoint,TrueLength)
from ..geometry import arc_point,sample_count
from .common import finish_part,check_cancel
from .cylinder import shell_part


def build(n,material,options,token=None):
    p=n['parameters'];R=p['bottom_diameter']/2;r=p.get('top_diameter',0.)/2;H=p['height']
    delta=R-r;slant=math.hypot(H,delta);split=n['split_options']['count']
    start=math.radians(n['seam_options']['start_angle_deg']);parts=[]
    mesh_samples=sample_count(R,2*math.pi/split,options.mesh_error_mm,options.max_samples)
    if split*2*(mesh_samples+1)>250000:
        raise ValueError('Koni geometri bütçesi 250000 örneği aşıyor; mesh hata hedefini değiştirin.')
    if delta<=1e-10*max(R,r):
        for i in range(split):
            part,_=shell_part(f'cone-{i+1:02d}',(R+r)/2,H,start+i*2*math.pi/split,2*math.pi/split,
                0.,0.,0.,(0.,0.,0.),(0.,0.,1.),(1.,0.,0.),(0.,1.,0.),n,material,options,token)
            parts.append(part)
        return tuple(parts),dict(cylinder_limit=True,chord_error_bound_mm=0.,radial_limit_error_mm=delta/2,
                                 slant_height_mm=slant,seam_closure_error_mm=0.)
    outer=slant*R/delta;inner=slant*r/delta;sector=2*math.pi*delta/slant/split
    center=(-outer,0.);degrees=math.degrees(sector)
    overlap=n['joint_options']['overlap'] if n['joint_options']['kind']=='lap' else 0.
    for i in range(split):
        check_cancel(token);oa=Arc2D(center,outer,0.,degrees)
        ia=Arc2D(center,inner,degrees,-degrees) if r>0 else None
        a=arc_point(oa,0.);b=arc_point(oa,degrees)
        c=arc_point(ia,degrees) if ia else center;d=arc_point(ia,0.) if ia else center
        curves=[oa]
        if overlap:
            normal=(-math.sin(sector)*overlap,math.cos(sector)*overlap)
            bo=(b[0]+normal[0],b[1]+normal[1]);co=(c[0]+normal[0],c[1]+normal[1])
            curves.extend((Line2D(b,bo),Line2D(bo,co),Line2D(co,c)))
        else: curves.append(Line2D(b,c))
        if ia:curves.append(ia)
        curves.append(Line2D(d,a))
        geometry=Geometry2D(tuple(curves));theta0=start+i*2*math.pi/split;span=2*math.pi/split
        count=max(2,math.ceil(span/(math.pi/8)),sample_count(R,span,options.mesh_error_mm,options.max_samples))
        vertices=[];triangles=[];maps=[]
        for j in range(count+1):
            theta=theta0+span*j/count;psi=degrees*j/count
            for radius,z,flat in ((R,0.,arc_point(oa,psi)),(r,H,arc_point(ia,psi) if ia else center)):
                q=(radius*math.cos(theta),radius*math.sin(theta),z);vertices.append(q)
                maps.append(MappingPoint(flat,q,f'cone-{i+1}.{j}.{int(z>0)}'))
            if j:
                triangles.append((2*j-2,2*j,2*j-1))
                if r>0:triangles.append((2*j,2*j+1,2*j-1))
        patch=SurfacePatch('cone',FrozenMap(dict(bottom_radius=R,top_radius=r,height=H,theta0=theta0,span=span)))
        seam=Line2D(d,a)
        construction=tuple(Line2D(arc_point(ia,degrees*j/8) if ia else center,arc_point(oa,degrees*j/8),f'G{j}') for j in range(1,8))
        lengths=tuple(TrueLength(f'cone-{i+1}.G{j}',
            (R*math.cos(theta0+span*j/8),R*math.sin(theta0+span*j/8),0.),
            (r*math.cos(theta0+span*j/8),r*math.sin(theta0+span*j/8),H),slant) for j in range(9))
        parts.append(finish_part(f'cone-{i+1:02d}',geometry,Mesh3D(tuple(vertices),tuple(triangles)),(patch,),
             math.pi*(R+r)*slant/split,n,material,options,construction=construction,seams=(seam,Line2D(b,c)),
             mappings=maps,lengths=lengths))
    closure=max(math.dist(a.mesh_3d.vertices[-2+k],b.mesh_3d.vertices[k])
                for a,b in zip(parts,parts[1:]+parts[:1]) for k in (0,1))
    return tuple(parts),dict(cylinder_limit=False,slant_height_mm=slant,outer_sector_radius_mm=outer,
         inner_sector_radius_mm=inner,sector_angle_deg=math.degrees(sector),seam_closure_error_mm=closure,chord_error_bound_mm=0.)
