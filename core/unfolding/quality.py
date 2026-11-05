"""Checks on the generated snapshot, independent of individual shape formulas."""
import math
from .geometry import curve_length,arc_point
from .models import Arc2D,Line2D,Circle2D,Polyline2D
from .shapes.common import sub,cross,norm


def inspect_parts(parts,tolerance):
    closure=0.;min_area=math.inf;triangles=0
    for part in parts:
        seen=set()
        for ring in (part.geometry_2d.outer,*part.geometry_2d.holes):
            ends=[]
            for curve in ring:
                if isinstance(curve,Line2D):pts=(curve.start,curve.end)
                elif isinstance(curve,Arc2D):pts=(arc_point(curve,curve.start_angle_deg),arc_point(curve,curve.start_angle_deg+curve.sweep_deg))
                elif isinstance(curve,Circle2D):pts=((curve.center[0]+curve.radius,curve.center[1]),)*2
                else:pts=curve.points+((curve.points[0],) if curve.closed else ())
                if any(not math.isfinite(v) for p in pts for v in p):raise ValueError('Sonlu olmayan 2D koordinat.')
                if curve_length(curve)<=tolerance:raise ValueError('Sıfır uzunluklu kontur elemanı.')
                if isinstance(curve,Polyline2D) and any(math.dist(a,b)<=tolerance for a,b in zip(pts,pts[1:])):
                    raise ValueError('Polyline içinde sıfır uzunluklu/yinelenen kenar.')
                if curve in seen:raise ValueError('Yinelenen kontur elemanı.')
                seen.add(curve);ends.append((pts[0],pts[-1]))
            closure=max(closure,*(math.dist(a[1],b[0]) for a,b in zip(ends,ends[1:]+ends[:1])))
        if closure>tolerance:raise ValueError('Kontur kapanma hatası geometri toleransını aşıyor.')
        mesh=part.mesh_3d
        if any(not math.isfinite(c) for v in mesh.vertices for c in v):raise ValueError('Sonlu olmayan mesh koordinatı.')
        for tri in mesh.triangles:
            if any(type(i) is not int or not 0<=i<len(mesh.vertices) for i in tri):raise ValueError('Mesh indeksleri geçersiz.')
            a,b,c=(mesh.vertices[i] for i in tri);area=norm(cross(sub(b,a),sub(c,a)))/2
            if area<=tolerance*tolerance:raise ValueError('Dejenere 3D üçgen.')
            min_area=min(min_area,area);triangles+=1
        if not mesh.triangles:raise ValueError('Önizleme mesh verisi boş.')
    return dict(contour_closure_error_mm=closure,mesh_triangle_count=triangles,minimum_triangle_area_mm2=min_area,
                geometry_tolerance_mm=tolerance,manufacturing_tolerance_mm=None)
