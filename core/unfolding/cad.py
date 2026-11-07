"""Lazy OCCT mid-surface B-Rep export. No mesh-to-STEP or solid claim."""
import math
from threading import RLock

_lock=RLock()


def _ruled_round_surface(data):
    """Exact rational circular sections with linear axial/radial offset."""
    from OCP.Geom import Geom_BSplineSurface
    from OCP.collections import Array2_gp_Pnt,Array2_double,Array1_double,Array1_int
    from OCP.gp import gp_Pnt
    axis=data['axis'];rx=data['radial_x']
    ry=(axis[1]*rx[2]-axis[2]*rx[1],axis[2]*rx[0]-axis[0]*rx[2],axis[0]*rx[1]-axis[1]*rx[0])
    poles=Array2_gp_Pnt(1,9,1,2);weights=Array2_double(1,9,1,2)
    for i in range(9):
        angle=data['theta0']+i*math.pi/4;w=math.sqrt(.5) if i%2 else 1.
        for j,z in enumerate((data['zmin'],data['zmax']),1):
            r=data['radius']+data['slope']*z
            x=data['skew'][0]*z+r*math.cos(angle)/w
            y=data['skew'][1]*z+r*math.sin(angle)/w
            p=tuple(data['origin'][k]+axis[k]*z+rx[k]*x+ry[k]*y for k in range(3))
            poles.SetValue(i+1,j,gp_Pnt(*p));weights.SetValue(i+1,j,w)
    def array(cls,values):
        result=cls(1,len(values))
        for i,value in enumerate(values,1):result.SetValue(i,value)
        return result
    return Geom_BSplineSurface(poles,weights,array(Array1_double,(0.,1.,2.,3.,4.)),
        array(Array1_double,(data['zmin'],data['zmax'])),
        array(Array1_int,(3,2,2,2,3)),array(Array1_int,(2,2)),2,1)


