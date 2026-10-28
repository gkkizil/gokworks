"""Exact offset circle edges -> closed wire -> prism, optional bored hub."""
from .. import cad as kernel
from .geometry import profile
from .calculation import calculate


def build(s):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge,BRepBuilderAPI_MakeWire,BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism,BRepPrimAPI_MakeCylinder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse,BRepAlgoAPI_Cut
    from OCP.gp import gp_Circ,gp_Ax2,gp_Pnt,gp_Dir,gp_Vec
    from OCP.TopoDS import TopoDS
    with kernel._kernel_lock:
        wire=BRepBuilderAPI_MakeWire()
        for a in profile(s):
            circle=gp_Circ(gp_Ax2(gp_Pnt(*a.center,0),gp_Dir(0,0,1)),a.radius)
            edge=BRepBuilderAPI_MakeEdge(circle,min(a.start,a.end),max(a.start,a.end))
            if not edge.IsDone():raise ValueError('Zincir dişi daire yayı oluşturulamadı.')
            e=edge.Edge()
            if a.end<a.start:e=TopoDS.Edge(e.Reversed())
            wire.Add(e)
        if not wire.IsDone() or not wire.Wire().Closed():raise ValueError('Zincir dişlisi CAD konturu kapanmadı.')
        face=BRepBuilderAPI_MakeFace(wire.Wire(),True)
        if not face.IsDone():raise ValueError('Zincir dişlisi yüzeyi oluşturulamadı.')
        shape=BRepPrimAPI_MakePrism(face.Face(),gp_Vec(0,0,s.width_mm)).Shape()
        if s.hub_diameter_mm:
            op=BRepAlgoAPI_Fuse(shape,BRepPrimAPI_MakeCylinder(s.hub_diameter_mm/2,s.hub_length_mm).Shape());op.Build()
            if not op.IsDone():raise ValueError('Zincir dişlisi göbeği birleştirilemedi.')
            shape=op.Shape()
        if s.bore_mm:
            tool=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0,0,-1),gp_Dir(0,0,1)),s.bore_mm/2,max(s.width_mm,s.hub_length_mm)+2).Shape()
            op=BRepAlgoAPI_Cut(shape,tool);op.Build()
            if not op.IsDone():raise ValueError('Mil deliği kesilemedi.')
            shape=op.Shape()
        if kernel.shape_stats(shape)['solids']!=1:raise ValueError('Zincir dişlisi tek geçerli katı olmalı.')
        return shape


def placed(s,target='pair'):
    from ..families.cad import move
    r=calculate(s)
    if target not in ('pinion','wheel','pair'):raise ValueError('Zincir dişlisi CAD hedefi geçersiz.')
    if target=='pinion':return [build(s.driver)]
    if target=='wheel':return [build(s.driven)]
    return [build(s.driver),move(build(s.driven),x=r.corrected_center_mm)]
