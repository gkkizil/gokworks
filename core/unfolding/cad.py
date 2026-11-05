"""Lazy OCCT mid-surface B-Rep export. No mesh-to-STEP or solid claim."""
import math
from threading import RLock

_lock=RLock()


def build_patch(patch):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon,BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Pnt,gp_Dir,gp_Ax3,gp_Cylinder,gp_Cone
    p=patch.data
    if patch.kind=='triangle':
        wire=BRepBuilderAPI_MakePolygon()
        for v in p['vertices']:wire.Add(gp_Pnt(*v))
        wire.Close();maker=BRepBuilderAPI_MakeFace(wire.Wire(),True)
    elif patch.kind=='cylinder':
        if p['lower'] or p['upper']:raise ValueError('Eğik kesilmiş silindirin STEP yüzey kırpması v1 kapsamında değil.')
        axis=gp_Ax3(gp_Pnt(*p['origin']),gp_Dir(*p['axis']),gp_Dir(*p['radial_x']))
        maker=BRepBuilderAPI_MakeFace(gp_Cylinder(axis,p['radius']),p['theta0'],p['theta0']+p['span'],0.,p['length'])
    elif patch.kind=='cone':
        angle=math.atan2(p['top_radius']-p['bottom_radius'],p['height'])
        axis=gp_Ax3(gp_Pnt(0,0,0),gp_Dir(0,0,1))
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
    props=GProp_GProps();BRepGProp.SurfaceProperties_s(shape,props);area=props.Mass()
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
        shape=reader.OneShape();return shape,surface_stats(shape)


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
        if writer.Transfer(shape,STEPControl_AsIs)!=IFSelect_RetDone or writer.Write(str(path))!=IFSelect_RetDone:raise ValueError('STEP yazılamadı.')
        _,after=read_step(path)
        if before['faces']!=after['faces'] or not math.isclose(before['area_mm2'],after['area_mm2'],rel_tol=1e-7,abs_tol=1e-6):
            raise ValueError('STEP yeniden okuma alan/yüzey sayısı uyuşmuyor.')
        if max(abs(a-b) for a,b in zip(before['bounds_mm'],after['bounds_mm']))>1e-4:raise ValueError('STEP sınır kutusu uyuşmuyor.')
        return after
