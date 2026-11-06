"""Measured curve sampling and triangle-strip developments from actual 3D edges.

Faceted developments represent piecewise planar material. They never assert
isometry to a doubly curved smooth loft. The triangulation is authoritative,
independent of the coarser display mesh.
"""
from dataclasses import dataclass,replace,field
import math
from ..geometry import outline,contour_area
from ..models import (Line2D,Mesh3D,FrozenMap,SurfacePatch,MappingPoint,TrueLength)
from .common import (add,sub,mul,dot,cross,norm,check_cancel,finish_part)


def unit(v):
    d=norm(v)
    if d<1e-12:raise ValueError('Sıfır yön vektörü.')
    return mul(v,1/d)


def basis(axis):
    a=unit(axis);x=unit(cross((0.,1.,0.) if abs(a[1])<.9 else (1.,0.,0.),a))
    return a,x,cross(a,x)


def triangle_point(a,b,ra,rb,side=1):
    d=math.dist(a,b)
    if d<=1e-12:raise ValueError('Üçgen kenarı sıfır.')
    if min(ra,rb)<0 or not all(math.isfinite(v) for v in (d,ra,rb)):raise ValueError('Üçgen kenarları sonlu ve pozitif olmalı.')
    longest,middle,shortest=sorted((d,ra,rb),reverse=True)
    gap=shortest-(longest-middle)
    if gap < -16*math.ulp(longest):raise ValueError('Üçgen eşitsizliği geçersiz.')
    # Kahan's rearrangement of Heron's formula avoids subtracting almost
    # equal squared lengths: the old height collapsed slender rectangles
    # into triangles and silently lost half their material area.
    f1=longest+(middle+shortest);f2=max(0.,gap)
    f3=shortest+(longest-middle);f4=longest+(middle-shortest)
    y=.5*math.sqrt((f1/d)*f2)*math.sqrt((f3/d)*f4)*side
    x=(ra-rb)*(ra+rb)/(2*d)+d/2
    if not math.isfinite(x) or not math.isfinite(y):raise ValueError('Üçgen hesabı sayısal aralığı aştı.')
    u=((b[0]-a[0])/d,(b[1]-a[1])/d)
    return (a[0]+x*u[0]-y*u[1],a[1]+x*u[1]+y*u[0])


def adaptive(function,start,end,tolerance,maximum,breaks=(),token=None):
    """Quarter/midpoint tested recursive chord approximation with measured residual.

    Not a global derivative certificate. The quality contract reports a measured
    residual and forbids quoting it as certified manufacturing accuracy.
    """
    seeds=[]
    for v in sorted(set((start,end,*(v for v in breaks if start<v<end)))):
        if not seeds or v-seeds[-1]>1e-11*max(1.,end-start):seeds.append(v)
    seeds[-1]=end
    out=[(start,function(start))];worst=0.
    def interval(a,pa,b,pb,depth=0):
        nonlocal worst
        check_cancel(token)
        tests=[]
        for f in (.25,.5,.75):
            t=a+(b-a)*f;p=function(t);linear=tuple(x+(y-x)*f for x,y in zip(pa,pb));tests.append((t,p,math.dist(p,linear)))
        err=max(v[2] for v in tests)
        if err>tolerance:
            if depth>=24 or len(out)>=maximum:raise ValueError('Eğri örnekleme bütçesi/toleransı aşıldı.')
            mid,p,_=tests[1];interval(a,pa,mid,p,depth+1);interval(mid,p,b,pb,depth+1)
        else:
            if len(out)>=maximum+1:raise ValueError('Eğri örnekleme üst sınırı aşıldı.')
            worst=max(worst,err);out.append((b,pb))
    for a,b in zip(seeds,seeds[1:]):interval(a,function(a),b,function(b))
    return tuple(out),worst


@dataclass(frozen=True)
class Profile:
    perimeter: float
    point: object
    breaks: tuple = ()
    flat_seams: tuple = ()
    radius_seams: tuple = ()
    forming: FrozenMap = field(default_factory=FrozenMap)


def circle(d):
    if d<=0:raise ValueError('Çap pozitif olmalı.')
    r=d/2;length=math.tau*r
    return Profile(length,lambda s:(r*math.cos(s/r),r*math.sin(s/r)),tuple(length*i/4 for i in range(5)),
                   forming=FrozenMap(dict(kind='circle',radius_mm=r)))


def stadium(length,width):
    if not length>=width>0:raise ValueError('Oval kesitte boy ≥ genişlik > 0 olmalı.')
    a=(length-width)/2;r=width/2;half=math.pi*r;perimeter=2*half+4*a
    def point(s):
        s%=perimeter
        if s<half:return a+r*math.cos(-math.pi/2+s/r),r*math.sin(-math.pi/2+s/r)
        s-=half
        if s<2*a:return a-s,r
        s-=2*a
        if s<half:return -a+r*math.cos(math.pi/2+s/r),r*math.sin(math.pi/2+s/r)
        s-=half
        return -a+s,-r
    return Profile(perimeter,point,tuple(sorted(set((0,half,half+2*a,2*half+2*a,perimeter)))),
                   (half+a,2*half+3*a),(half/2,1.5*half+2*a),
                   FrozenMap(dict(kind='stadium',radius_mm=r,straight_length_mm=2*a)))


