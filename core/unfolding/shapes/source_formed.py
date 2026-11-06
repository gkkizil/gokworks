"""Formed heads and helical flights: explicit, quantified faceting/strain methods."""
from dataclasses import replace
import math
from .development import adaptive,ribbon
from .common import finish_part,check_cancel
from ..models import (Mesh3D,Geometry2D,Circle2D,FrozenMap,SurfacePatch,MappingPoint)
from ..geometry import outline,contour_area


def head_meridian(m,p,tol,maximum,token):
    a=p['D']/2;hole=p['Dh']/2;F=p['F']
    if not 0<=hole<a:raise ValueError('Tepe deliği çapı 0 ≤ Dh < D olmalı.')
    if F<0:raise ValueError('Düz etek yüksekliği negatif olamaz.')
    points=[(a,0.)]
    if F:points.append((a,F))
    residual=0.
    if m['source_id'].endswith('torispherical'):
        R=p['Rc'];k=p['rk']
        if not 0<k<a or R<=a or R-k<=a-k:raise ValueError('Torisferik tepe/knuckle yarıçapları geometrik olarak geçersiz.')
        zc=-math.sqrt((R-k)**2-(a-k)**2);u=math.acos((a-k)/(R-k));rt=a-k+k*math.cos(u)
        knuckle_end=u if hole<=rt else math.acos((hole-a+k)/k)
        sampled,e=adaptive(lambda q:(a-k+k*math.cos(q),F+k*math.sin(q)),0,knuckle_end,tol,maximum,token=token)
        points.extend(v for q,v in sampled[1:]);residual=max(residual,e)
        if hole<rt:
            end=math.acos(hole/R);sampled,e=adaptive(lambda q:(R*math.cos(q),F+zc+R*math.sin(q)),u,end,tol,maximum,token=token)
            points.extend(v for q,v in sampled[1:]);residual=max(residual,e)
    else:
        height=p.get('Hd',a)
        if height<=0:raise ValueError('Bombe yüksekliği pozitif olmalı.')
        end=math.acos(hole/a)
        sampled,e=adaptive(lambda q:(a*math.cos(q),F+height*math.sin(q)),0,end,tol,maximum,token=token)
        points.extend(v for q,v in sampled[1:]);residual=max(residual,e)
    return points,residual


def build_head(m,n,material,options,token):
    p=n['parameters'];profile,residual=head_meridian(m,p,options.chord_error_mm,options.max_samples,token)
    half=math.pi/p['n'];flat=[];verts=[];triangles=[];height=0.;previous=None;maps=[]
    for i,(r,z) in enumerate(profile):
        if previous:
            rr,zz=previous;height+=math.hypot((r-rr)*math.cos(half),z-zz)
        for sign in (-1,1):
            q=(sign*r*math.sin(half),height);v=(r*math.cos(half),sign*r*math.sin(half),z)
            flat.append(q);verts.append(v);maps.append(MappingPoint(q,v,f'R{i}.{sign}'))
        if i:
            a,b,c,d=2*i-2,2*i-1,2*i,2*i+1
            triangles.append((a,c,b))
            if r>options.geometry_tolerance_mm:triangles.append((c,d,b))
        previous=(r,z)
    points=flat[::2]+flat[1::2][::-1]
    points=[v for i,v in enumerate(points) if not i or math.dist(v,points[i-1])>1e-8]
    if contour_area(outline(points).outer)<0:points.reverse()
    geometry=outline(points)
    patches=tuple(SurfacePatch('triangle',FrozenMap(dict(vertices=tuple(verts[j] for j in t)))) for t in triangles)
    part=finish_part(m['source_id']+'-gore',geometry,Mesh3D(tuple(verts),tuple(triangles)),patches,contour_area(geometry.outer),n,material,options,mappings=maps)
    from .common import with_generators
    from ..models import Line2D
    count=n['model_options']['helper_divisions'];indices=sorted(set(round(j*(len(profile)-1)/count) for j in range(count+1)))
    part=with_generators(part,[(flat[2*i],flat[2*i+1],verts[2*i],verts[2*i+1]) for i in indices],n)
    part=replace(part,bending_lines=tuple(Line2D(flat[2*i],flat[2*i+1],f'B{i}') for i in range(1,len(profile)-1)))
    part=replace(part,quantity=p['n'])
    return (part,),dict(approximation='faceted_gore; forming/springback/press forces not evaluated',smooth_isometry=False,
        meridian_measured_residual_mm=residual,circumferential_chord_deviation_mm=max(r for r,z in profile)*(1-math.cos(half)),
        circumferential_length_deficit_ratio=1-math.sin(half)/half,gore_quantity=p['n'])


