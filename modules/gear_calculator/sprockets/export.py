"""Validated round trips and atomic publication; exact circular DXF bulges."""
from pathlib import Path
from tempfile import TemporaryDirectory
from math import cos,sin,tan,pi,isclose
import os
from .geometry import profile,verify
from .calculation import calculate
from .. import cad as kernel


def write_dxf(s,path,target,construction):
    import ezdxf
    from ezdxf.path import make_path
    from shapely.geometry import Polygon
    r=calculate(s);doc=ezdxf.new('R2010');doc.units=4
    for name in ('SPROCKET_PROFILE','BORE','PITCH_CIRCLE','ROLLER_CENTERS','CONSTRUCTION'):doc.layers.new(name)
    chosen=[(s.driver,0.)] if target=='pinion' else [(s.driven,0.)] if target=='wheel' else [(s.driver,0.),(s.driven,r.corrected_center_mm)]
    model=doc.modelspace()
    for wheel,x in chosen:
        arcs=profile(wheel);vertices=[]
        for a in arcs:
            p=a.point(0);vertices.append((p[0]+x,p[1],tan((a.end-a.start)/4)))
        model.add_lwpolyline(vertices,format='xyb',close=True,dxfattribs={'layer':'SPROCKET_PROFILE'})
        if wheel.bore_mm:model.add_circle((x,0),wheel.bore_mm/2,dxfattribs={'layer':'BORE'})
        model.add_point((x,0),dxfattribs={'layer':'CONSTRUCTION'})
        if construction:
            from .calculation import dimensions
            radius=dimensions(wheel).pitch_diameter_mm/2
            model.add_circle((x,0),radius,dxfattribs={'layer':'PITCH_CIRCLE'})
            if wheel.hub_diameter_mm:model.add_circle((x,0),wheel.hub_diameter_mm/2,dxfattribs={'layer':'CONSTRUCTION'})
            for j in range(wheel.teeth):model.add_point((x+radius*cos(2*pi*j/wheel.teeth),radius*sin(2*pi*j/wheel.teeth)),dxfattribs={'layer':'ROLLER_CENTERS'})
    doc.saveas(path);read=ezdxf.readfile(path)
    if read.units!=4 or read.audit().has_errors:raise ValueError('Zincir dişlisi DXF birimi veya dosyası geçersiz.')
    contours=list(read.modelspace().query('LWPOLYLINE[layer=="SPROCKET_PROFILE"]'))
    if len(contours)!=len(chosen):raise ValueError('DXF zincir dişlisi kontur sayısı değişti.')
    for entity in contours:
        p=Polygon([(v.x,v.y) for v in make_path(entity).flattening(.0005)])
        if not entity.closed or not p.is_valid or p.area<=0:raise ValueError('DXF profil konturu açık/kendini kesiyor.')
    return dict(format='DXF',units='mm',contours=len(contours),profile_curves='exact circular bulges',chain_included=False,hub_section='z=0 tooth plate')


def export_cad(s,path,*,target='pair',construction=True,overwrite=False):
    path=Path(path).absolute()
    if target not in ('pinion','wheel','pair'):raise ValueError('CAD hedefi geçersiz.')
    if path.suffix.lower() not in ('.dxf','.step','.stp') or not path.parent.is_dir():raise ValueError('CAD klasörü/uzantısı geçersiz.')
    if path.exists() and not overwrite:raise FileExistsError(str(path))
    check=verify(s)
    with TemporaryDirectory(prefix='.gokworks-sprocket-',dir=path.parent) as folder:
        staged=Path(folder)/path.name
        if path.suffix.lower()=='.dxf':info=write_dxf(s,staged,target,construction)
        else:
            from .cad import placed
            shapes=placed(s,target);before=kernel.shape_stats(kernel.compound(shapes))
            kernel.write_step(shapes,staged);info=kernel.shape_stats(kernel.read_step(staged))
            if info['solids']!=len(shapes) or not isclose(info['volume_mm3'],before['volume_mm3'],rel_tol=1e-7,abs_tol=1e-5):
                raise ValueError('STEP yeniden okuma hacim/gövde doğrulaması başarısız.')
            if any(abs(a-b)>1e-4 for a,b in zip(info['bounds_mm'],before['bounds_mm'])):raise ValueError('STEP ölçüleri yeniden okumada değişti.')
            info.update(format='STEP',units='mm',chain_included=False)
        if overwrite:os.replace(staged,path)
        else:os.link(staged,path)
    return dict(info,path=str(path),**check)
