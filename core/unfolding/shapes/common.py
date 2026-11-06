"""Shared immutable part assembly; never invents material/process data."""
import math
from ..models import (FrozenMap, UnfoldPart, Line2D, DimensionAnnotation, DrawingView,
                      Mesh3D, SurfacePatch)
from ..geometry import measure


class UnfoldCancelled(Exception): pass


def check_cancel(token):
    if token is not None and token.is_set(): raise UnfoldCancelled('Sac açınımı hesabı iptal edildi.')


def add(a,b): return tuple(x+y for x,y in zip(a,b))
def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def mul(a,k): return tuple(x*k for x in a)
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def norm(a): return math.sqrt(dot(a,a))


def finish_part(identifier, geometry, mesh, patches, net_area, normalized, material, options,
                *, construction=(), seams=(), mappings=(), lengths=()):
    metrics=measure(geometry,net_area,normalized['thickness'],material,options.chord_error_mm,options.max_samples)
    b=metrics.bounds_mm
    dims=(DimensionAnnotation(identifier+'.width',b[2]-b[0],'mm','developed_width',
                              (b[0],b[1]),(b[2],b[1]),((b[0]+b[2])/2,b[1]-8)),
          DimensionAnnotation(identifier+'.height',b[3]-b[1],'mm','developed_height',
                              (b[2],b[1]),(b[2],b[3]),(b[2]+8,(b[1]+b[3])/2)))
    front=tuple((v[0],v[2]) for v in mesh.vertices)
    top=tuple((v[0],v[1]) for v in mesh.vertices)
    # Wireframe views use actual triangle edges, not a fictitious smooth silhouette.
    def edges(points):
        known=set();result=[]
        for face in mesh.triangles:
            for a,c in zip(face,face[1:]+face[:1]):
                edge=tuple(sorted((a,c)))
                if edge not in known and math.dist(points[a],points[c])>1e-9:
                    known.add(edge);result.append(Line2D(points[a],points[c]))
        return tuple(result)
    return UnfoldPart(identifier,identifier,normalized['request_id'],1,geometry,mesh,tuple(patches),
        (DrawingView('front','Ön görünüş',edges(front)),DrawingView('top','Üst görünüş',edges(top))),dims,
        construction_lines=tuple(construction),seams=tuple(seams),labels=((identifier,(b[0],b[1]-12)),),
        true_lengths=tuple(lengths),mappings=tuple(mappings),metrics=metrics)


def mesh_from_faces(vertices,faces):
    return Mesh3D(tuple(vertices),tuple(faces))


def planar_part(identifier, vertices3, points2, triangles, normalized, material, options, *, construction=(), lengths=()):
    from ..geometry import outline,contour_area
    from ..models import MappingPoint
    geometry=outline(points2)
    patches=tuple(SurfacePatch('triangle',FrozenMap({'vertices':tuple(vertices3[i] for i in t)})) for t in triangles)
    mappings=tuple(MappingPoint(p,q,str(i+1)) for i,(p,q) in enumerate(zip(points2,vertices3)))
    return finish_part(identifier,geometry,mesh_from_faces(vertices3,triangles),patches,contour_area(geometry.outer),
                       normalized,material,options,construction=construction,mappings=mappings,lengths=lengths)


def with_generators(part,samples,normalized,*,clip_holes=False):
    """Attach independent helper sampling; holes interrupt material guide lengths."""
    from dataclasses import replace
    from ..models import TrueLength
    guides=[];lengths=[];maximum=len(samples)-1
    for j,(flat0,flat1,world0,world1) in enumerate(samples):
        if math.dist(flat0,flat1)<=1e-8:continue
        segments=[(flat0,flat1)]
        if clip_holes:
            from shapely.geometry import LineString
            from ..geometry import polygon
            o=normalized['development_options'];line=LineString((flat0,flat1));cut=line.intersection(polygon(part.geometry_2d,o['chord_error_mm'],o['max_samples']))
            geoms=[cut] if cut.geom_type=='LineString' else [v for v in getattr(cut,'geoms',()) if v.geom_type=='LineString']
            segments=[(tuple(v.coords[0]),tuple(v.coords[-1])) for v in geoms if v.length>1e-7]
        direction=sub(flat1,flat0);den=dot(direction,direction)
        for index,(a,b) in enumerate(segments):
            fa=dot(sub(a,flat0),direction)/den;fb=dot(sub(b,flat0),direction)/den
            aa=add(world0,mul(sub(world1,world0),fa));bb=add(world0,mul(sub(world1,world0),fb))
            name=f'G{j}'+(f'.{index+1}' if len(segments)>1 else '')
            lengths.append(TrueLength(name,aa,bb,math.dist(aa,bb)))
            if j not in (0,maximum):guides.append(Line2D(a,b,name))
    return replace(part,construction_lines=tuple(guides),true_lengths=tuple(lengths))
