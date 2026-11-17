"""Closed, thickness-centred OCCT solids from authoritative nominal surfaces.

No display triangulation is converted to a solid. Explicit planar material
facets remain facets; thickening does not invent a forming or bend radius.
"""
import math


def _all_planar(shape):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    faces=TopExp_Explorer(shape,TopAbs_FACE)
    while faces.More():
        if BRepAdaptor_Surface(TopoDS.Face(faces.Current()),False).GetType()!=GeomAbs_Plane:return False
        faces.Next()
    return True


def solid_stats(shape):
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE,TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    if shape.IsNull() or not BRepCheck_Analyzer(shape).IsValid():
        raise ValueError('Kalınlıklı B-Rep katı geometrisi geçersiz.')
    free=TopExp_Explorer(shape,TopAbs_FACE,TopAbs_SOLID)
    if free.More():raise ValueError('Katı çıktıda bağımsız açık yüzey kalmış.')
    planar=_all_planar(shape)
    def integrate(item,kind):
        """(value, relative error). Planar faces: Gauss integration of the linear
        integrand is exact, so the adaptive (eps) pass only repeated it slowly."""
        properties=GProp_GProps()
        if planar:
            (BRepGProp.VolumeProperties_s if kind=='volume' else BRepGProp.SurfaceProperties_s)(item,properties)
            return properties.Mass(),0.
        if kind=='volume':error=BRepGProp.VolumeProperties_s(item,properties,1e-10,True)
        else:error=BRepGProp.SurfaceProperties_s(item,properties,1e-10)
        return properties.Mass(),error
    faces=TopExp_Explorer(shape,TopAbs_FACE);face_count=0
    while faces.More():face_count+=1;faces.Next()
    solids=TopExp_Explorer(shape,TopAbs_SOLID);volumes=[]
    while solids.More():
        volume,error=integrate(solids.Current(),'volume')
        if not math.isfinite(volume) or volume<=0:
            raise ValueError('Her katı gövdenin yönlü hacmi pozitif olmalı.')
        volumes.append((volume,error));solids.Next()
    counts=[face_count,len(volumes)]
    shells=TopExp_Explorer(shape,TopAbs_SHELL)
    while shells.More():
        if not BRep_Tool.IsClosed_s(shells.Current()):raise ValueError('Katı gövdenin kabuğu kapalı değil.')
        shells.Next()
    if counts[1]<1:raise ValueError('STEP çıktısında katı gövde bulunamadı; açık yüzey teslim edilmez.')
    # No free faces (checked above): the shape's volume is the sum of its solids'.
    total_volume=sum(v for v,_ in volumes);volume_error=max(abs(e) for _,e in volumes)
    total_area,area_error=integrate(shape,'area')
    if any(not math.isfinite(v) or v<=0 for v in (total_area,total_volume)):
        raise ValueError('Katının alanı ve hacmi sonlu, pozitif olmalı.')
    if any(not math.isfinite(e) or abs(e)>1e-7 for e in (volume_error,area_error)):
        raise ValueError('Katı alan/hacim integrasyonu istenen doğruluğa ulaşmadı.')
    bounds=Bnd_Box();BRepBndLib.AddOptimal_s(shape,bounds,False,False)
    a,b=bounds.CornerMin(),bounds.CornerMax()
    coordinates=(a.X(),a.Y(),a.Z(),b.X(),b.Y(),b.Z())
    if not all(math.isfinite(v) for v in coordinates):raise ValueError('Katı sınır kutusu sonlu değil.')
    return dict(faces=counts[0],solids=counts[1],area_mm2=total_area,volume_mm3=total_volume,
                closed=True,free_faces=0,bounds_mm=coordinates,
                volume_integration_relative_error=volume_error,area_integration_relative_error=area_error)


def _cone_tip(patch,thickness):
    """Close parallel conical walls at their separate, non-folded apices."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon,BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Pnt,gp_Ax1,gp_Dir
    p=patch.data;r=p['bottom_radius'];height=p['height'];half=thickness/2
    slant=math.hypot(r,height);c=height/slant;s=r/slant
    theta=p['theta0'];z=p.get('z_offset',0.)
    points=((r+half*c,half*s),(0.,height+half/s),(0.,height-half/s),(r-half*c,-half*s))
    if points[-1][0]<=0:raise ValueError('Koni kalınlığı iç açıklığı kapatıyor.')
    wire=BRepBuilderAPI_MakePolygon()
    for radius,h in points:wire.Add(gp_Pnt(radius*math.cos(theta),radius*math.sin(theta),z+h))
    wire.Close();face=BRepBuilderAPI_MakeFace(wire.Wire(),True)
    builder=BRepPrimAPI_MakeRevol(face.Face(),gp_Ax1(gp_Pnt(0.,0.,z),gp_Dir(0,0,1)),p['span'],True)
    if not builder.IsDone():raise ValueError('Tam koni katı tepe kapanması oluşturulamadı.')
    return builder.Shape()


def _joined_thickness(middle,thickness):
    """Intersect adjacent parallel planes at material creases before closing."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffsetShape
    from OCP.BRepOffset import BRepOffset_MakeOffset,BRepOffset_Skin
    from OCP.GeomAbs import GeomAbs_Intersection
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    unify=ShapeUpgrade_UnifySameDomain(middle,True,True,False);unify.Build()
    offset=BRepOffsetAPI_MakeOffsetShape()
    offset.PerformByJoin(unify.Shape(),-thickness/2,1e-6,BRepOffset_Skin,False,False,GeomAbs_Intersection,False)
    if not offset.IsDone():raise ValueError('Fasetlerin iç offseti oluşturulamadı.')
    sew=BRepBuilderAPI_Sewing(1e-6);sew.Add(offset.Shape());sew.Perform()
    builder=BRepOffset_MakeOffset()
    builder.Initialize(sew.SewedShape(),thickness,1e-6,BRepOffset_Skin,False,False,GeomAbs_Intersection,True,False)
    builder.MakeOffsetShape()
    if not builder.IsDone():raise ValueError('Faset köşeleri kapalı kalınlık gövdesi oluşturmuyor.')
    return builder.Shape()


