"""Planar transverse DXF, true B-Rep STEP; shared atomic publication path."""
from math import cos,sin,pi,isclose
from pathlib import Path
from tempfile import TemporaryDirectory
import os
from .calculation import calculate
from .geometry import sections,sample,poses,verify,section_polygon
from ..geometry import rotate
from .. import cad as kernel


def export_cad(spec,path,*,target='pair',construction=True,overwrite=False):
    path=Path(path).absolute()
    if path.suffix.lower() not in ('.step','.stp','.dxf') or not path.parent.is_dir():raise ValueError('CAD yolu/uzantısı geçersiz.')
    if path.exists() and not overwrite:raise FileExistsError(str(path))
    if target not in ('pair','pinion','wheel'):raise ValueError('CAD hedefi geçersiz.')
    check=verify(spec)
    with TemporaryDirectory(prefix='.gokworks-family-',dir=path.parent) as folder:
        staged=Path(folder)/path.name
        if path.suffix.lower()=='.dxf':info=write_dxf(spec,target,staged,construction)
        else:
            from .cad import placed
            shapes=placed(spec,target);before=kernel.shape_stats(kernel.compound(shapes))
            kernel.write_step(shapes,staged);info=kernel.shape_stats(kernel.read_step(staged))
            if info['solids']!=len(shapes) or not isclose(info['volume_mm3'],before['volume_mm3'],rel_tol=1e-7,abs_tol=1e-5):raise ValueError('STEP yeniden okuma hacim/gövde hatası.')
            if any(abs(a-b)>1e-4 for a,b in zip(info['bounds_mm'],before['bounds_mm'])):raise ValueError('STEP boyutları değişti.')
            info.update(format='STEP',units='mm')
        if overwrite:os.replace(staged,path)
        else:os.link(staged,path)
    return dict(info,path=str(path),**check)


def write_dxf(s,target,path,construction):
    import ezdxf
    from ezdxf import units
    from shapely.geometry import Polygon
    calculate(s);sec=sections(s);doc=ezdxf.new('R2010');doc.units=units.MM
    for name in ('GEAR_PROFILE','BORE','PITCH_CIRCLE','CONSTRUCTION'):doc.layers.new(name)
    model=doc.modelspace();positions=list(poses(s))
    if target!='pair':positions=[(0 if target=='pinion' else (2 if s.kind=='planetary' else 1),0,0,0)]
    if s.kind=='cycloidal' and target=='wheel':positions=[]
    for idx,angle,x,y in positions:
        section=sec[idx];section_polygon(section,min(.005,s.module_mm/1000))
        for segments in (section.outer,section.inner):
            if segments:
                pts=[rotate(p,angle,(x,y)) for p in sample(segments,min(.005,s.module_mm/1000))[:-1]]
                model.add_lwpolyline(pts,close=True,dxfattribs={'layer':'GEAR_PROFILE'})
        if section.bore:model.add_circle((x,y),section.bore/2,dxfattribs={'layer':'BORE'})
        model.add_point((x,y),dxfattribs={'layer':'CONSTRUCTION'})
        if construction and s.kind in ('helical','herringbone','internal','planetary'):
            from .calculation import cylindrical
            z=(s.teeth1 if idx==0 else s.teeth2 if idx==1 else s.teeth1+2*s.teeth2)
            r=(cylindrical(s,z)['r'] if s.kind in ('helical','herringbone') else s.module_mm*z/2)
            model.add_circle((x,y),r,dxfattribs={'layer':'PITCH_CIRCLE'})
    if s.kind=='cycloidal' and target!='pinion':
        R=s.module_mm*s.teeth2/2
        for j in range(s.teeth2):model.add_circle((R*cos(2*pi*j/s.teeth2),R*sin(2*pi*j/s.teeth2)),s.roller_radius_mm,dxfattribs={'layer':'GEAR_PROFILE'})
    doc.saveas(path);read=ezdxf.readfile(path)
    if read.units!=units.MM or read.audit().has_errors:raise ValueError('DXF tekrar okuma başarısız.')
    contours=list(read.modelspace().query('LWPOLYLINE'))
    for entity in contours:
        if not entity.closed or not Polygon([(p[0],p[1]) for p in entity.get_points()]).is_valid:raise ValueError('DXF konturu açık veya kendini kesiyor.')
    return dict(format='DXF',units='mm',contours=len(contours),section='z=0 alın kesiti; helis/konik yüzeyi temsil etmez')