def polygon_profile(points,radius=0.):
    pts=[tuple(p) for p in points]
    area=sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(pts,pts[1:]+pts[:1]))/2
    if area<0:pts.reverse()
    elements=[]
    if radius<0:raise ValueError('Köşe yarıçapı negatif olamaz.')
    if not radius:
        for a,b in zip(pts,pts[1:]+pts[:1]):elements.append((math.dist(a,b),lambda f,a=a,b=b:tuple(x+f*(y-x) for x,y in zip(a,b))))
    else:
        corners=[]
        for i,b in enumerate(pts):
            a,c=pts[i-1],pts[(i+1)%len(pts)];u=unit(sub(a,b));v=unit(sub(c,b));ang=math.acos(max(-1.,min(1.,dot(u,v))))
            cut=radius/math.tan(ang/2)
            if cut>=min(math.dist(a,b),math.dist(b,c))/2:raise ValueError('Köşe yarıçapı kenara sığmıyor.')
            aa=add(b,mul(u,cut));bb=add(b,mul(v,cut));center=add(b,mul(unit(add(u,v)),radius/math.sin(ang/2)))
            start=math.atan2(aa[1]-center[1],aa[0]-center[0]);sweep=math.pi-ang
            corners.append((aa,bb,center,start,sweep))
        for i,(a,b,c,start,sweep) in enumerate(corners):
            elements.append((radius*sweep,lambda f,c=c,start=start,sweep=sweep:(c[0]+radius*math.cos(start+sweep*f),c[1]+radius*math.sin(start+sweep*f))))
            e=corners[(i+1)%len(corners)][0]
            if math.dist(b,e)>1e-8:elements.append((math.dist(b,e),lambda f,a=b,b=e:tuple(x+f*(y-x) for x,y in zip(a,b))))
    lengths=[0.]
    for distance,_ in elements:lengths.append(lengths[-1]+distance)
    def point(s):
        s%=lengths[-1]
        for i,(d,fn) in enumerate(elements):
            if s<=lengths[i+1]+1e-10:return fn(max(0.,min(1.,(s-lengths[i])/d)))
        return elements[-1][1](1.)
    flats=tuple((lengths[i]+lengths[i+1])/2 for i in range(len(elements)) if not radius or i%2==1)
    radii=tuple((lengths[i]+lengths[i+1])/2 for i in range(len(elements)) if radius and i%2==0)
    return Profile(lengths[-1],point,tuple(lengths),flats,radii)


def rectangle(w,l,r=0):
    if min(w,l)<=0:raise ValueError('Dikdörtgen ölçüleri pozitif olmalı.')
    return polygon_profile([(-l/2,-w/2),(l/2,-w/2),(l/2,w/2),(-l/2,w/2)],r)


def ellipse(length,width):
    if min(length,width)<=0:raise ValueError('Elips eksenleri pozitif olmalı.')
    # Parameter is angle, not arc length. Only loft sampling uses this profile.
    return Profile(math.tau,lambda s:(length/2*math.cos(s),width/2*math.sin(s)),tuple(math.pi*i/2 for i in range(5)),
                   (math.pi/2,3*math.pi/2),(0.,math.pi))


def polygon_part(identifier,vertices,n,material,options,token=None):
    """Exactly planar polygon; triangulated using constrained interior triangles."""
    from shapely.geometry import Polygon
    from shapely import constrained_delaunay_triangles
    check_cancel(token)
    a=vertices[0];x=unit(sub(vertices[1],a));normal=None
    for v in vertices[2:]:
        cr=cross(x,sub(v,a))
        if norm(cr)>1e-9:normal=unit(cr);break
    if normal is None:raise ValueError('Düz levha dejenere.')
    y=cross(normal,x);pts=[(dot(sub(v,a),x),dot(sub(v,a),y)) for v in vertices]
    if max(abs(dot(sub(v,a),normal)) for v in vertices)>options.geometry_tolerance_mm:raise ValueError('Levha köşeleri aynı düzlemde değil.')
    poly=Polygon(pts)
    if not poly.is_valid or poly.area<=0:raise ValueError('Düz levha konturu geçersiz.')
    if contour_area(outline(pts).outer)<0:pts.reverse();vertices=list(reversed(vertices))
    verts=list(vertices);xy=list(pts);triangles=[]
    for tri in constrained_delaunay_triangles(Polygon(xy)).geoms:
        
        idx=[]
        for q in list(tri.exterior.coords)[:3]:idx.append(min(range(len(xy)),key=lambda i:math.dist(q,xy[i])))
        triangles.append(tuple(idx))
    from .common import planar_part
    return planar_part(identifier,tuple(verts),tuple(xy),tuple(triangles),n,material,options)


