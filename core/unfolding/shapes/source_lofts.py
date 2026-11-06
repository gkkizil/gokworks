"""Feature-preserving section lofts and independent real-length developments."""
from dataclasses import replace
import math
from .development import adaptive,ribbon
from .common import check_cancel
from ..models import FrozenMap,SurfacePatch,Arc2D
from .source_extrusions import edge_allowances
from .support_profiles import (round_section,oval_section,ellipse_section,polygon_section,rectangular_section,matched_profiles)


def section(m,p,top=False):
    s=m['source_id'];family=m['family']
    if family in ('Eğik silindir','Eğik koni'):
        return round_section(p.get('d',p['D']) if top else p['D'])
    if family=='Dikdörtgenden yuvarlağa':
        if top:return round_section(p['D'])
        if 'drop' in p:
            length=p['W'];depth=p['hRight'];drop=p['drop'];drop2=p.get('drop2',0.)
            if drop+drop2>=length:raise ValueError('Taban köşeleri ters sıralanıyor; içe çekmeler toplamı taban boyundan küçük olmalı.')
            return polygon_section([(-length/2,-depth/2),(length/2,-depth/2),(length/2-drop2,depth/2),(-length/2+drop,depth/2)],p['cornerRadius'])
        return rectangular_section(p['W'],p.get('L',p['W']),p.get('R',p.get('cornerRadius',0.)))
    if family=='Dikdörtgen redüksiyon':return rectangular_section(p['Wt'],p['Lt'],p['Rt']) if top else rectangular_section(p['W'],p['L'],p['R'])
    if family=='Yuvarlak redüksiyon':return round_section(p['Dt'] if top else p['D'])
    if family in ('Ovalden yuvarlağa','Elipsten yuvarlağa'):
        return round_section(p['D']) if top else (oval_section if family.startswith('Oval') else ellipse_section)(p['L'],p['W'])
    if family in ('Oval redüksiyon','Elips redüksiyon'):
        return (oval_section if family.startswith('Oval') else ellipse_section)(p['Lt'] if top else p['L'],p['Wt'] if top else p['W'])
    if family in ('Ovalden dikdörtgene','Elipsten dikdörtgene'):
        return (oval_section if family.startswith('Oval') else ellipse_section)(p['Lt'],p['Wt']) if top else rectangular_section(p['W'],p['L'],p['R'])
    if family in ('Altıgenden yuvarlağa','Sekizgenden yuvarlağa'):
        if top:return round_section(p['D'])
        count=6 if family.startswith('Altı') else 8;r=p['AF']/(2*math.cos(math.pi/count))
        return polygon_section([(r*math.cos(math.tau*i/count+math.pi/count),r*math.sin(math.tau*i/count+math.pi/count)) for i in range(count)],p['R'])
    raise ValueError('Kesit yöntemi tanımlanmadı: '+s)


def count_cuts(cut):
    return 4 if cut.startswith('4_') else 3 if cut.startswith('3_') else 2 if cut.startswith('2_') else 1


def build_loft(m,n,material,options,token):
    p=n['parameters'];a,b=matched_profiles(section(m,p),section(m,p,True));h=p['H'];x=p.get('xOffset',p.get('X',0.));y=p.get('yOffset',p.get('Y',0.))
    tilt=math.radians(p.get('tiltAngle',90. if m['source_id']=='round-to-round-top-90' else 0.));base=math.radians(p.get('baseAngle',0.))
    def bottom(t):
        xx,yy=a.point(t*a.perimeter);return xx*math.cos(base),yy,-xx*math.sin(base)
    def top(t):
        xx,yy=b.point(t*b.perimeter);return x+xx*math.cos(tilt),y+yy,h-xx*math.sin(tilt)
    return build_sections(m,n,material,options,token,bottom,top,a,b)


