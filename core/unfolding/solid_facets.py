"""Normal-offset B-Rep for explicitly planar material facets (not preview mesh).

At each material vertex intersect the incident parallel facet planes. Curved
fans can overconstrain a vertex; their measured normal residual is limited to
min(0.001 mm, 0.001*t). This is a nominal faceted CAD approximation, not a
manufacturing tolerance. Non-manifold or incompatible systems are rejected.
"""
from collections import defaultdict,deque
import math

from .shapes.common import add,sub,mul,dot,cross,norm


def prepare_facets(patches,thickness,quality=None):
    """GUI-independent eligibility and normal-offset construction."""
    vertices=[];index={};triangles=[];edges=defaultdict(list)
    for patch in patches:
        if patch.kind!='triangle':raise ValueError('Faset katısı yalnız açıkça tanımlanmış düz malzeme yüzlerini kabul eder.')
        ids=[]
        for p in patch.data['vertices']:
            key=tuple(round(v,8) for v in p)
            if key not in index:index[key]=len(vertices);vertices.append(tuple(p))
            ids.append(index[key])
        if len(set(ids))<3:continue
        if norm(cross(sub(vertices[ids[1]],vertices[ids[0]]),sub(vertices[ids[2]],vertices[ids[0]])))<1e-12:continue
        i=len(triangles);triangles.append(tuple(ids))
        for a,b in zip(ids,ids[1:]+ids[:1]):edges[tuple(sorted((a,b)))].append((i,a,b))
    if not triangles or any(len(v)>2 for v in edges.values()):raise ValueError('Malzeme fasetleri manifold yüzey oluşturmuyor.')
    adjacent=defaultdict(list)
    for entries in edges.values():
        if len(entries)==2:
            (i,a,b),(j,c,d)=entries;same=a==c
            adjacent[i].append((j,same));adjacent[j].append((i,same))
    flips={0:False};queue=deque([0])
    while queue:
        i=queue.popleft()
        for j,same in adjacent[i]:
            flip=flips[i]^same
            if j in flips:
                if flips[j]!=flip:raise ValueError('Fasetlerin yüz yönleri tutarlı değil.')
            else:flips[j]=flip;queue.append(j)
    if len(flips)!=len(triangles):raise ValueError('Tek parçanın malzeme yüzeyleri bağlantısız.')
    triangles=[t[::-1] if flips[i] else t for i,t in enumerate(triangles)]
    normals=defaultdict(list)
    for triangle in triangles:
        a,b,c=(vertices[i] for i in triangle);normal=cross(sub(b,a),sub(c,a));normal=mul(normal,1/norm(normal))
        for i in triangle:normals[i].append(normal)
    offsets={};max_error=0.;tolerance=min(0.001,thickness*0.001)
    for i,ns in normals.items():
        # Subtract the first normal before forming the dual plane. Solving
        # almost-parallel unit rows directly loses precision at ellipse lofts.
        a=ns[0];b=max(ns,key=lambda n:dot(sub(n,a),sub(n,a)));delta=sub(b,a)
        pair_den=1+dot(a,b)
        if pair_den<1e-12:raise ValueError('Faset normalleri karşıt; kalınlık köşesi tekil.')
        pair_direction=mul(add(a,b),1/pair_den)
        c=max(ns,key=lambda n:dot(cross(delta,sub(n,a)),cross(delta,sub(n,a))))
        dual=cross(delta,sub(c,a));den=dot(a,dual)
        if max(abs(dot(n,pair_direction)-1) for n in ns)<1e-10:
            # Coplanar duplicates and round-off near a straight generator must
            # not turn a rank-one/two corner into an ill-conditioned rank three.
            direction=pair_direction
        elif norm(dual)>1e-12*max(dot(delta,delta),1e-24):
            if abs(den)<1e-12*norm(dual):raise ValueError('Faset normal offseti sonlu köşe üretmiyor.')
            direction=mul(dual,1/den)
        else:
            direction=pair_direction
        error=max(abs(dot(n,direction)-1)*thickness/2 for n in ns)
        max_error=max(max_error,error)
        if not math.isfinite(error) or error>tolerance:
            raise ValueError(f'Bu kalınlıkta faset köşesinin normal sapması {error:.6g} mm; sınır {tolerance:.6g} mm. Katı STEP üretilemez.')
        offsets[i]=mul(direction,thickness/2)
    outer={i:add(p,offsets[i]) for i,p in enumerate(vertices) if i in offsets}
    inner={i:sub(p,offsets[i]) for i,p in enumerate(vertices) if i in offsets}
    if quality is not None:quality.update(method='parallel_facet_plane_miters',normal_residual_mm=max_error,normal_residual_limit_mm=tolerance)
    return triangles,edges,outer,inner


def facet_solid(patches,thickness,quality=None):
    from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakePolygon,BRepBuilderAPI_MakeFace,
                                   BRepBuilderAPI_Sewing,BRepBuilderAPI_MakeSolid)
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt
    from OCP.BRep import BRep_Tool
    triangles,edges,outer,inner=prepare_facets(patches,thickness,quality)
    sew=BRepBuilderAPI_Sewing(1e-6)
    def face(points):
        builder=BRepBuilderAPI_MakePolygon()
        for p in points:builder.Add(gp_Pnt(*p))
        builder.Close();maker=BRepBuilderAPI_MakeFace(builder.Wire(),True)
        if not maker.IsDone():raise ValueError('Kalınlıklı gerçek düz B-Rep yüz oluşturulamadı.')
        sew.Add(maker.Face())
    for triangle in triangles:
        face([outer[i] for i in triangle]);face([inner[i] for i in triangle[::-1]])
        for a,b in zip(triangle,triangle[1:]+triangle[:1]):
            if len(edges[tuple(sorted((a,b)))])==1:
                face((inner[a],inner[b],outer[b]));face((inner[a],outer[b],outer[a]))
    sew.Perform();shells=TopExp_Explorer(sew.SewedShape(),TopAbs_SHELL);result=[]
    while shells.More():result.append(TopoDS.Shell(shells.Current()));shells.Next()
    if len(result)!=1 or not BRep_Tool.IsClosed_s(result[0]):raise ValueError('Faset katısının tek kapalı kabuğu oluşmadı.')
    return BRepBuilderAPI_MakeSolid(result[0]).Solid()