def ribbon(identifier,lower,upper,n,material,options,token=None,diagonal=1):
    """Unfold a chain of triangles; all its 3D triangle edges preserved exactly."""
    if len(lower)!=len(upper) or len(lower)<2:raise ValueError('Şerit sınır örnekleri uyuşmuyor.')
    pairs=[];tolerance=options.geometry_tolerance_mm
    for a,b in zip(lower,upper):
        if not pairs or math.dist(a,pairs[-1][0])>tolerance or math.dist(b,pairs[-1][1])>tolerance:pairs.append((a,b))
    lower,upper=map(list,zip(*pairs))
    if len(lower)<2:raise ValueError('Geçişte değişen kesim kenarı kalmadı.')
    vertices=[v for pair in zip(lower,upper) for v in pair];flat=[(0.,0.),(0.,math.dist(lower[0],upper[0]))];triangles=[]
    canonical=list(range(len(vertices)))
    for i in range(1,len(lower)):
        check_cancel(token)
        a,b=2*i-2,2*i-1;c,d=2*i,2*i+1
        same_lower=math.dist(vertices[c],vertices[a])<=tolerance
        same_upper=math.dist(vertices[d],vertices[b])<=tolerance
        if same_lower:canonical[c]=canonical[a]
        if same_upper:canonical[d]=canonical[b]
        if diagonal==1:
            pc=flat[a] if same_lower else triangle_point(flat[a],flat[b],math.dist(vertices[c],vertices[a]),math.dist(vertices[c],vertices[b]),-1)
            flat.append(pc)
            pd=flat[b] if same_upper else triangle_point(flat[c],flat[b],math.dist(vertices[d],vertices[c]),math.dist(vertices[d],vertices[b]),-1)
            flat.append(pd);faces=((a,c,b),(c,d,b))
        else:
            pd=flat[b] if same_upper else triangle_point(flat[a],flat[b],math.dist(vertices[d],vertices[a]),math.dist(vertices[d],vertices[b]),-1)
            pc=flat[a] if same_lower else triangle_point(flat[a],pd,math.dist(vertices[c],vertices[a]),math.dist(vertices[c],vertices[d]),-1)
            flat.extend((pc,pd));faces=((a,c,d),(a,d,b))
        for face in faces:
            face=tuple(canonical[j] for j in face)
            if len(set(face))==3:triangles.append(face)
    points=flat[::2]+flat[1::2][::-1]
    points=[v for i,v in enumerate(points) if not i or math.dist(v,points[i-1])>tolerance]
    if math.dist(points[0],points[-1])<=tolerance:points.pop()
    if contour_area(outline(points).outer)<0:points.reverse()
    geometry=outline(points)
    patches=tuple(SurfacePatch('triangle',FrozenMap(dict(vertices=tuple(vertices[j] for j in tri)))) for tri in triangles)
    helpers=n['model_options']['helper_divisions']
    indices=tuple(sorted(set(round(i*(len(lower)-1)/helpers) for i in range(helpers+1))))
    lengths=tuple(TrueLength(f'{identifier}.G{j}',lower[i],upper[i],math.dist(lower[i],upper[i])) for j,i in enumerate(indices))
    construction=tuple(Line2D(flat[2*i],flat[2*i+1],f'G{j}') for j,i in enumerate(indices) if i not in (0,len(lower)-1))
    adjacency={}
    for tri in triangles:
        a,b,c=(vertices[i] for i in tri);normal=unit(cross(sub(b,a),sub(c,a)))
        for aa,bb in zip(tri,tri[1:]+tri[:1]):adjacency.setdefault(tuple(sorted((aa,bb))),[]).append(normal)
    bends=[]
    for (a,b),normals in adjacency.items():
        if len(normals)==2 and norm(cross(normals[0],normals[1]))>1e-10:
            bends.append(Line2D(flat[a],flat[b],f'B{len(bends)+1}'))
    maps=tuple(MappingPoint(q,v,str(i)) for i,(q,v) in enumerate(zip(flat,vertices)))
    edge_error=max(abs(math.dist(vertices[a],vertices[b])-math.dist(flat[a],flat[b])) for tri in triangles for a,b in zip(tri,tri[1:]+tri[:1]))
    if edge_error>tolerance:raise ValueError('Açınım üçgen kenarlarındaki sayısal hata geometri toleransını aşıyor.')
    part=finish_part(identifier,geometry,Mesh3D(tuple(vertices),tuple(triangles)),patches,contour_area(geometry.outer),n,material,options,
                     construction=construction,mappings=maps,lengths=lengths)
    return replace(part,bending_lines=tuple(bends)),edge_error
