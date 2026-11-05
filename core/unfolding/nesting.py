"""Adapter to the existing polygon nesting contract; original cut curves stay intact."""
from .geometry import polygon
from .validation import integer


def to_nesting_parts(result,*,quantity_multiplier=1):
    from io import StringIO
    import ezdxf
    from modules.nesting.models import Part
    from shapely.geometry import mapping
    from .dxf import _cut
    if result.status!='success':raise ValueError('Nesting için başarılı hesap gerekli.')
    integer(quantity_multiplier,'Adet çarpanı',1,1000000)
    n=result.normalized_inputs;o=n['development_options'];material=n['material']['name']
    if n['thickness']<=0 or not material:raise ValueError('Nesting için pozitif kalınlık ve malzeme adı gerekli.')
    parts=[]
    for p in result.parts:
        doc=ezdxf.new('R2013');doc.units=4
        for layer in ('CUT_OUTER','CUT_INNER'):doc.layers.new(layer)
        _cut(doc.modelspace(),p.geometry_2d.outer,'CUT_OUTER')
        for h in p.geometry_2d.holes:_cut(doc.modelspace(),h,'CUT_INNER')
        # Existing nesting flattens virtual LWPOLYLINE arcs in CCW order.
        # Keep exact clockwise bulges as independent native ARC/LINE entities,
        # so contour matching does not join their sampled endpoints backwards.
        model=doc.modelspace()
        for entity in list(model.query('LWPOLYLINE')):
            if entity.has_arc:
                for child in entity.virtual_entities():model.add_entity(child.copy())
                model.delete_entity(entity)
        source=StringIO();doc.write(source)
        parts.append(Part(id=f'{result.request_id}:{p.id}',code=p.code,
        geometry=mapping(polygon(p.geometry_2d,o['chord_error_mm'],o['max_samples'])),
        material=material,thickness=n['thickness'],quantity=p.quantity*quantity_multiplier,
        description=f'Sac açınımı {result.calculation_method}; özgün yaylar DXF çıktısındadır.',
        source=f'gokworks.unfolding:{result.request_id}:r{result.revision}',source_sha256=result.input_hash,
        curve_tolerance=o['chord_error_mm'],join_tolerance=o['geometry_tolerance_mm'],source_unit='mm',
        original_dxf=source.getvalue()))
    return tuple(parts)
