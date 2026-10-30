"""Non-destructive checks for native DXF output; no geometry repair or remapping."""
import math
import ezdxf
from modules.cad_converter.models import checkpoint


def validate_flat_geometry(path, stop=None):
    """Reject nonfinite/degenerate and exactly repeated common curve entities.

    Checks are layer-aware so bend and cut semantics stay intact. This is not
    a full CAM/self-intersection proof, nor a binary DWG geometry validator.
    """
    document = ezdxf.readfile(path)
    seen = set()
    def point(p):
        values = tuple(float(v) for v in p)
        if not all(math.isfinite(v) for v in values):
            raise ValueError('DXF sonlu olmayan koordinat içeriyor.')
        return tuple(round(v,9) for v in values)
    count = 0
    def visit(entities,depth=0,parent_layer=None):
        nonlocal count
        if depth>16:
            raise ValueError('DXF BLOCK derinliği sınırı aşıldı.')
        for entity in entities:
            checkpoint(stop);count+=1
            if count>200000:
                raise ValueError('DXF geometri denetimi 200.000 öğe sınırını aştı.')
            kind = entity.dxftype(); layer=entity.dxf.layer
            if layer=='0' and parent_layer:layer=parent_layer
            geometry = None
            if kind=='INSERT':
                if entity.mcount>1000:
                    raise ValueError('DXF BLOCK tekrar sınırı aşıldı.')
                for insert in entity.multi_insert() if entity.mcount>1 else (entity,):
                    skipped=[]
                    visit(insert.virtual_entities(skipped_entity_callback=lambda *args:skipped.append(True)),depth+1,layer)
                    if skipped:raise ValueError('DXF BLOCK geometrisi doğrulanamadı.')
            elif kind=='LINE':
                a,b=point(entity.dxf.start),point(entity.dxf.end)
                if a==b:raise ValueError('DXF sıfır uzunluklu çizgi içeriyor.')
                geometry=tuple(sorted((a,b)))
            elif kind in ('CIRCLE','ARC'):
                radius=float(entity.dxf.radius)
                if not math.isfinite(radius) or radius<=0:raise ValueError('DXF geçersiz yay/daire yarıçapı içeriyor.')
                geometry=(point(entity.dxf.center),round(radius,9),point(entity.dxf.extrusion))
                if kind=='ARC':geometry+=tuple(point((entity.dxf.start_angle,entity.dxf.end_angle)))
            elif kind=='LWPOLYLINE':
                points=tuple(point(p) for p in entity.get_points('xyseb'))
                if len(points)<2:raise ValueError('DXF geçersiz polyline içeriyor.')
                geometry=(points,bool(entity.closed),float(entity.dxf.elevation),point(entity.dxf.extrusion))
            if geometry is not None:
                token=(kind,layer,geometry)
                if token in seen:raise ValueError('DXF aynı katmanda mükerrer kesim geometrisi içeriyor; çıktı yayımlanmadı.')
                seen.add(token)
    visit(document.modelspace())