def build_sections(m,n,material,options,token,bottom,top,a,b):
    p=n['parameters'];cuts=count_cuts(n['model_options']['cut_type']);levels=p.get('levels',1)
    if cuts*levels>256:raise ValueError('Parça bütçesi 256 üst sınırını aşıyor.')
    seam=n['seam_options']['start_angle_deg']/360
    cut=n['model_options']['cut_type']
    positions=a.radius_seams if 'radius' in cut else a.flat_seams
    if '180' in cut and len(positions)==4:positions=positions[1:]+positions[:1]
    if cuts==4 and len(a.flat_seams)==len(a.radius_seams)==2:
        positions=tuple(sorted(a.flat_seams+a.radius_seams))
    if positions and len(positions)%cuts==0:
        positions=[positions[i*len(positions)//cuts]/a.perimeter for i in range(cuts)]
        positions=sorted((v+seam)%1 for v in positions)
    else:positions=[seam+j/cuts for j in range(cuts)]
    bounds=positions+[positions[0]+1.]
    if m['family'] in ('Eğik koni','Eğik silindir'):
        direction=math.atan2(p.get('Y',0.),p.get('X',0.))/math.tau
        if cuts==2:positions=[direction+.25+seam,direction+.75+seam]
        else:positions=[seam+(direction if m['cut_set'] in ('K12','K14') else .5)]
        bounds=positions+[positions[0]+1.]
    breakpoints=[q/pr.perimeter+offset for offset in (-1,0,1,2) for pr in (a,b) for q in pr.breaks]
    breakpoints.extend(i/32 for i in range(-32,97))
    helpers=n['model_options']['helper_divisions']
    breakpoints.extend(i/helpers for i in range(-helpers,3*helpers+1))
    result=[];error=0.;edge_error=0.
    for level in range(levels):
        lo=lambda t:tuple((1-level/levels)*aa+level/levels*bb for aa,bb in zip(bottom(t),top(t)))
        hi=lambda t:tuple((1-(level+1)/levels)*aa+(level+1)/levels*bb for aa,bb in zip(bottom(t),top(t)))
        for j in range(cuts):
            check_cancel(token);start=bounds[j];end=bounds[j+1]
            samples,e=adaptive(lambda t:lo(t)+hi(t),start,end,options.chord_error_mm,options.max_samples,breakpoints,token)
            lower=[v[:3] for t,v in samples];upper=[v[3:] for t,v in samples]
            if any(math.dist(v,w)<options.geometry_tolerance_mm for v,w in zip(lower,upper)):raise ValueError('Geçişte sıfır boylu üreteç veya kesişen ağızlar var.')
            part,ee=ribbon(f'{m["source_id"]}-L{level+1:02}-P{j+1:02}',lower,upper,n,material,options,token,p.get('diagonal',1))
            flat=[q.developed for q in part.mappings];low=flat[::2];high=flat[1::2]
            part=edge_allowances(part,dict(bottom=low,top=high[::-1],left=(high[0],low[0]),right=(low[-1],high[-1])),n,material,options)
            result.append(part);error=max(error,e);edge_error=max(edge_error,ee)
    return tuple(result),dict(measured_curve_residual_mm=error,facet_edge_error_mm=edge_error,
         approximation='piecewise_planar_ruled_surface; smooth forming strain is not solved',smooth_isometry=False,
         level_count=levels,cut_part_count=cuts)


def translate_part(part,z):
    return replace(part,mesh_3d=replace(part.mesh_3d,vertices=tuple((x,y,zz+z) for x,y,zz in part.mesh_3d.vertices)),
        mappings=tuple(replace(mp,assembled=(mp.assembled[0],mp.assembled[1],mp.assembled[2]+z)) for mp in part.mappings),
        surface_patches=tuple(SurfacePatch('triangle',FrozenMap(dict(vertices=tuple((x,y,zz+z) for x,y,zz in patch.data['vertices']))))
                              for patch in part.surface_patches) if z else part.surface_patches)


def build_cone(m,n,material,options,token):
    from . import cone
    p=n['parameters'];H=p['H'];R=p['D']/2;r=p.get('d',0.)/2;levels=p.get('levels',1);parts=p.get('parts',1);out=[]
    if parts*levels>256:raise ValueError('Koni kat × parça sayısı 256 sınırını aşıyor.')
    for level in range(levels):
        nn=dict(n);nn['parameters']=dict(bottom_diameter=2*(R+(r-R)*level/levels),top_diameter=2*(R+(r-R)*(level+1)/levels),height=H/levels)
        nn['split_options']=dict(count=parts)
        computed,q=cone.build(nn,material,options,token)
        for i,part in enumerate(computed):
            if level:
                # Analytic conical patches carry their own placement; do not silently leave at z=0.
                patches=tuple(SurfacePatch(s.kind,FrozenMap(
                    dict(s.data,origin=(s.data['origin'][0],s.data['origin'][1],s.data['origin'][2]+H*level/levels))
                    if s.kind=='cylinder' else dict(s.data,z_offset=H*level/levels))) for s in part.surface_patches)
                part=replace(part,surface_patches=patches,mesh_3d=replace(part.mesh_3d,vertices=tuple((x,y,z+H*level/levels) for x,y,z in part.mesh_3d.vertices)),
                    mappings=tuple(replace(mp,assembled=(mp.assembled[0],mp.assembled[1],mp.assembled[2]+H*level/levels)) for mp in part.mappings),
                    true_lengths=tuple(replace(v,start=(v.start[0],v.start[1],v.start[2]+H*level/levels),end=(v.end[0],v.end[1],v.end[2]+H*level/levels)) for v in part.true_lengths))
            from .common import finish_part
            part=finish_part(f'{m["source_id"]}-L{level+1:02}-P{i+1:02}',part.geometry_2d,part.mesh_3d,part.surface_patches,
                part.metrics.net_area_mm2,n,material,options,construction=part.construction_lines,seams=part.seams,
                mappings=part.mappings,lengths=part.true_lengths)
            # Named conic arc edges receive allowances along their actual curves.
            from ..geometry import curve_points
            low=curve_points(part.geometry_2d.outer[0],options.chord_error_mm,options.max_samples)
            inner=None
            if r>0:
                inner=next((v for v in part.geometry_2d.outer if getattr(v,'kind',None)=='arc' and v is not part.geometry_2d.outer[0]),None)
                high=curve_points(inner if inner else part.geometry_2d.outer[-2],options.chord_error_mm,options.max_samples)
            else:high=(part.geometry_2d.outer[-1].start,)
            # Source helper divisions are independent of the legacy eight
            # generators and independent of the preview mesh sample count.
            from .common import with_generators
            from ..geometry import arc_point
            bottom_radius=nn['parameters']['bottom_diameter']/2
            top_radius=nn['parameters']['top_diameter']/2
            z0=H*level/levels;count=n['model_options']['helper_divisions'];guides=[]
            cylinder_limit=not isinstance(part.geometry_2d.outer[0],Arc2D)
            theta0=math.radians(n['seam_options']['start_angle_deg'])+math.tau*i/parts
            for j in range(count+1):
                f=j/count;theta=theta0+math.tau*f/parts
                if cylinder_limit:
                    radius=(bottom_radius+top_radius)/2
                    flat0=(radius*math.tau*f/parts,0.);flat1=(flat0[0],H/levels)
                    rb=rt=radius
                else:
                    outer=part.geometry_2d.outer[0]
                    flat0=arc_point(outer,outer.start_angle_deg+outer.sweep_deg*f)
                    flat1=arc_point(inner,inner.start_angle_deg+inner.sweep_deg*(1-f)) if inner else high[0]
                    rb,rt=bottom_radius,top_radius
                guides.append((flat0,flat1,(rb*math.cos(theta),rb*math.sin(theta),z0),
                               (rt*math.cos(theta),rt*math.sin(theta),z0+H/levels)))
            part=with_generators(part,guides,n)
            part=edge_allowances(part,dict(bottom=low,top=high,left=(high[-1],low[0]),right=(low[-1],high[0])),n,material,options,joint_applied=True)
            out.append(part)
    return tuple(out),dict(analytic=True,slant_height_mm=math.hypot(H,R-r),level_count=levels,sector_angle_deg=360*(R-r)/math.hypot(H,R-r)/parts)


def build_pyramid(m,n,material,options,token):
    p=n['parameters'];count=p['n'];R=p['D']/2;H=p['H'];r=p.get('d',0.)/2;apex=H*R/(R-r) if r else H
    if 'Hc' in p:apex=H;H=p['Hc'];r=R*(1-H/apex)
    angle=math.tan(math.radians(p.get('A',0.)))
    bottom=[];top=[]
    for i in range(count+1):
        theta=math.tau*i/count;x=R*math.cos(theta);y=R*math.sin(theta);bottom.append((x,y,0.))
        height=H/(1+angle*x/apex)
        if not 0<height<=apex:raise ValueError('Piramit kesim düzlemi tepeyi veya tabanı geçiyor.')
        f=1-height/apex;top.append((x*f,y*f,height))
    if r==0 and 'Hc' not in p:
        # Fan triangles share one apex; avoid zero upper edges in a two-ring ribbon.
        pts=[(0.,0.)];last=(math.dist(bottom[0],(0.,0.,apex)),0.)
        from .development import triangle_point
        for i in range(count):
            pa=last;pb=triangle_point((0.,0.),pa,math.dist(bottom[i+1],(0.,0.,apex)),math.dist(bottom[i],bottom[i+1]),1)
            pts.append(pa);last=pb
        pts.append(last)
        vertices=[(0.,0.,apex)]+bottom
        from .common import planar_part
        triangles=tuple((0,i+1,i+2) for i in range(count))
        part=planar_part(m['source_id'],vertices,pts,triangles,n,material,options)
        return (part,),dict(face_count=count,apex_height_mm=apex)
    part,error=ribbon(m['source_id'],bottom,top,n,material,options,token)
    return (part,),dict(face_count=count,facet_edge_error_mm=error,apex_height_mm=apex)
