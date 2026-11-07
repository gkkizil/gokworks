"""Cylindrical/profile extrusions, planar cuts, plate openings and prisms."""
from dataclasses import replace
import math
from .development import circle,stadium,polygon_profile,adaptive
from .common import add,mul,finish_part
from ..models import (Geometry2D,Polyline2D,Line2D,Mesh3D,MappingPoint,TrueLength,FrozenMap,SurfacePatch)
from ..geometry import outline,contour_area


def edge_allowances(part,groups,n,material,options,*,joint_applied=False):
    """Add strips to named nominal edges; no enclosing rectangle substitution."""
    from shapely.geometry import Polygon,LineString
    from shapely.ops import unary_union
    opts=n['model_options'];nominal=part.geometry_2d
    joint=n['joint_options']['overlap'] if n['joint_options']['kind']=='lap' and not joint_applied else 0.
    if not any(opts.get('lap_'+k,0) for k in groups) and not opts.get('strip_lap',0) and not joint:return part
    from ..geometry import contour_points
    poly=Polygon(contour_points(nominal.outer,options.chord_error_mm,options.max_samples),
                 [contour_points(h,options.chord_error_mm,options.max_samples) for h in nominal.holes])
    shapes=[poly];seams=list(part.seams)
    for key,points in groups.items():
        amount=opts.get('lap_'+key,0.)+(opts.get('strip_lap',0.)+joint if key=='right' else 0.)
        if not amount:continue
        line=LineString(points)
        if key=='right' and joint_applied and n['joint_options']['kind']=='lap':
            # The analytic cone builder has already added the joint strip.
            # Extra edge/strip pay starts at that strip's outer seam, rather
            # than disappearing inside the material which is already present.
            line=line.offset_curve(-n['joint_options']['overlap'],join_style='mitre')
        shapes.append(line.buffer(-amount,single_sided=True,cap_style='flat',join_style='mitre'))
        seams.extend(Line2D(a,b) for a,b in zip(points,points[1:]) if math.dist(a,b)>options.geometry_tolerance_mm)
    combined=unary_union(shapes)
    if combined.geom_type!='Polygon' or not combined.is_valid:raise ValueError('Kenar payları tek geçerli kontur üretmiyor.')
    from shapely.geometry.polygon import orient
    combined=orient(combined,sign=1.)
    geometry=Geometry2D((Polyline2D(tuple(combined.exterior.coords)[:-1],True),),tuple((Polyline2D(tuple(r.coords)[:-1],True),) for r in combined.interiors))
    rebuilt=finish_part(part.id,geometry,part.mesh_3d,(),part.metrics.net_area_mm2,n,material,options,
                        construction=part.construction_lines,seams=seams,mappings=part.mappings,lengths=part.true_lengths)
    return replace(rebuilt,code=part.code,quantity=part.quantity,bending_lines=part.bending_lines)


