"""Analytic cylindrical development, including independent planar end cuts."""
import math
from dataclasses import replace
from ..models import (Line2D, Polyline2D, Geometry2D, Mesh3D, SurfacePatch, FrozenMap,
                      MappingPoint, TrueLength)
from ..geometry import sample_count
from .common import finish_part, check_cancel, add, mul


def shell_part(identifier, radius, length, theta0, span, lower, upper, azimuth,
               origin, axis, radial_x, radial_y, n, material, options, token=None):
    check_cancel(token)
    amplitude=radius*max(abs(lower),abs(upper))
    count=max(1,math.ceil(abs(span)*math.sqrt(amplitude/(8*options.chord_error_mm))))
    if count>options.max_samples: raise ValueError('Eğik kesim için gereken örnek sayısı üst sınırı aşıyor.')
    width=radius*span
    def z(theta,top): return (length if top else 0)+radius*(upper if top else lower)*math.cos(theta-azimuth)
    def line_points(top,number):
        return tuple((width*i/number,z(theta0+span*i/number,top)) for i in range(number+1))
    low,high=line_points(False,count),line_points(True,count)
    def curve(p): return Line2D(p[0],p[-1]) if len(p)==2 else Polyline2D(p)
    overlap=n['joint_options']['overlap'] if n['joint_options']['kind']=='lap' else 0.
    curves=[curve(low)]
    if overlap:
        curves.extend((Line2D(low[-1],(width+overlap,low[-1][1])),
                       Line2D((width+overlap,low[-1][1]),(width+overlap,high[-1][1])),
                       Line2D((width+overlap,high[-1][1]),high[-1])))
    else: curves.append(Line2D(low[-1],high[-1]))
    curves.extend((curve(high[::-1]),Line2D(high[0],low[0])))
    geometry=Geometry2D(tuple(curves))
    mesh_count=max(2,math.ceil(abs(span)/(math.pi/8)),sample_count(radius*math.sqrt(1+max(abs(lower),abs(upper))**2),span,
                                  options.mesh_error_mm,options.max_samples))
    vertices=[];triangles=[];mappings=[];lengths=[]
    for i in range(mesh_count+1):
        if i%128==0:check_cancel(token)
        theta=theta0+span*i/mesh_count
        radial=add(mul(radial_x,radius*math.cos(theta)),mul(radial_y,radius*math.sin(theta)))
        pair=[]
        for top in (False,True):
            height=z(theta,top);v=add(origin,add(radial,mul(axis,height)));vertices.append(v);pair.append(v)
            mappings.append(MappingPoint((width*i/mesh_count,height),v,f'{identifier}.{i}.{int(top)}'))
        if i: triangles.extend(((2*i-2,2*i,2*i+1),(2*i-2,2*i+1,2*i-1)))
    patch=SurfacePatch('cylinder',FrozenMap(dict(radius=radius,length=length,theta0=theta0,span=span,
        lower=lower,upper=upper,azimuth=azimuth,origin=origin,axis=axis,radial_x=radial_x)))
    patches=(patch,)
    if (lower or upper) and not overlap:
        from .development import circle
        from .surface_patches import extrusion_patches
        patches=extrusion_patches(circle(2*radius),geometry,theta0*radius,
            origin=origin,axis=axis,radial_x=radial_x,radial_y=radial_y)
    net=radius*(length*span+radius*(upper-lower)*(math.sin(theta0+span-azimuth)-math.sin(theta0-azimuth)))
    seams=(Line2D(low[0],high[0]),Line2D(low[-1],high[-1]))
    construction=tuple(Line2D((width*i/8,z(theta0+span*i/8,False)),
                            (width*i/8,z(theta0+span*i/8,True)),f'G{i}') for i in range(1,8))
    for i in range(9):
        theta=theta0+span*i/8
        radial=add(mul(radial_x,radius*math.cos(theta)),mul(radial_y,radius*math.sin(theta)))
        a,b=(add(origin,add(radial,mul(axis,z(theta,top)))) for top in (False,True))
        lengths.append(TrueLength(f'{identifier}.G{i}',a,b,math.dist(a,b)))
    part=finish_part(identifier,geometry,Mesh3D(tuple(vertices),tuple(triangles)),patches,net,n,material,options,
                     construction=construction,seams=seams,mappings=mappings,lengths=lengths)
    if not overlap:
        part=replace(part,forming_basis=FrozenMap(dict(kind='circle',radius_mm=radius,start_mm=theta0*radius,span_mm=width)))
    return part, amplitude*(span/count)**2/8


def build(n, material, options, token=None):
    p=n['parameters'];radius=p['diameter']/2;length=p['height']
    slope=-math.tan(math.radians(p.get('cut_angle_deg',0.)))
    azimuth=math.radians(p.get('plane_azimuth_deg',0.))
    start=math.radians(n['seam_options']['start_angle_deg']);split=n['split_options']['count']
    mesh_samples=sample_count(radius*math.hypot(1.,slope),2*math.pi/split,options.mesh_error_mm,options.max_samples)
    cut_samples=max(1,math.ceil(2*math.pi/split*math.sqrt(radius*abs(slope)/(8*options.chord_error_mm))))
    if split*(2*(mesh_samples+1)+2*(cut_samples+1))>250000:
        raise ValueError('Silindir geometri bütçesi 250000 örneği aşıyor; hata hedefini veya bölme sayısını değiştirin.')
    parts=[];error=0.
    for i in range(split):
        part,bound=shell_part(f'cylinder-{i+1:02d}',radius,length,start+2*math.pi*i/split,2*math.pi/split,
            0.,slope,azimuth,(0.,0.,0.),(0.,0.,1.),(1.,0.,0.),(0.,1.,0.),n,material,options,token)
        parts.append(part);error=max(error,bound)
    closure=max(math.dist(a.mesh_3d.vertices[-2+k],b.mesh_3d.vertices[k])
                for a,b in zip(parts,parts[1:]+parts[:1]) for k in (0,1))
    return tuple(parts), dict(chord_error_bound_mm=error,mid_diameter_mm=2*radius,
                             circumference_mm=2*math.pi*radius,seam_closure_error_mm=closure)
