"""Rectangular duct covers and real side-wall paths; open ends are never capped."""
import math
from ..models import (Line2D,Arc2D,Polyline2D,Geometry2D,Mesh3D,SurfacePatch,FrozenMap,MappingPoint,to_data)
from ..geometry import (curve_points,curve_length,contour_points,contour_area,outline,arc_point)
from .common import finish_part,check_cancel
from .development import polygon_part,unit,add,sub,mul,dot
from .source_extrusions import edge_allowances


def reverse(c):
    if isinstance(c,Line2D):return Line2D(c.end,c.start)
    if isinstance(c,Arc2D):return Arc2D(c.center,c.radius,c.start_angle_deg+c.sweep_deg,-c.sweep_deg)
    return Polyline2D(c.points[::-1],c.closed)


def endpoints(c):
    return (c.start,c.end) if isinstance(c,Line2D) else (arc_point(c,c.start_angle_deg),arc_point(c,c.start_angle_deg+c.sweep_deg))


def close_polygon(points):return tuple(Line2D(a,b) for a,b in zip(points,points[1:]+points[:1]))


def rounded_boundary(points,r,open_pairs,skip=()):
    """Fillet internal corners only; duct inlet/outlet rectangles remain unchanged."""
    if not r:return close_polygon(points)
    arcs=[]
    def at_open(p):return any(math.dist(p,q)<1e-6 for pair in open_pairs for q in pair)
    for i,b in enumerate(points):
        a,c=points[i-1],points[(i+1)%len(points)];u=unit(sub(a,b));v=unit(sub(c,b));turn=(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
        if at_open(b) or any(math.dist(b,v)<1e-7 for v in skip) or turn>=-1e-8:arcs.append((b,b,None));continue
        angle=math.acos(max(-1.,min(1.,dot(u,v))));length=r/math.tan(angle/2)
        if length>=min(math.dist(a,b),math.dist(b,c))-1e-6:raise ValueError('Kanal köşe yarıçapı komşu düz kenara sığmıyor.')
        x=add(b,mul(u,length));y=add(b,mul(v,length));center=add(b,mul(unit(add(u,v)),r/math.sin(angle/2)))
        start=math.degrees(math.atan2(x[1]-center[1],x[0]-center[0]));sweep=-math.degrees(math.pi-angle)
        arcs.append((x,y,Arc2D(center,r,start,sweep)))
    curves=[]
    for i,(x,y,arc) in enumerate(arcs):
        if arc:curves.append(arc)
        end=arcs[(i+1)%len(arcs)][0]
        if math.dist(y,end)>1e-8:curves.append(Line2D(y,end))
    return tuple(curves)


def buffered_path(points,width):
    from shapely.geometry import LineString
    from shapely.geometry.polygon import orient
    if any(math.dist(a,b)<=1e-8 for a,b in zip(points,points[1:])):raise ValueError('Kanal eksen yolu sıfır boylu parça içeriyor.')
    poly=orient(LineString(points).buffer(width/2,cap_style='flat',join_style='mitre'),sign=1.)
    if poly.geom_type!='Polygon' or len(poly.interiors):raise ValueError('Kanal yolu kendini kesiyor.')
    def endpair(point,direction):
        d=unit(direction);normal=(-d[1]*width/2,d[0]*width/2);return (add(point,normal),sub(point,normal))
    ends=[endpair(points[0],sub(points[1],points[0])),endpair(points[-1],sub(points[-1],points[-2]))]
    return list(poly.exterior.coords)[:-1],ends


def offset_path(curves,offset):
    out=[]
    for c in curves:
        if isinstance(c,Line2D):
            d=unit(sub(c.end,c.start));delta=(-d[1]*offset,d[0]*offset);out.append(Line2D(add(c.start,delta),add(c.end,delta)))
        else:
            radius=c.radius-(1 if c.sweep_deg>0 else -1)*offset
            if radius<=0:raise ValueError('Kanal genişliği iç kavisi sıfır/negatif yapıyor.')
            out.append(Arc2D(c.center,radius,c.start_angle_deg,c.sweep_deg))
    return out


def curved_footprint(center,width):
    left,right=offset_path(center,width/2),offset_path(center,-width/2)
    a,b=endpoints(right[0])[0],endpoints(left[0])[0];c,d=endpoints(right[-1])[1],endpoints(left[-1])[1]
    return tuple(right+[Line2D(c,d)]+[reverse(x) for x in left[::-1]]+[Line2D(b,a)]),[(a,b),(c,d)]


def branching_plan(p,s):
    arms=[]
    def arm(axis,length,width,main=False):
        d=unit(axis);normal=(-d[1]*width/2,d[0]*width/2);end=mul(d,length)
        if length<=0 or width<=0:raise ValueError('Kol boyu/genişliği pozitif olmalı.')
        arms.append((math.atan2(d[1],d[0])%math.tau,d,sub(end,normal),add(end,normal),main))
    if '-branch' in s:
        arm((-1.,0.),p['A1'],p['W'],True);arm((1.,0.),p['A2'],p['W'],True)
        a=math.radians(p.get('A',90.));arm((math.cos(a),math.sin(a)),p['R'],p['w'])
    else:
        arm((0.,-1.),p['L'],p['W'],True)
        if s.endswith('-180'):pairs=[(-90.,p['B']/2,p['w']),(90.,p['B']/2,p['w'])]
        elif s.endswith('-asymmetric'):pairs=[(-p['A1'],p['R1'],p['w1']),(p['A2'],p['R2'],p['w2'])]
        else:pairs=[(-p['A']/2,p['R'],p['w']),(p['A']/2,p['R'],p['w'])]
        for a,L,w in pairs:
            a=math.radians(a);arm((math.sin(a),math.cos(a)),L,w)
    arms.sort();points=[];ends=[];skip=[]
    for i,(_,d,right,left,main) in enumerate(arms):
        points.extend((right,left));ends.append((right,left))
        _,e,rr,ll,nextmain=arms[(i+1)%len(arms)];den=d[0]*e[1]-d[1]*e[0]
        if abs(den)>1e-10:
            delta=sub(rr,left);u=(delta[0]*e[1]-delta[1]*e[0])/den;corner=add(left,mul(d,u));points.append(corner)
            if '-y' in s and not main and not nextmain:skip.append(corner)
    return rounded_boundary(points,p.get('r',0.),ends,skip),ends


def build_plan(p,s):
    if s=='rectangular-duct-splitter':return splitter_plan(p)
    if s=='rectangular-duct-straight':
        w,L=p['W'],p['L'];points=[(0.,-w/2),(L,-w/2),(L,w/2),(0.,w/2)];return close_polygon(points),[(points[-1],points[0]),(points[1],points[2])]
    if s.startswith('rectangular-duct-reducer'):
        W,w,L,E1,E2=(p[k] for k in ('W','w','L','E1','E2'))
        if E1<0 or E2<0 or E1+E2>=L:raise ValueError('Düz boylar toplamı kanal boyundan küçük olmalı.')
        low0,low1=(0.,0.) if s.endswith('straight-side') else (-W/2,-w/2)
        high0,high1=(W,w) if s.endswith('straight-side') else (W/2,w/2)
        lower=[(0.,low0),(E1,low0),(L-E2,low1),(L,low1)];upper=[(0.,high0),(E1,high0),(L-E2,high1),(L,high1)]
        pts=lower+upper[::-1];pts=[v for i,v in enumerate(pts) if not i or math.dist(v,pts[i-1])>1e-8]
        return close_polygon(pts),[(lower[0],upper[0]),(lower[-1],upper[-1])]
    if s.startswith('rectangular-duct-offset'):
        W,L,X,E1,E2=(p[k] for k in ('W','L','X','E1','E2'));travel=L-E1-E2
        if min(E1,E2)<0 or travel<=0:raise ValueError('Düz uzantılar toplamı boydan küçük olmalı.')
        if s.endswith('-radius') and X:
            a=2*math.atan(abs(X)/travel);radius=(travel*travel+X*X)/(4*abs(X));sign=1 if X>0 else -1
            center=[Line2D((0.,0.),(E1,0.))] if E1 else []
            c1=(E1,sign*radius);arc1=Arc2D(c1,radius,-sign*90,sign*math.degrees(a));mid=endpoints(arc1)[1]
            c2=(mid[0]+radius*math.sin(a),mid[1]-sign*radius*math.cos(a));arc2=Arc2D(c2,radius,sign*90+sign*math.degrees(a),-sign*math.degrees(a))
            center.extend((arc1,arc2))
            if E2:center.append(Line2D((L-E2,X),(L,X)))
            return curved_footprint(center,W)
        points=[(0.,0.)]+([(E1,0.)] if E1 else [])+[(L-E2,X)]+([(L,X)] if E2 else [])
        poly,ends=buffered_path(points,W);return close_polygon(poly),ends
    if s.endswith('-bend'):
        R,A,E1,E2=(p[k] for k in ('R','A','E1','E2'));a=math.radians(A)
        if not 0<A<180 or R<=p['W']/2:raise ValueError('Dirsek açısı (0,180); eksen yarıçapı W/2 üstünde olmalı.')
        arc=Arc2D((E1,R),R,-90.,A);end=endpoints(arc)[1];center=[]
        if E1:center.append(Line2D((0.,0.),(E1,0.)))
        center.append(arc)
        if E2:center.append(Line2D(end,add(end,(E2*math.cos(a),E2*math.sin(a)))))
        return curved_footprint(center,p['W'])
    if s.endswith('-elbow'):
        a=math.radians(p['A']);pts=[(-p['E1'],0.),(0.,0.),(p['E2']*math.cos(a),p['E2']*math.sin(a))]
        poly,ends=buffered_path(pts,p['W']);return close_polygon(poly),ends
    if '-branch' in s or '-y' in s:return branching_plan(p,s)
    raise ValueError('Bu kanal plan yöntemi henüz uygulanmadı: '+s)


def cover_part(identifier,curves,z,n,material,options,token):
    from shapely.geometry import Polygon
    from shapely import constrained_delaunay_triangles
    points=contour_points(curves,options.chord_error_mm,options.max_samples);poly=Polygon(points)
    if not poly.is_valid:raise ValueError('Kanal kapak planı geçersiz.')
    lookup={v:i for i,v in enumerate(points)};triangles=[];area=0.
    for t in constrained_delaunay_triangles(poly).geoms:
        triangles.append(tuple(lookup[tuple(v)] for v in list(t.exterior.coords)[:3]));area+=t.area
    if not math.isclose(area,poly.area,rel_tol=1e-8,abs_tol=1e-5):raise ValueError('Kanal kapak üçgenlemesi eksik.')
    vertices=tuple((x,y,z) for x,y in points);geometry=Geometry2D(curves)
    patch=SurfacePatch('planar_xy',FrozenMap(dict(outer=to_data(curves),holes=(),z=z)))
    return finish_part(identifier,geometry,Mesh3D(vertices,tuple(triangles)),(patch,),contour_area(curves),n,material,options,
                       mappings=tuple(MappingPoint(v,vertices[i],str(i)) for i,v in enumerate(points)))


def wall_part(identifier,path,height,n,material,options,token):
    points=[];flat=[];total=0.;patches=[]
    for c in path:
        check_cancel(token);sampled=curve_points(c,options.chord_error_mm,options.max_samples);length=curve_length(c)
        for i,q in enumerate(sampled):
            if points and i==0:continue
            points.append(q);flat.append(total+length*i/(len(sampled)-1))
        total+=length
        if isinstance(c,Line2D):
            a,b=c.start,c.end
            for v in (((a[0],a[1],0.),(b[0],b[1],0.),(b[0],b[1],height)),((a[0],a[1],0.),(b[0],b[1],height),(a[0],a[1],height))):patches.append(SurfacePatch('triangle',FrozenMap(dict(vertices=v))))
        else:
            startangle=min(c.start_angle_deg,c.start_angle_deg+c.sweep_deg);span=abs(math.radians(c.sweep_deg))
            patches.append(SurfacePatch('cylinder',FrozenMap(dict(radius=c.radius,length=height,theta0=math.radians(startangle),span=span,
                lower=0.,upper=0.,azimuth=0.,origin=(c.center[0],c.center[1],0.),axis=(0.,0.,1.),radial_x=(1.,0.,0.)))))
    if total<=0:raise ValueError('Kanal duvarı sıfır boylu.')
    vertices=[(x,y,z) for x,y in points for z in (0.,height)];triangles=[]
    for i in range(1,len(points)):triangles.extend(((2*i-2,2*i,2*i-1),(2*i,2*i+1,2*i-1)))
    geometry=outline(((0.,0.),(total,0.),(total,height),(0.,height)))
    part=finish_part(identifier,geometry,Mesh3D(tuple(vertices),tuple(triangles)),tuple(patches),total*height,n,material,options)
    from .common import with_generators
    guides=[];count=n['model_options']['helper_divisions']
    for j in range(count+1):
        s=total*j/count;offset=0.
        for curve in path:
            length=curve_length(curve)
            if s<=offset+length+1e-8:
                f=max(0.,min(1.,(s-offset)/length))
                if isinstance(curve,Line2D):q=add(curve.start,mul(sub(curve.end,curve.start),f))
                else:q=arc_point(curve,curve.start_angle_deg+curve.sweep_deg*f)
                guides.append(((s,0.),(s,height),(q[0],q[1],0.),(q[0],q[1],height)));break
            offset+=length
    part=with_generators(part,guides,n)
    bends=[];offset=0.
    def tangent(c,last):
        if isinstance(c,Line2D):return unit(sub(c.end,c.start))
        a=math.radians(c.start_angle_deg+(c.sweep_deg if last else 0.));sign=1 if c.sweep_deg>0 else -1
        return -sign*math.sin(a),sign*math.cos(a)
    for a,b in zip(path,path[1:]):
        offset+=curve_length(a);u,v=tangent(a,True),tangent(b,False)
        if abs(u[0]*v[1]-u[1]*v[0])>1e-9:bends.append(Line2D((offset,0.),(offset,height),f'B{len(bends)+1}'))
    from dataclasses import replace
    part=replace(part,bending_lines=tuple(bends))
    opts=dict(n['model_options']);opts['lap_bottom']=opts['lap_top'];opts['lap_right']=opts['lap_left'];nn=dict(n,model_options=opts)
    part=edge_allowances(part,dict(bottom=((0.,0.),(total,0.)),right=((total,0.),(total,height)),top=((total,height),(0.,height)),left=((0.,height),(0.,0.))),nn,material,options)
    return part


def build_duct(m,n,material,options,token):
    p=n['parameters'];s=m['source_id']
    if s=='rectangular-duct-reducer-offset':return build_variable_duct(m,n,material,options,token)
    curves,ends=build_plan(p,s)
    def is_open(c):
        if not isinstance(c,Line2D):return False
        a,b=endpoints(c)
        return any(min(math.dist(a,x)+math.dist(b,y),math.dist(a,y)+math.dist(b,x))<1e-5 for x,y in ends)
    indices=[i for i,c in enumerate(curves) if is_open(c)]
    if len(indices)!=len(ends):raise ValueError('Kanal açık ağızları plan sınırında korunamıyor; kol boylarını artırın.')
    out=[cover_part(s+'-bottom',curves,0.,n,material,options,token),cover_part(s+'-top',curves,p['H'],n,material,options,token)]
    for j,start in enumerate(indices):
        path=[];k=(start+1)%len(curves)
        while not is_open(curves[k]):path.append(curves[k]);k=(k+1)%len(curves)
        if path:
            if s=='rectangular-duct-splitter' and any(isinstance(c,Arc2D) and c.radius==p['r']+p['w'] for c in path):
                split=next(i for i,c in enumerate(path) if isinstance(c,Arc2D) and c.radius==p['r']+p['w'])
                for k,group in enumerate((path[:split],path[split:])):out.append(wall_part(f'{s}-wall{j+1}-{k+1}',group,p['H'],n,material,options,token))
            else:out.append(wall_part(f'{s}-wall{j+1}',path,p['H'],n,material,options,token))
    expected=int(m['cut_options'][0]['value'].split('_')[0])
    if len(out)!=expected:raise ValueError('Kanal levha sayısı kaynak kesim sözleşmesiyle uyuşmuyor.')
    return tuple(out),dict(real_plate_count=len(out),open_end_count=len(ends),wall_lap_semantics='lap_top on both long wall edges; lap_left at both ends; covers receive no rectangular padding')


def splitter_plan(p):
    W,w,E,L,r,E2=(p[k] for k in ('W','w','E','L','r','E2'));A=p['A'];a=math.radians(A)
    if not 0<w<W or min(E,L,r)<0 or not 0<A<180:raise ValueError('Ayırıcı genişlik/yarıçap/açı ilişkisi geçersiz.')
    center=(E,W+r);outer=Arc2D(center,r+w,-90.,A);inner=Arc2D(center,r,-90.,A)
    oe,ie=endpoints(outer)[1],endpoints(inner)[1];delta=(E2*math.cos(a),E2*math.sin(a));of,inf=add(oe,delta),add(ie,delta)
    curves=[Line2D((0.,0.),(E+L,0.)),Line2D((E+L,0.),(E+L,W-w)),Line2D((E+L,W-w),(E,W-w)),outer]
    if E2:curves.append(Line2D(oe,of))
    curves.append(Line2D(of,inf))
    if E2:curves.append(Line2D(inf,ie))
    curves.extend((reverse(inner),Line2D((E,W),(0.,W)),Line2D((0.,W),(0.,0.))))
    return tuple(curves),[((0.,0.),(0.,W)),((E+L,0.),(E+L,W-w)),(of,inf)]


def build_variable_duct(m,n,material,options,token):
    from .development import ribbon
    p=n['parameters'];L=p['L'];Y=p['Y'];W1,W2=p['W1'],p['W2']
    for a,b in [('T1','T2'),('B1','B2')]:
        if min(p[a],p[b])<0 or p[a]+p[b]>=L:raise ValueError('Üst/alt düz boylar toplamı kanal boyundan küçük olmalı.')
    def height(x,top):
        e1,e2=(p['T1'],p['T2']) if top else (p['B1'],p['B2']);z0=p['H1'] if top else 0.;z1=Y+p['H2'] if top else Y
        return z0+(z1-z0)*max(0.,min(1.,(x-e1)/(L-e1-e2)))
    def width(x):return W1+(W2-W1)*x/L
    breaks=sorted(set((0.,L,p['T1'],L-p['T2'],p['B1'],L-p['B2'])))
    if min(height(x,True)-height(x,False) for x in breaks)<=0:raise ValueError('Kanal üst ve alt sacları kesişiyor.')
    out=[];error=0.
    for top in (False,True):
        pts0=[(x,-width(x)/2,height(x,top)) for x in breaks];pts1=[(x,width(x)/2,height(x,top)) for x in breaks]
        part,e=ribbon(m['source_id']+('-top' if top else '-bottom'),pts0,pts1,n,material,options,token)
        out.append(part);error=max(error,e)
    for side in (-1,1):
        low=[(x,side*width(x)/2,height(x,False)) for x in breaks];high=[(x,side*width(x)/2,height(x,True)) for x in breaks]
        part=polygon_part(m['source_id']+f'-wall{side}',low+high[::-1],n,material,options,token)
        # Use the authoritative projection. A downward bottom kink can make
        # polygon_part choose the opposite normal to a low-edge/high-point basis.
        projection={point.assembled:point.developed for point in part.mappings}
        low2=[projection[v] for v in low];high2=[projection[v] for v in high]
        groups=dict(bottom=low2,top=high2[::-1],left=(high2[0],low2[0]),right=(low2[-1],high2[-1]))
        # polygon_part uses this same first-edge basis; reverse if its orientation was inverted.
        if contour_area(outline(low2+high2[::-1]).outer)<0:groups={k:tuple(reversed(v)) for k,v in groups.items()}
        opts=dict(n['model_options']);opts['lap_bottom']=opts['lap_top'];opts['lap_right']=opts['lap_left'];nn=dict(n,model_options=opts)
        out.append(edge_allowances(part,groups,nn,material,options))
    return tuple(out),dict(real_plate_count=4,facet_edge_error_mm=error,method='piecewise planar top/bottom plates plus two exact planar side walls')