def extrude(identifier,profile,bottom,top,n,material,options,token=None,*,start=0.,span=None,origin=(0.,0.,0.),
            axis=(0.,0.,1.),radial_x=(1.,0.,0.),radial_y=(0.,1.,0.)):
    """True arc-length extrusion development. profile parameter is arc length."""
    span=profile.perimeter if span is None else span
    def values(s):
        x,y=profile.point(s);lo=bottom(x,y);hi=top(x,y)
        if hi-lo<=options.geometry_tolerance_mm:raise ValueError('Kesimler kesişiyor; her üreteçte yükseklik pozitif olmalı.')
        return (s-start,lo,hi,x,y)
    breaks=[q+period*profile.perimeter for period in range(-2,4) for q in profile.breaks]
    # Quarter-turn seeds catch periodic extrema, adaptive tests control measured residual.
    breaks.extend(start+span*i/16 for i in range(17))
    sampled,residual=adaptive(values,start,start+span,options.chord_error_mm,options.max_samples,breaks,token)
    low=[];high=[];vertices=[];triangles=[];maps=[];lengths=[]
    for i,(s,(u,lo,hi,x,y)) in enumerate(sampled):
        low.append((u,lo));high.append((u,hi));radial=add(mul(radial_x,x),mul(radial_y,y));v0=add(origin,add(radial,mul(axis,lo)));v1=add(origin,add(radial,mul(axis,hi)))
        vertices.extend((v0,v1));maps.extend((MappingPoint(low[-1],v0,str(i)+'.0'),MappingPoint(high[-1],v1,str(i)+'.1')))
        if i:triangles.extend(((2*i-2,2*i,2*i-1),(2*i,2*i+1,2*i-1)))
    for i in range(n['model_options']['helper_divisions']+1):
        s=start+span*i/n['model_options']['helper_divisions'];x,y=profile.point(s);lo=bottom(x,y);hi=top(x,y)
        v0=add(origin,add(add(mul(radial_x,x),mul(radial_y,y)),mul(axis,lo)));v1=add(v0,mul(axis,hi-lo))
        lengths.append(TrueLength(f'{identifier}.G{i}',v0,v1,hi-lo))
    points=low+high[::-1];geometry=outline(points)
    construction=tuple(Line2D((span*i/n['model_options']['helper_divisions'],bottom(*profile.point(start+span*i/n['model_options']['helper_divisions']))),
                              (span*i/n['model_options']['helper_divisions'],top(*profile.point(start+span*i/n['model_options']['helper_divisions']))),f'G{i}') for i in range(1,n['model_options']['helper_divisions']))
    part=finish_part(identifier,geometry,Mesh3D(tuple(vertices),tuple(triangles)),(),contour_area(geometry.outer),n,material,options,
        construction=construction,seams=(Line2D(high[0],low[0]),Line2D(low[-1],high[-1])),mappings=maps,lengths=lengths)
    from .surface_patches import extrusion_patches
    part=replace(part,surface_patches=extrusion_patches(profile,geometry,start,
        origin=origin,axis=axis,radial_x=radial_x,radial_y=radial_y))
    part=edge_allowances(part,dict(bottom=low,right=(low[-1],high[-1]),top=high[::-1],left=(high[0],low[0])),n,material,options)
    if profile.forming and not any(n['model_options'].get(k,0.) for k in ('lap_top','lap_bottom','lap_left','lap_right','strip_lap')) and n['joint_options']['kind']=='butt':
        part=replace(part,forming_basis=FrozenMap(dict(profile.forming,start_mm=start,span_mm=span)))
    return part,residual


def cut_layout(m,n,profile):
    cut=n['model_options']['cut_type'];parts={'2_parts':2,'2_parts_90_degrees':2,'2_parts_180_degrees':2,'4_parts':4}.get(cut,1)
    start=n['parameters'].get('seam',n['seam_options']['start_angle_deg'])/360*profile.perimeter
    if 'on_radius' in cut or '180_degrees' in cut:start+=profile.perimeter/4
    # The midpoint of the first stadium flat vs first semicircle, using breakpoints.
    if m['family']=='Oval boru':
        half=math.pi*n['parameters']['W']/2
        start=(half+(n['parameters']['L']-n['parameters']['W'])/2) if 'flat' in cut or '90_degrees' in cut else half/2
    return parts,start


