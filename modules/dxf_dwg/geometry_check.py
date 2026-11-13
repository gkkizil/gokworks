"""Non-destructive checks for native DXF output; no geometry repair or remapping."""
import math
import ezdxf
from modules.cad_converter.models import checkpoint


def validate_flat_geometry(path, stop=None, *, document=None):
    """Reject nonfinite/degenerate and exactly repeated common curve entities.

    Checks are layer-aware so bend and cut semantics stay intact. This is not
    a full CAM/self-intersection proof, nor a binary DWG geometry validator.
    """
    if document is None:
        document = ezdxf.readfile(path)
    seen = set()
    def point(p):
        values = tuple(float(v) for v in p)
        if not all(math.isfinite(v) for v in values):
            raise ValueError('DXF sonlu olmayan koordinat içeriyor.')
        return tuple(round(v,9) for v in values)
    count = geometric = 0
    def visit(entities,depth=0,parent_layer=None):
        nonlocal count, geometric
        if depth>16:
            raise ValueError('DXF BLOCK derinliği sınırı aşıldı.')
        for entity in entities:
            checkpoint(stop);count+=1
            if count>200000:
                raise ValueError('DXF geometri denetimi 200.000 öğe sınırını aştı.')
            kind = entity.dxftype(); layer=entity.dxf.layer
            if kind in ('LINE','CIRCLE','ARC','LWPOLYLINE','POLYLINE','ELLIPSE','SPLINE'):
                geometric += 1
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
                elevation=float(entity.dxf.elevation)
                if not math.isfinite(elevation):raise ValueError('DXF sonlu olmayan polyline yüksekliği içeriyor.')
                geometry=(points,bool(entity.closed),elevation,point(entity.dxf.extrusion))
            elif kind=='POLYLINE':
                point(entity.dxf.elevation);point(entity.dxf.extrusion)
                vertices=entity.vertices
                for vertex in vertices:
                    point(vertex.dxf.location)
                    point((vertex.dxf.bulge,vertex.dxf.start_width,vertex.dxf.end_width))
                # Mesh/polyface flags and topology differ from a 2D contour;
                # validate their coordinates without equating their geometry.
                if entity.is_2d_polyline:
                    if len(vertices)<2:raise ValueError('DXF geçersiz polyline içeriyor.')
                    geometry=(tuple((point(v.dxf.location),v.dxf.bulge,v.dxf.start_width,v.dxf.end_width)
                                    for v in vertices),entity.dxf.flags,point(entity.dxf.elevation),point(entity.dxf.extrusion))
            elif kind=='ELLIPSE':
                center=point(entity.dxf.center);major=point(entity.dxf.major_axis)
                extrusion=point(entity.dxf.extrusion)
                ratio,start,end=point((entity.dxf.ratio,entity.dxf.start_param,entity.dxf.end_param))
                if not any(entity.dxf.major_axis) or not 0<entity.dxf.ratio<=1:
                    raise ValueError('DXF geçersiz elips içeriyor.')
                geometry=(center,major,extrusion,ratio,start,end)
            elif kind=='SPLINE':
                for vertex in entity.control_points:point(vertex)
                for vertex in entity.fit_points:point(vertex)
                point(entity.knots);point(entity.weights)
                for name in ('start_tangent','end_tangent','extrusion'):
                    value=entity.dxf.get(name)
                    if value is not None:point(value)
            if geometry is not None:
                token=(kind,layer.casefold(),geometry)
                if token in seen:raise ValueError('DXF aynı katmanda mükerrer kesim geometrisi içeriyor; çıktı yayımlanmadı.')
                seen.add(token)
    visit(document.modelspace())
    if not geometric:
        raise ValueError('DXF kesim çizgisi veya eğrisi içermiyor; çıktı yayımlanmadı.')
