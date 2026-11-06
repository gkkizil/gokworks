"""Metric distortion and bounded spring-energy mesh relaxation (not plasticity/FEA)."""
import math

from ..shapes.common import check_cancel


def _area(points, tri):
    a, b, c = (points[i] for i in tri)
    return ((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2


def edges_of(triangles):
    return sorted({tuple(sorted((a, b))) for tri in triangles for a, b in zip(tri, tri[1:]+tri[:1])})


def analyze_mesh(vertices, triangles, flat):
    if len(vertices) != len(flat) or not triangles:
        raise ValueError('3D/2D düğüm sayısı uyuşmuyor veya üçgen yok.')
    if any(len(v) != 3 or any(not math.isfinite(c) for c in v) for v in vertices) or any(
            len(v) != 2 or any(not math.isfinite(c) for c in v) for v in flat):
        raise ValueError('Mesh koordinatları sonlu 3D/2D noktalar olmalı.')
    if any(len(tri) != 3 or len(set(tri)) != 3 or any(type(i) is not int or not 0 <= i < len(vertices) for i in tri) for tri in triangles):
        raise ValueError('Mesh üçgen indeksleri geçersiz.')
    rows = []
    for a, b in edges_of(triangles):
        world = math.dist(vertices[a], vertices[b]); developed = math.dist(flat[a], flat[b])
        if min(world, developed) <= 1e-12: raise ValueError('Mesh kenarı dejenere.')
        rows.append(dict(edge=(a,b), length_3d_mm=world, length_2d_mm=developed,
                         unfolding_strain=developed/world-1, required_forming_strain=world/developed-1))
    areas = []
    for tri in triangles:
        a, b, c = (vertices[i] for i in tri)
        u = tuple(y-x for x,y in zip(a,b)); v = tuple(y-x for x,y in zip(a,c))
        world = math.sqrt(sum((u[i]*v[j]-u[j]*v[i])**2 for i,j in ((0,1),(0,2),(1,2))))/2
        planar = abs(_area(flat,tri))
        if min(world,planar) <= 1e-15: raise ValueError('Mesh üçgen alanı dejenere.')
        areas.append(dict(triangle=tri, area_3d_mm2=world, area_2d_mm2=planar, area_change_ratio=planar/world-1))
    return dict(status='GEOMETRIC_DISTORTION', edges=rows, triangles=areas,
                max_abs_edge_strain=max(abs(r['unfolding_strain']) for r in rows),
                rms_edge_strain=math.sqrt(sum(r['unfolding_strain']**2 for r in rows)/len(rows)),
                max_abs_area_change_ratio=max(abs(a['area_change_ratio']) for a in areas),
                total_area_change_ratio=sum(a['area_2d_mm2'] for a in areas)/sum(a['area_3d_mm2'] for a in areas)-1,
                plastic_strain=None, thickness_change_mm=None,
                interpretation='Geometrik metrik farkı; plastik deformasyon, incelme veya şekillendirilebilirlik onayı değildir.')


def relax_mesh(vertices, triangles, flat, *, iterations=200, cancel_token=None):
    """Minimize sum((flat edge/3D edge)-1)^2; pin two points, reject inverted triangles."""
    if type(iterations) is not int or not 1 <= iterations <= 500 or len(vertices)>5000:
        raise ValueError('Mesh optimizasyon bütçesi: 1–500 iterasyon, en çok 5000 düğüm.')
    analyze_mesh(vertices, triangles, flat)
    edges = [(a,b,math.dist(vertices[a],vertices[b])) for a,b in edges_of(triangles)]
    points = [tuple(p) for p in flat]
    pinned = {0, next(i for i,p in enumerate(points) if math.dist(points[0],p)>1e-10)}
    signs = [1 if _area(points,tri)>0 else -1 for tri in triangles]
    def energy(pts): return sum((math.dist(pts[a],pts[b])/length-1)**2 for a,b,length in edges)
    initial = previous = energy(points); history=[initial]; accepted=0;converged=False
    for iteration in range(iterations):
        check_cancel(cancel_token)
        gradient = [[0.,0.] for _ in points]
        for a,b,length in edges:
            dx,dy = points[a][0]-points[b][0],points[a][1]-points[b][1]
            distance=math.hypot(dx,dy)
            factor=2*(distance-length)/(length*length*max(distance,1e-15))
            for j,value in enumerate((factor*dx,factor*dy)):
                gradient[a][j]+=value;gradient[b][j]-=value
        magnitude=max(math.hypot(*g) for i,g in enumerate(gradient) if i not in pinned)
        if magnitude<1e-13:converged=True;break
        step=min(length for a,b,length in edges)*.1/magnitude
        for backtrack in range(30):
            candidate=[p if i in pinned else tuple(p[j]-step*gradient[i][j] for j in range(2)) for i,p in enumerate(points)]
            value=energy(candidate)
            if value<previous and all(sign*_area(candidate,tri)>1e-15 for sign,tri in zip(signs,triangles)):break
            step*=.5
        else:break
        points=candidate;history.append(value);accepted+=1
        if previous-value<max(1e-18,initial*1e-10):previous=value;converged=True;break
        previous=value
    return tuple(points),dict(method='edge_metric_gradient_descent_with_no_flip_line_search', iterations=accepted,
                              initial_energy=initial, final_energy=previous, energy_history=history,
                              converged=previous<1e-18 or converged,
                              production_process_verified=False)


def relax_part(part,n,material,options,token=None):
    """Relax one simply connected mapped patch, preserving the 3D reference and cuts.

    Does not sew unrelated panels, bridge holes, move seams to other surfaces,
    or infer a plastic strain model. Unsupported topologies are rejected.
    """
    from collections import Counter
    from dataclasses import replace
    from shapely.geometry import Polygon
    from ..geometry import outline,contour_area
    from ..models import Line2D,Polyline2D
    from ..shapes.common import finish_part
    verts=part.mesh_3d.vertices;triangles=part.mesh_3d.triangles;maps=part.mappings
    if part.geometry_2d.holes or len(maps)!=len(verts) or not verts or any(math.dist(m.assembled,v)>1e-7 for m,v in zip(maps,verts)):
        raise ValueError('Mesh optimizasyonu deliksiz, bire bir eşlenmiş tek yüzey yaması gerektirir.')
    flat=tuple(m.developed for m in maps)
    if len(set(flat))!=len(flat):raise ValueError('Çakışık/dikişte yinelenen mesh düğümleri otomatik birleştirilmez.')
    counts=Counter(tuple(sorted((a,b))) for tri in triangles for a,b in zip(tri,tri[1:]+tri[:1]))
    if any(count>2 for count in counts.values()):raise ValueError('Mesh manifold değil.')
    neighbors={}
    for (a,b),count in counts.items():
        if count==1:neighbors.setdefault(a,[]).append(b);neighbors.setdefault(b,[]).append(a)
    if not neighbors or any(len(v)!=2 for v in neighbors.values()):raise ValueError('Mesh dış sınırı tek kapalı halka değil.')
    loop=[min(neighbors)];previous=None;current=loop[0]
    while True:
        next_node=next(v for v in neighbors[current] if v!=previous)
        if next_node==loop[0]:break
        if next_node in loop:raise ValueError('Mesh sınırı kendisiyle kesişiyor.')
        loop.append(next_node);previous,current=current,next_node
    if len(loop)!=len(neighbors):raise ValueError('Birden fazla sınır halkası desteklenmiyor.')
    polygon=Polygon([flat[i] for i in loop])
    if not polygon.is_valid or not math.isclose(polygon.area,sum(abs(_area(flat,t)) for t in triangles),rel_tol=1e-7,abs_tol=1e-6):
        raise ValueError('Başlangıç mesh açınımı üst üste biniyor veya kesim sınırıyla uyuşmuyor.')
    new,optimization=relax_mesh(verts,triangles,flat,cancel_token=token)
    poly=Polygon([new[i] for i in loop])
    if not poly.is_valid or not math.isclose(poly.area,sum(abs(_area(new,t)) for t in triangles),rel_tol=1e-7,abs_tol=1e-6):
        raise ValueError('Optimize mesh açınımı üst üste biniyor; nominal geometri korundu.')
    coordinates=[new[i] for i in loop]
    if contour_area(outline(coordinates).outer)<0:coordinates.reverse()
    geometry=outline(coordinates);direct=dict(zip(flat,new))
    def point(q):
        if q in direct:return direct[q]
        for tri in triangles:
            a,b,c=(flat[i] for i in tri);den=2*_area(flat,tri)
            u=((b[0]-q[0])*(c[1]-q[1])-(b[1]-q[1])*(c[0]-q[0]))/den
            v=((c[0]-q[0])*(a[1]-q[1])-(c[1]-q[1])*(a[0]-q[0]))/den
            w=1-u-v
            if min(u,v,w)>=-1e-8:
                return tuple(u*new[tri[0]][j]+v*new[tri[1]][j]+w*new[tri[2]][j] for j in range(2))
        raise ValueError('Yardımcı çizgi mesh alanı dışında; güvenli yeniden eşleme yapılamadı.')
    def curve(c):
        if isinstance(c,Line2D):return replace(c,start=point(c.start),end=point(c.end))
        if isinstance(c,Polyline2D):return replace(c,points=tuple(point(p) for p in c.points))
        raise ValueError('Bu yardımcı eğri türünün mesh eşlemesi desteklenmiyor.')
    rebuilt=finish_part(part.id,geometry,part.mesh_3d,part.surface_patches,poly.area,n,material,options,
                        construction=tuple(curve(c) for c in part.construction_lines),
                        seams=tuple(curve(c) for c in part.seams),
                        mappings=tuple(replace(m,developed=p) for m,p in zip(maps,new)),lengths=part.true_lengths)
    return replace(rebuilt,code=part.code,quantity=part.quantity,bending_lines=tuple(curve(c) for c in part.bending_lines),
                   nominal_geometry_2d=part.geometry_2d,nominal_bending_lines=part.bending_lines,nominal_part=part),optimization