def build_cylinder(m,n,material,options,token):
    p=n['parameters'];identifier=m['source_id'];profile=circle(p['D']) if 'D' in p else stadium(p['L'],p['W']);radius=p.get('D',p.get('W',0))/2
    bottom=lambda x,y:0.;top=lambda x,y:p.get('H',0.)
    if identifier in ('cylinder-top-angle','cylinder-top-angle-side','cylinder-angled-top'):
        if identifier=='cylinder-angled-top':height=(p['H1']+p['H2'])/2;slope=p['_plane_slope']
        else:
            slope=math.tan(math.radians(p['A']));height=p.get('_center_height',p['H'])
        top=lambda x,y:height+x*slope
    elif identifier=='cylinder-cut-both-ends':
        a,b=map(lambda k:math.tan(math.radians(p[k])),('A','B'));turn=math.radians(p['turn'])
        top=lambda x,y:p['H']+a*x
        bottom=lambda x,y:b*(x*math.cos(turn)+y*math.sin(turn))
    elif identifier.startswith('cylinder-ridge-top'):
        x0=p.get('X',0.);a,b=math.tan(math.radians(p['A1'])),math.tan(math.radians(p['A2']))
        if abs(x0)>=radius:raise ValueError('Mahya silindir kesitinin içinde olmalı.')
        top=lambda x,y:p['H']+min((x-x0)*a,-(x-x0)*b)
    elif identifier=='cylinder-round-top':
        if p['R']<radius:raise ValueError('Üst yay yarıçapı boru yarıçapından küçük olamaz.')
        top=lambda x,y:p['H']-p['R']+math.sqrt(max(0.,p['R']**2-x*x))
    elif identifier.startswith('oval-cylinder'):
        profile=stadium(p['L'],p['W']);along='along' in identifier or identifier.endswith('-turned');a=math.tan(math.radians(p.get('A',0.)))
        top=lambda x,y:p['H']+a*(x if along else y)
        if 'base' in identifier:
            b=math.tan(math.radians(p['B']));basealong=along and not identifier.endswith('turned');bottom=lambda x,y:-b*(x if basealong else y)
    parts,start=cut_layout(m,n,profile);out=[];residual=0.
    for i in range(parts):
        part,e=extrude(f'{identifier}-{i+1:02}',profile,bottom,top,n,material,options,token,start=start+profile.perimeter*i/parts,span=profile.perimeter/parts)
        if identifier=='cylinder' and n['joint_options']['kind']=='butt' and not any(n['model_options'].get(k,0.) for k in ('lap_top','lap_bottom','lap_left','lap_right','strip_lap')):
            patch=SurfacePatch('cylinder',FrozenMap(dict(radius=radius,length=p['H'],theta0=(start+profile.perimeter*i/parts)/radius,
                span=profile.perimeter/parts/radius,lower=0.,upper=0.,azimuth=0.,origin=(0.,0.,0.),axis=(0.,0.,1.),radial_x=(1.,0.,0.))))
            part=replace(part,surface_patches=(patch,))
        out.append(part);residual=max(residual,e)
    return tuple(out),dict(measured_curve_residual_mm=residual,curve_error_certified=False,perimeter_mm=profile.perimeter)


def build_prism(m,n,material,options,token):
    p=n['parameters'];r=p['D']/2;count=p['n'];pts=[(r*math.cos(math.tau*i/count),r*math.sin(math.tau*i/count)) for i in range(count)]
    profile=polygon_profile(pts)
    a=math.tan(math.radians(p.get('A',0.)));b=math.tan(math.radians(p.get('B',0.)))
    part,e=extrude(m['source_id'],profile,lambda x,y:-x*b,lambda x,y:p['H']+x*a,n,material,options,token)
    # Polygon corners are real bends. Adaptive curved-boundary sampling is not bend count.
    bends=[]
    for s in profile.breaks[1:-1]:
        x,y=profile.point(s);bends.append(Line2D((s,-x*b),(s,p['H']+x*a),f'B{len(bends)+1}'))
    patches=[]
    if not any(n['model_options'].get(k,0.) for k in ('lap_top','lap_bottom','lap_left','lap_right','strip_lap')) and n['joint_options']['kind']=='butt':
        for x,y in zip(pts,pts[1:]+pts[:1]):
            v=((x[0],x[1],-x[0]*b),(y[0],y[1],-y[0]*b),(y[0],y[1],p['H']+y[0]*a),(x[0],x[1],p['H']+x[0]*a))
            for tri in ((0,1,2),(0,2,3)):patches.append(SurfacePatch('triangle',FrozenMap(dict(vertices=tuple(v[j] for j in tri)))))
    return (replace(part,bending_lines=tuple(bends),surface_patches=tuple(patches)),),dict(measured_curve_residual_mm=e,face_count=count,side_length_mm=2*r*math.sin(math.pi/count))
