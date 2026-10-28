"""OCCT solids. Smooth lofts for helical sections, exact prisms otherwise."""
from math import ceil, cos, pi, sin, tan
from .. import cad as kernel
from .calculation import calculate,cylindrical
from .geometry import sections,poses


def wire(segments):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire
    w=BRepBuilderAPI_MakeWire()
    for seg in segments:w.Add(kernel._edge(seg))
    if not w.IsDone() or not w.Wire().Closed():raise ValueError('CAD konturu kapanmadı.')
    return w.Wire()


def move(shape,theta=0.,x=0.,y=0.,z=0.):
    from OCP.gp import gp_Trsf,gp_Ax1,gp_Pnt,gp_Dir,gp_Vec
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    t=gp_Trsf();t.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,0,1)),theta)
    t.SetTranslationPart(gp_Vec(x,y,z))
    return BRepBuilderAPI_Transform(shape,t,True).Shape()


def solid(s,section,index):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism,BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Vec
    outer=wire(section.outer)
    if s.kind in ('helical','herringbone'):
        from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
        from OCP.TopoDS import TopoDS
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
        r=cylindrical(s,s.teeth1 if index==0 else s.teeth2)['r']
        hand=1 if index==0 else -1
        angle=s.width_mm*tan(s.helix_deg*pi/180)/r
        n=max(4,ceil(abs(angle)/(pi/60)))
        if n>80:raise ValueError('Helisel loft 80 kesit sınırını aşıyor; genişliği/helis açısını azaltın.')
        def half(start,end,reverse=False):
            loft=BRepOffsetAPI_ThruSections(True,False,1e-7);loft.CheckCompatibility(False);loft.SetMaxDegree(3)
            for i in range(n+1):
                z=start+(end-start)*i/n
                depth=z if not reverse else s.width_mm-z
                loft.AddWire(TopoDS.Wire(move(outer,hand*depth*tan(s.helix_deg*pi/180)/r,z=z)))
            loft.Build()
            if not loft.IsDone():raise ValueError('Helisel katı loft üretilemedi.')
            return loft.Shape()
        if s.kind=='helical':shape=half(0,s.width_mm)
        else:
            from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
            joined=BRepAlgoAPI_Fuse(half(0,s.width_mm/2),half(s.width_mm/2,s.width_mm,True));joined.Build()
            if not joined.IsDone():raise ValueError('Çift helisel orta birleşimi başarısız.')
            shape=joined.Shape()
        if section.bore:
            cut=BRepAlgoAPI_Cut(shape,BRepPrimAPI_MakeCylinder(section.bore/2,s.width_mm).Shape());cut.Build()
            if not cut.IsDone():raise ValueError('Helisel delik kesilemedi.')
            shape=cut.Shape()
    else:
        f=BRepBuilderAPI_MakeFace(outer,True)
        if section.inner:
            hole=wire(section.inner);hole.Reverse();f.Add(hole)
        if section.bore:
            from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire,BRepBuilderAPI_MakeEdge
            from OCP.gp import gp_Circ,gp_Ax2,gp_Pnt,gp_Dir
            hole=BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(),gp_Dir(0,0,1)),section.bore/2)).Edge()).Wire()
            hole.Reverse();f.Add(hole)
        if not f.IsDone():raise ValueError('Delikli dişli yüzeyi üretilemedi.')
        shape=BRepPrimAPI_MakePrism(f.Face(),gp_Vec(0,0,s.width_mm)).Shape()
    if kernel.shape_stats(shape)['solids']!=1:raise ValueError('Parça tek bir geçerli katı olmalı.')
    return shape


def placed(s,target='pair'):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    result=calculate(s)
    if not result.cad_available:raise ValueError('Bu mekanizmanın doğrulanmış CAD yüzeyi henüz yok.')
    if target not in ('pinion','wheel','pair'):raise ValueError('Bilinmeyen CAD hedefi.')
    with kernel._kernel_lock:
        sec=sections(s);built={}
        chosen=list(poses(s)) if target=='pair' else [(0 if target=='pinion' else (2 if s.kind=='planetary' else 1),0,0,0)]
        shapes=[]
        if s.kind=='cycloidal':
            if target=='wheel':chosen=[]
            else:chosen=[(0,0,0,0)] if target=='pinion' else list(poses(s))
        for idx,theta,x,y in chosen:
            if idx not in built:built[idx]=solid(s,sec[idx],idx)
            shapes.append(move(built[idx],theta,x,y))
        if s.kind=='cycloidal' and target!='pinion':
            if s.teeth2>80:raise ValueError('Sikloid takım CAD sınırı 80 pimdir.')
            roller=BRepPrimAPI_MakeCylinder(s.roller_radius_mm,s.width_mm).Shape();R=s.module_mm*s.teeth2/2
            for j in range(s.teeth2):shapes.append(move(roller,x=R*cos(2*pi*j/s.teeth2),y=R*sin(2*pi*j/s.teeth2)))
        return shapes
