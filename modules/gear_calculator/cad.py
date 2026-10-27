"""Real OCCT curves, planar faces, bored prisms and STEP B-Rep (lazy module).

No mesh is used to construct a solid. Cubic Bezier involute approximation has
the bound documented in geometry.py; circular tip/root and bore edges are exact.
"""

from math import isfinite
from threading import RLock
from .geometry import gear_profile, pair_angles
from .calculation import calculate_pair
from .validation import require_manufacturable

_kernel_lock = RLock()


def _edge(segment):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.Geom import Geom_BezierCurve
    from OCP.collections import Array1_gp_Pnt
    from OCP.gp import gp_Pnt, gp_Ax2, gp_Dir, gp_Circ
    if segment.kind=='arc':
        circle=gp_Circ(gp_Ax2(gp_Pnt(0,0,0),gp_Dir(0,0,1)),segment.radius)
        maker=BRepBuilderAPI_MakeEdge(circle,segment.start_angle,segment.end_angle)
    elif segment.kind=='line':
        maker=BRepBuilderAPI_MakeEdge(*(gp_Pnt(x,y,0) for x,y in segment.controls))
    else:
        poles=Array1_gp_Pnt(1,4)
        for i,(x,y) in enumerate(segment.controls,1):
            poles.SetValue(i,gp_Pnt(x,y,0))
        maker=BRepBuilderAPI_MakeEdge(Geom_BezierCurve(poles))
    if not maker.IsDone():
        raise ValueError('OCCT diş profili kenarı oluşturulamadı.')
    return maker.Edge()


def build_gear(spec):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeEdge
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec, gp_Pnt, gp_Ax2, gp_Dir, gp_Circ
    profile=gear_profile(spec)
    with _kernel_lock:
        wire=BRepBuilderAPI_MakeWire()
        for segment in profile.segments:
            wire.Add(_edge(segment))
        if not wire.IsDone() or not wire.Wire().Closed():
            raise ValueError('OCCT diş konturu kapalı bir wire oluşturamadı.')
        face=BRepBuilderAPI_MakeFace(wire.Wire(),True)
        if spec.bore_mm:
            hole=BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(
                gp_Circ(gp_Ax2(gp_Pnt(0,0,0),gp_Dir(0,0,1)),spec.bore_mm/2)).Edge()).Wire()
            hole.Reverse();face.Add(hole)
        if not face.IsDone():
            raise ValueError('Dişli yüzeyi/deliği oluşturulamadı.')
        solid=BRepPrimAPI_MakePrism(face.Face(),gp_Vec(0,0,spec.face_width_mm),False,True)
        if not solid.IsDone():
            raise ValueError('Dişli katı modeli oluşturulamadı.')
        shape=solid.Shape()
        stats=shape_stats(shape)
        if stats['solids']!=1:
            raise ValueError('Her dişli tam bir kapalı katı gövde olmalı.')
        return shape


def placed_gears(spec,target='pair'):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
    result=calculate_pair(spec);require_manufacturable(result)
    if target not in ('pinion','wheel','pair'):
        raise ValueError('Aktarım hedefi pinyon, çark veya takım olmalı.')
    chosen=[spec.pinion] if target=='pinion' else [spec.wheel] if target=='wheel' else [spec.pinion,spec.wheel]
    with _kernel_lock:
        shapes=[build_gear(g) for g in chosen]
        if target=='pair':
            pose=gp_Trsf();pose.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,0,1)),pair_angles(spec)[1])
            pose.SetTranslationPart(gp_Vec(result.center_distance_mm,0,0))
            shapes[1]=BRepBuilderAPI_Transform(shapes[1],pose,True).Shape()
        return shapes


def compound(shapes):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    result=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(result)
    for shape in shapes:
        builder.Add(result,shape)
    return result


def shape_stats(shape):
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    if shape.IsNull() or not BRepCheck_Analyzer(shape).IsValid():
        raise ValueError('OCCT katı geometrisi geçersiz.')
    explorer=TopExp_Explorer(shape,TopAbs_SOLID);count=0
    while explorer.More():
        count+=1;explorer.Next()
    props=GProp_GProps();BRepGProp.VolumeProperties_s(shape,props)
    volume=props.Mass()
    if not count or not isfinite(volume) or volume<=0:
        raise ValueError('CAD modeli pozitif katı hacmi içermiyor.')
    bounds=Bnd_Box();BRepBndLib.AddOptimal_s(shape,bounds,False,False)
    low,high=bounds.CornerMin(),bounds.CornerMax()
    return dict(solids=count,volume_mm3=volume,bounds_mm=(low.X(),low.Y(),low.Z(),high.X(),high.Y(),high.Z()))


def write_step(shapes,path):
    from OCP.STEPControl import STEPControl_Writer,STEPControl_AsIs
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    with _kernel_lock:
        writer=STEPControl_Writer()
        Interface_Static.SetCVal_s('write.step.unit','MM')
        Interface_Static.SetCVal_s('write.step.schema','AP214IS')
        for shape in shapes:
            if writer.Transfer(shape,STEPControl_AsIs)!=IFSelect_RetDone:
                raise ValueError('Katı STEP modeline aktarılamadı.')
        if writer.Write(str(path))!=IFSelect_RetDone:
            raise OSError('STEP dosyası yazılamadı.')


def read_step(path):
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    with _kernel_lock:
        reader=STEPControl_Reader()
        if reader.ReadFile(str(path))!=IFSelect_RetDone or reader.TransferRoots()<1:
            raise ValueError('STEP dosyası tekrar okunamadı.')
        shape=reader.OneShape();shape_stats(shape)
        return shape


def triangulate(shapes,deflection=.1):
    """Tessellate the exact same bored B-Rep exported to STEP; coordinates mm."""
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    points=[]
    for shape in shapes:
        BRepMesh_IncrementalMesh(shape,deflection,False,.3,False)
        faces=TopExp_Explorer(shape,TopAbs_FACE)
        while faces.More():
            face=TopoDS.Face(faces.Current());location=TopLoc_Location()
            mesh=BRep_Tool.Triangulation_s(face,location)
            if mesh is not None:
                tr=location.Transformation()
                for i in range(1,mesh.NbTriangles()+1):
                    indices=list(mesh.Triangle(i).Get())
                    if face.Orientation()==TopAbs_REVERSED:
                        indices[1],indices[2]=indices[2],indices[1]
                    for index in indices:
                        p=mesh.Node(index).Transformed(tr)
                        points.extend((p.X(),p.Y(),p.Z()))
                    if len(points)>120000*9:
                        raise ValueError('3D önizleme 120.000 üçgen sınırını aşıyor; 2D/STEP kullanın.')
            faces.Next()
    if not points:
        raise ValueError('Katıdan görüntülenebilir üçgen üretilemedi.')
    return points