def thicken_part(part,thickness,quality=None):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffsetShape,BRepOffsetAPI_MakeThickSolid
    from OCP.BRepLib import BRepLib
    from OCP.TopoDS import TopoDS
    from .cad import build_patch
    if type(thickness) not in (int,float) or not math.isfinite(thickness) or thickness<=0:
        raise ValueError('Katı STEP için sıfırdan büyük sac kalınlığı gerekli.')
    if not part.surface_patches:raise ValueError('Bu parçada doğrulanmış CAD yüzey tanımı yok.')
    tip=next((p for p in part.surface_patches if p.kind=='cone' and p.data['top_radius']==0),None)
    if tip and len(part.surface_patches)==1:shape=_cone_tip(tip,thickness)
    elif all(p.kind=='triangle' for p in part.surface_patches):
        from .solid_facets import facet_solid
        shape=facet_solid(part.surface_patches,thickness,quality)
    else:
        sew=BRepBuilderAPI_Sewing(1e-6)
        for patch in part.surface_patches:sew.Add(build_patch(patch))
        sew.Perform();middle=sew.SewedShape()
        if any(p.kind=='triangle' for p in part.surface_patches):
            shape=_joined_thickness(middle,thickness)
        else:
            offset=BRepOffsetAPI_MakeOffsetShape();offset.PerformBySimple(middle,-thickness/2)
            if not offset.IsDone():raise ValueError(f'{part.id}: orta yüzey kalınlık offseti oluşturulamadı.')
            builder=BRepOffsetAPI_MakeThickSolid();builder.MakeThickSolidBySimple(offset.Shape(),thickness)
            if not builder.IsDone():raise ValueError(f'{part.id}: yüzey kapalı katıya dönüştürülemedi.')
            shape=builder.Shape()
    from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    if TopExp_Explorer(shape,TopAbs_FACE,TopAbs_SOLID).More():
        raise ValueError(f'{part.id}: kalınlık işlemi bağımsız açık yüzey bıraktı.')
    solids=TopExp_Explorer(shape,TopAbs_SOLID);result=[]
    while solids.More():result.append(TopoDS.Solid(solids.Current()));solids.Next()
    if len(result)!=1:raise ValueError(f'{part.id}: tek fiziksel parça için tam bir katı gövde gerekli.')
    solid=result[0]
    if not BRepLib.OrientClosedSolid_s(solid):raise ValueError(f'{part.id}: katı yönü/kapanması doğrulanamadı.')
    solid_stats(solid)
    return solid


def write_solid_step(parts,path,thickness):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    from OCP.STEPControl import STEPControl_Writer,STEPControl_AsIs
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.APIHeaderSection import APIHeaderSection_MakeHeader
    from OCP.collections import HArray1_TCollection_HAsciiString
    from OCP.TCollection import TCollection_HAsciiString
    from .cad import _lock,read_step
    with _lock:
        shape=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(shape)
        qualities={}
        for part in parts:
            quality={};builder.Add(shape,thicken_part(part,thickness,quality))
            if quality:qualities[part.id]=quality
        before=solid_stats(shape)
        if before['solids']!=len(parts):raise ValueError('Katı gövde sayısı seçilen fiziksel parçalarla uyuşmuyor.')
        writer=STEPControl_Writer()
        Interface_Static.SetCVal_s('write.step.unit','MM');Interface_Static.SetCVal_s('write.step.schema','AP214IS')
        if writer.Transfer(shape,STEPControl_AsIs)!=IFSelect_RetDone:raise ValueError('Katı STEP aktarımı hazırlanamadı.')
        description=HArray1_TCollection_HAsciiString(1,3 if qualities else 2)
        description.SetValue(1,TCollection_HAsciiString(f'GOKWORKS CLOSED SOLIDS in MM; nominal midsurface +/- {thickness/2:.12g} MM; thickness {thickness:.12g} MM.'))
        description.SetValue(2,TCollection_HAsciiString('Separate solid per unique physical part; faceted designs remain faceted. Forming/process NOT VALIDATED.'))
        if qualities:
            maximum=max(q['normal_residual_mm'] for q in qualities.values())
            description.SetValue(3,TCollection_HAsciiString(f'FACETED NOMINAL CAD: maximum measured normal offset residual {maximum:.12g} MM; limit min(0.001 MM, 0.001*thickness). Not a manufacturing tolerance.'))
        header=APIHeaderSection_MakeHeader(writer.Model());header.SetDescription(description);header.Apply(writer.Model())
        if writer.Write(str(path))!=IFSelect_RetDone:raise ValueError('Katı STEP yazılamadı.')
        _,after=read_step(path)
        if (after['solids']!=before['solids'] or after.get('closed') is not True
                or not math.isclose(before['volume_mm3'],after.get('volume_mm3',0.),rel_tol=1e-7,abs_tol=1e-5)
                or not math.isclose(before['area_mm2'],after['area_mm2'],rel_tol=1e-7,abs_tol=1e-5)):
            raise ValueError('STEP yeniden okuma katı/hacim/alan doğrulaması başarısız.')
        if max(abs(a-b) for a,b in zip(before['bounds_mm'],after['bounds_mm']))>1e-4:
            raise ValueError('Katı STEP yeniden okuma sınır ölçüleri uyuşmuyor.')
        if qualities:after['facet_quality']=qualities
        return after