def build_helix(m,n,material,options,token):
    p=n['parameters'];s=m['source_id'];pitch=p['P'];width=p['W']
    if min(pitch,width)<=0:raise ValueError('Hatve ve kanat genişliği pozitif olmalı.')
    if s=='helix-angled-flight':inner=p['d']/2;outer=inner+width;rise=p['R']
    else:outer=p['D']/2;inner=outer-width;rise=0.
    if inner<=0:raise ValueError('Kanat genişliği iç yarıçapı sıfır/negatif yapıyor.')
    if s=='helix-deformed':
        lo=math.hypot(math.tau*outer,pitch);li=math.hypot(math.tau*inner,pitch);rf=lo/math.tau;ri=rf-width
        geometry=Geometry2D((Circle2D((0.,0.),rf),),((Circle2D((0.,0.),ri),),))
        # Preview shows the intended formed helix; no STEP claim for this non-isometric blank.
        samples=max(32,math.ceil(math.tau*math.sqrt(outer/(8*options.mesh_error_mm))))
        if samples>options.max_samples:raise ValueError('Helezon önizleme bütçesi aşıldı.')
        vertices=[];triangles=[]
        for i in range(samples+1):
            angle=math.tau*i/samples
            vertices.extend(((inner*math.cos(angle),inner*math.sin(angle),pitch*i/samples),(outer*math.cos(angle),outer*math.sin(angle),pitch*i/samples)))
            if i:triangles.extend(((2*i-2,2*i,2*i-1),(2*i,2*i+1,2*i-1)))
        part=finish_part(s,geometry,Mesh3D(tuple(vertices),tuple(triangles)),(),math.pi*(rf*rf-ri*ri),n,material,options)
        return (part,),dict(approximation='outer_edge_length_matched_annular_forming_blank; not an isometric development',smooth_isometry=False,
            required_inner_edge_engineering_strain=li/(math.tau*ri)-1,outer_edge_strain=0.,radial_blank_width_mm=width)
    H=p['H'];turns=H/pitch
    if not 0<turns<=256:raise ValueError('Helezon tur sayısı (0,256] aralığında olmalı.')
    if s=='helix-tapered' and p['Dt']/2-width<=0:raise ValueError('Konik kanadın üst iç yarıçapı pozitif olmalı.')
    out=[];edge_error=0.;residual=0.
    for turn in range(math.ceil(turns)):
        check_cancel(token);start=math.tau*turn;end=math.tau*min(turn+1,turns)
        def points(angle):
            z=pitch*angle/math.tau;ro=outer+(p.get('Dt',2*outer)/2-outer)*z/H if s=='helix-tapered' else outer
            ri=ro-width
            return (ri*math.cos(angle),ri*math.sin(angle),z,ro*math.cos(angle),ro*math.sin(angle),z+rise)
        sampled,e=adaptive(points,start,end,options.chord_error_mm,options.max_samples,[start+(end-start)*i/16 for i in range(17)],token)
        part,ee=ribbon(f'{s}-turn{turn+1:03}',[v[:3] for t,v in sampled],[v[3:] for t,v in sampled],n,material,options,token)
        # noNumbers means helper identifiers/labels must not imply bend numbering.
        part=replace(part,construction_lines=(),true_lengths=(),bending_lines=tuple(replace(l,id='') for l in part.bending_lines))
        out.append(part);edge_error=max(edge_error,ee);residual=max(residual,e)
    return tuple(out),dict(approximation='triangulated_helicoid; forming strain between facets not evaluated',smooth_isometry=False,
        measured_curve_residual_mm=residual,facet_edge_error_mm=edge_error,total_turns=turns)