def _trimmed_surface(surface, data):
    """Build p-curves on an analytic surface; display triangles are not used."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge,BRepBuilderAPI_MakeWire,BRepBuilderAPI_MakeFace
    from OCP.Geom2d import Geom2d_BSplineCurve
    from OCP.collections import Array1_gp_Pnt2d,Array1_double,Array1_int
    from OCP.gp import gp_Pnt2d
    from OCP.BRepLib import BRepLib
    def wire(points, positive):
        points=list(points)
        area=sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(points,points[1:]+points[:1]))
        if (area>0)!=positive:points.reverse()
        # Degree-one B-splines preserve every original straight UV segment.
        # Keep monotone-U runs together: one exact piecewise-linear boundary
        # edge avoids hundreds of unnecessary thickness wall faces.
        groups=[];keys=[]
        for a,b in zip(points,points[1:]+points[:1]):
            if math.dist(a,b)<1e-12:continue
            du=b[0]-a[0];key=0 if abs(du)<1e-12 else 1 if du>0 else -1
            if keys and key==keys[-1]:groups[-1].append(b)
            else:keys.append(key);groups.append([a,b])
        if len(groups)>1 and keys[-1]==keys[0]:groups[0]=groups[-1][:-1]+groups[0];groups.pop()
        builder=BRepBuilderAPI_MakeWire()
        for group in groups:
            count=len(group);poles=Array1_gp_Pnt2d(1,count);knots=Array1_double(1,count);multiplicities=Array1_int(1,count)
            for i,q in enumerate(group,1):
                poles.SetValue(i,gp_Pnt2d(*q));knots.SetValue(i,i-1.)
                multiplicities.SetValue(i,2 if i in (1,count) else 1)
            curve=Geom2d_BSplineCurve(poles,knots,multiplicities,1,False)
            edge=BRepBuilderAPI_MakeEdge(curve,surface,0.,count-1.)
            if not edge.IsDone():raise ValueError('Analitik yüzey sınır kenarı oluşturulamadı.')
            builder.Add(edge.Edge())
        if not builder.IsDone():raise ValueError('Analitik yüzey sınır teli kapatılamadı.')
        return builder.Wire()
    maker=BRepBuilderAPI_MakeFace(surface,wire(data['outer'],True),True)
    for hole in data['holes']:maker.Add(wire(hole,False))
    if not maker.IsDone():raise ValueError('Kırpılmış analitik yüzey oluşturulamadı.')
    face=maker.Face()
    if not BRepLib.BuildCurves3d_s(face,1e-7):raise ValueError('Yüzeyin gerçek 3D sınır eğrileri oluşturulamadı.')
    BRepLib.SameParameter_s(face,1e-7,True)
    return face


def build_patch(patch):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon,BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Pnt,gp_Dir,gp_Ax3,gp_Cylinder,gp_Cone
    p=patch.data
    if patch.kind=='trimmed_ruled_round':
        # Split rational-circle knot lines. Each basis patch is C-infinity;
        # OCCT offsetting rejects a C0-labelled multi-quadrant BSpline even
        # when its circular geometry is tangent-continuous at those knots.
        from shapely.geometry import Polygon,box
        from OCP.BRep import BRep_Builder
        from OCP.TopoDS import TopoDS_Compound
        result=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(result)
        region=Polygon(p['outer'],p['holes'])
        for i in range(4):
            clipped=region.intersection(box(i,p['zmin']-1,i+1,p['zmax']+1))
            areas=(clipped,) if clipped.geom_type=='Polygon' else getattr(clipped,'geoms',())
            for area in areas:
                if area.geom_type!='Polygon' or area.area<=1e-12:continue
                surface=_ruled_round_surface(p);surface.Segment(i,i+1,p['zmin'],p['zmax'])
                data=dict(outer=list(area.exterior.coords)[:-1],holes=[list(h.coords)[:-1] for h in area.interiors])
                builder.Add(result,_trimmed_surface(surface,data))
        return result
    if patch.kind in ('trimmed_cylinder','trimmed_cone'):
        from OCP.Geom import Geom_CylindricalSurface,Geom_ConicalSurface
        axis=gp_Ax3(gp_Pnt(*p['origin']),gp_Dir(*p['axis']),gp_Dir(*p['radial_x']))
        surface=(Geom_CylindricalSurface(gp_Cylinder(axis,p['radius'])) if patch.kind=='trimmed_cylinder'
                 else Geom_ConicalSurface(gp_Cone(axis,p['semi_angle'],p['radius'])))
        return _trimmed_surface(surface,p)
    if patch.kind=='planar_3d':
        def wire(points):
            builder=BRepBuilderAPI_MakePolygon()
            for q in points:builder.Add(gp_Pnt(*q))
            builder.Close()
            if not builder.IsDone():raise ValueError('Düzlemsel yüzey sınırı oluşturulamadı.')
            return builder.Wire()
        maker=BRepBuilderAPI_MakeFace(wire(p['outer']),True)
        for hole in p['holes']:maker.Add(wire(hole))
    elif patch.kind=='triangle':
        wire=BRepBuilderAPI_MakePolygon()
        for v in p['vertices']:wire.Add(gp_Pnt(*v))
        wire.Close();maker=BRepBuilderAPI_MakeFace(wire.Wire(),True)
    elif patch.kind=='planar_xy':
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire,BRepBuilderAPI_MakeEdge
        from OCP.gp import gp_Circ,gp_Ax2
        def wire(curves):
            builder=BRepBuilderAPI_MakeWire();z=p['z']
            for c in curves:
                kind=c['kind']
                if kind in ('arc','circle'):
                    axis=gp_Ax2(gp_Pnt(c['center'][0],c['center'][1],z),gp_Dir(0,0,1))
                    circle=gp_Circ(axis,c['radius'])
                    if kind=='circle':edge=BRepBuilderAPI_MakeEdge(circle).Edge()
                    else:
                        a=math.radians(c['start_angle_deg']);b=a+math.radians(c['sweep_deg'])
                        edge=BRepBuilderAPI_MakeEdge(circle,min(a,b),max(a,b)).Edge()
                        if b<a:edge.Reverse()
                    builder.Add(edge)
                else:
                    pts=(c['start'],c['end']) if kind=='line' else tuple(c['points'])+((c['points'][0],) if c.get('closed') else ())
                    for a,b in zip(pts,pts[1:]):builder.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(a[0],a[1],z),gp_Pnt(b[0],b[1],z)).Edge())
            if not builder.IsDone():raise ValueError('Düz levha B-Rep teli oluşturulamadı.')
            return builder.Wire()
        maker=BRepBuilderAPI_MakeFace(wire(p['outer']),True)
        for hole in p['holes']:maker.Add(wire(hole))
    elif patch.kind=='cylinder':
        if p['lower'] or p['upper']:raise ValueError('Eğik kesilmiş silindirin STEP yüzey kırpması v1 kapsamında değil.')
        axis=gp_Ax3(gp_Pnt(*p['origin']),gp_Dir(*p['axis']),gp_Dir(*p['radial_x']))
        maker=BRepBuilderAPI_MakeFace(gp_Cylinder(axis,p['radius']),p['theta0'],p['theta0']+p['span'],0.,p['length'])
    elif patch.kind=='cone':
        angle=math.atan2(p['top_radius']-p['bottom_radius'],p['height'])
        axis=gp_Ax3(gp_Pnt(0,0,p.get('z_offset',0.)),gp_Dir(0,0,1))
        maker=BRepBuilderAPI_MakeFace(gp_Cone(axis,angle,p['bottom_radius']),p['theta0'],p['theta0']+p['span'],
                                    0.,math.hypot(p['height'],p['bottom_radius']-p['top_radius']))
    else:raise ValueError('STEP yüzey tanımı desteklenmiyor.')
    if not maker.IsDone():raise ValueError('B-Rep orta yüzey oluşturulamadı.')
    return maker.Face()


def surface_stats(shape):
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.TopAbs import TopAbs_FACE,TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    if shape.IsNull() or not BRepCheck_Analyzer(shape).IsValid():raise ValueError('Geçersiz STEP B-Rep yüzeyi.')
    counts=[]
    for kind in (TopAbs_FACE,TopAbs_SOLID):
        e=TopExp_Explorer(shape,kind);count=0
        while e.More():count+=1;e.Next()
        counts.append(count)
    props=GProp_GProps();BRepGProp.SurfaceProperties_s(shape,props,1e-10);area=props.Mass()
    if counts[0]<1 or counts[1]!=0 or not math.isfinite(area) or area<=0:raise ValueError('STEP geçerli pozitif alanlı orta yüzey olmalı; solid değildir.')
    bounds=Bnd_Box();BRepBndLib.AddOptimal_s(shape,bounds,False,False)
    low,high=bounds.CornerMin(),bounds.CornerMax()
    return dict(faces=counts[0],solids=counts[1],area_mm2=area,
                bounds_mm=(low.X(),low.Y(),low.Z(),high.X(),high.Y(),high.Z()))


def read_step(path):
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    with _lock:
        reader=STEPControl_Reader()
        if reader.ReadFile(str(path))!=IFSelect_RetDone or reader.TransferRoots()<1:raise ValueError('STEP tekrar okunamadı.')
        shape=reader.OneShape()
        from OCP.TopAbs import TopAbs_SOLID
        from OCP.TopExp import TopExp_Explorer
        if TopExp_Explorer(shape,TopAbs_SOLID).More():
            from .solid_cad import solid_stats
            return shape,solid_stats(shape)
        return shape,surface_stats(shape)


def write_step(parts,path):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    from OCP.STEPControl import STEPControl_Writer,STEPControl_AsIs
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    with _lock:
        shape=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(shape)
        for part in parts:
            for patch in part.surface_patches:builder.Add(shape,build_patch(patch))
        before=surface_stats(shape);writer=STEPControl_Writer()
        Interface_Static.SetCVal_s('write.step.unit','MM');Interface_Static.SetCVal_s('write.step.schema','AP214IS')
        if writer.Transfer(shape,STEPControl_AsIs)!=IFSelect_RetDone:raise ValueError('STEP aktarımı hazırlanamadı.')
        from OCP.APIHeaderSection import APIHeaderSection_MakeHeader
        from OCP.collections import HArray1_TCollection_HAsciiString
        from OCP.TCollection import TCollection_HAsciiString
        description=HArray1_TCollection_HAsciiString(1,2)
        description.SetValue(1,TCollection_HAsciiString('GOKWORKS geometric midsurface in MM; surface only, NOT A SOLID; manufacturing/forming NOT VALIDATED.'))
        description.SetValue(2,TCollection_HAsciiString('Triangle patches are explicit planar/faceted material, not a smooth-surface isometric development.' if any(p.kind=='triangle' for part in parts for p in part.surface_patches) else 'Analytic midsurface patches; springback and material strain are not evaluated.'))
        header=APIHeaderSection_MakeHeader(writer.Model());header.SetDescription(description);header.Apply(writer.Model())
        if writer.Write(str(path))!=IFSelect_RetDone:raise ValueError('STEP yazılamadı.')
        _,after=read_step(path)
        if before['faces']!=after['faces'] or not math.isclose(before['area_mm2'],after['area_mm2'],rel_tol=1e-7,abs_tol=1e-6):
            raise ValueError('STEP yeniden okuma alan/yüzey sayısı uyuşmuyor.')
        if max(abs(a-b) for a,b in zip(before['bounds_mm'],after['bounds_mm']))>1e-4:raise ValueError('STEP sınır kutusu uyuşmuyor.')
        return after
