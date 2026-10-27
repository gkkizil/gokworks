"""Validated DXF/STEP exports with atomic publication and independent re-read."""

from math import isclose
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from .calculation import calculate_pair
from .geometry import gear_profile, rotate, pair_angles, verify_mesh
from .validation import require_manufacturable


def _selected(spec,target):
    result=calculate_pair(spec);require_manufacturable(result)
    if target=='pinion':return [(spec.pinion,0.,(0.,0.))]
    if target=='wheel':return [(spec.wheel,0.,(0.,0.))]
    if target=='pair':return [(spec.pinion,0.,(0.,0.)),(spec.wheel,pair_angles(spec)[1],(result.center_distance_mm,0.))]
    raise ValueError('Aktarım hedefi pinyon, çark veya takım olmalı.')


def _dxf(spec,target,path,construction):
    import ezdxf
    from ezdxf import units
    from .calculation import calculate_gear
    doc=ezdxf.new('R2010');doc.units=units.MM
    for name,color in (('GEAR_PROFILE',7),('BORE',3),('PITCH_CIRCLE',4),('BASE_CIRCLE',5),('CONSTRUCTION',8)):
        doc.layers.new(name,dxfattribs=dict(color=color))
    space=doc.modelspace()
    for gear,angle,center in _selected(spec,target):
        profile=gear_profile(gear)
        tolerance=min(.005,gear.module_mm*.0025)
        points=[rotate(p,angle,center) for p in profile.points(tolerance)[:-1]]
        space.add_lwpolyline(points,close=True,dxfattribs={'layer':'GEAR_PROFILE'})
        if gear.bore_mm:
            space.add_circle(center,gear.bore_mm/2,dxfattribs={'layer':'BORE'})
        space.add_point(center,dxfattribs={'layer':'CONSTRUCTION'})
        if construction:
            g=calculate_gear(gear)
            for layer,r in (('PITCH_CIRCLE',g.pitch_radius_mm),('BASE_CIRCLE',g.base_radius_mm),
                            ('CONSTRUCTION',g.outside_radius_mm),('CONSTRUCTION',g.root_radius_mm)):
                space.add_circle(center,r,dxfattribs={'layer':layer})
    doc.saveas(path)
    read=ezdxf.readfile(path)
    if read.units!=units.MM or read.audit().has_errors:
        raise ValueError('DXF birimi/yapısı tekrar okumada doğrulanamadı.')
    from shapely.geometry import Polygon
    contours=list(read.modelspace().query('LWPOLYLINE[layer=="GEAR_PROFILE"]'))
    if len(contours)!=len(_selected(spec,target)):
        raise ValueError('DXF dişli kontur sayısı hatalı.')
    for contour in contours:
        p=Polygon([(v[0],v[1]) for v in contour.get_points()])
        if not contour.closed or not p.is_valid or p.area<=0:
            raise ValueError('DXF konturu kapalı/basit değil.')
    return dict(format='DXF',gears=len(contours),units='mm',chord_tolerance_mm=min(.005,spec.pinion.module_mm*.0025),
                curve_tolerance_mm=gear_profile(spec.pinion).curve_tolerance_mm)


def _step(spec,target,path):
    import OCP
    from . import cad
    shapes=cad.placed_gears(spec,target)
    before=cad.shape_stats(cad.compound(shapes))
    cad.write_step(shapes,path)
    after=cad.shape_stats(cad.read_step(path))
    if after['solids']!=len(shapes) or not isclose(before['volume_mm3'],after['volume_mm3'],rel_tol=1e-7,abs_tol=1e-5):
        raise ValueError('STEP yeniden okumada katı sayısı/hacmi değişti.')
    if any(abs(a-b)>1e-4 for a,b in zip(before['bounds_mm'],after['bounds_mm'])):
        raise ValueError('STEP yeniden okumada model boyutları değişti.')
    return dict(format='STEP',units='mm',**after,curve_tolerance_mm=gear_profile(spec.pinion).curve_tolerance_mm,
                kernel_version=OCP.__version__,kernel_module_path=OCP.__file__)


def export_cad(spec,path,*,target='pair',construction=True,overwrite=False):
    """Existing destination is preserved on failure; no silent replacement."""
    path=Path(path).absolute()
    if path.suffix.lower() not in ('.dxf','.step','.stp') or not path.parent.is_dir():
        raise ValueError('Mevcut bir klasör ve .dxf/.step/.stp dosya adı seçin.')
    if path.exists() and not overwrite:
        raise FileExistsError(str(path))
    _selected(spec,target)
    check=verify_mesh(spec)
    with TemporaryDirectory(prefix='.gokworks-gear-',dir=path.parent) as folder:
        temp=Path(folder)/('gear'+path.suffix.lower())
        result=_dxf(spec,target,temp,construction) if path.suffix.lower()=='.dxf' else _step(spec,target,temp)
        if not temp.is_file() or temp.stat().st_size==0:
            raise ValueError('CAD dosyası boş.')
        if overwrite:
            os.replace(temp,path)
        else:
            # Atomic no-clobber: refuse a destination created during calculation.
            os.link(temp,path)
        return dict(path=str(path),**result,mesh_samples=check.samples,maximum_overlap_mm2=check.maximum_overlap_mm2)
