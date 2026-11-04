"""Read a DXF into DFM contours (mm). The source file is only read.

Reuses the nesting reader's safe opener (Turkish errors for empty/broken
files) and its curve flattening (native ARC/CIRCLE/ELLIPSE/SPLINE
evaluators, bulges through ezdxf virtual entities). Unlike nesting, nothing
unknown stops the read: it is listed so the report can say what was not
checked.
"""

import math
from pathlib import Path

from ezdxf import units
from ezdxf.math import Matrix44

from modules.nesting.dxf_import import flatten_entity, open_dxf
from ..models import Drawing

CUT = {'LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ELLIPSE'}
ANNOTATION = {'TEXT', 'MTEXT', 'DIMENSION', 'LEADER', 'MLEADER', 'ATTDEF', 'ATTRIB', 'HATCH', 'SOLID',
              'POINT', 'TOLERANCE', 'ARC_DIMENSION', 'WIPEOUT', 'IMAGE', 'VIEWPORT'}
# Layer names that carry bend lines rather than cuts (SOLIDWORKS, generic CAM, Turkish).
BEND_LAYER_WORDS = ('BEND', 'BUKUM', 'BÜKÜM', 'BÜKUM', 'BUKÜM')
UNIT_CODES = {'mm': units.MM, 'cm': units.CM, 'm': units.M, 'inch': units.IN}


class MissingUnits(ValueError):
    """The DXF has no $INSUNITS; the caller must choose the unit."""


def is_bend_layer(name):
    upper = str(name).upper()
    return any(word in upper for word in BEND_LAYER_WORDS)


def read(path, *, unit=None, tolerance=.01, excluded_layers=(), stop=None):
    """Return ``(Drawing, file_bytes)``. ``tolerance`` is the chord error in mm."""
    path = Path(path)
    before = path.read_bytes()
    doc = open_dxf(path)
    code = doc.header.get('$INSUNITS', 0)
    source_unit = units.unit_name(code) if code else ''
    if not code:
        if unit not in UNIT_CODES:
            raise MissingUnits(f'{path.name}: DXF birimi ($INSUNITS) tanımlı değil. Birimi seçin (mm, cm, m veya inch).')
        code, source_unit = UNIT_CODES[unit], unit + ' (kullanıcı seçimi)'
    try:
        scale = units.conversion_factor(code, units.MM)
    except (TypeError, ValueError, KeyError):
        raise ValueError(f'DXF birimi desteklenmiyor ($INSUNITS={code}).') from None
    excluded = {str(name) for name in excluded_layers}
    excluded |= {layer.dxf.name for layer in doc.layers if layer.is_off() or layer.is_frozen()}
    contours, ignored, unsupported = [], [], {}

    def visit(entities, depth=0, inherited=None, owner=''):
        if depth > 20:
            unsupported[('INSERT', '', 'iç içe BLOCK derinliği 20 sınırını aşıyor')] = \
                unsupported.get(('INSERT', '', 'iç içe BLOCK derinliği 20 sınırını aşıyor'), 0) + 1
            return
        for index, entity in enumerate(entities):
            if stop is not None and stop.is_set():
                raise InterruptedError('Analiz durduruldu.')
            kind = entity.dxftype()
            layer = inherited if entity.dxf.layer == '0' and inherited else entity.dxf.layer
            handle = owner + (f'/{index}' if owner else str(entity.dxf.handle or index))
            if layer in excluded:
                ignored.append((kind, layer, 'katman dışlandı veya kapalı'))
                continue
            if kind == 'INSERT':
                skipped = []
                for insert in (entity.multi_insert() if entity.mcount > 1 else [entity]):
                    virtual = list(insert.virtual_entities(skipped_entity_callback=lambda e, reason: skipped.append(reason)))
                    for reason in skipped:
                        key = ('INSERT', layer, reason)
                        unsupported[key] = unsupported.get(key, 0) + 1
                    visit(virtual, depth + 1, layer, handle)
                continue
            if kind in ANNOTATION:
                ignored.append((kind, layer, 'kesim dışı açıklama/tarama nesnesi'))
                continue
            if kind not in CUT:
                key = (kind, layer, 'desteklenmeyen nesne; kontrol edilmedi')
                unsupported[key] = unsupported.get(key, 0) + 1
                continue
            if is_bend_layer(layer):
                ignored.append((kind, layer, 'büküm katmanı; kesim konturu sayılmadı'))
                continue
            entity = entity.copy()
            entity.transform(Matrix44.scale(scale))
            try:
                vertices, closed, curved = flatten_entity(entity, tolerance)
            except Exception as error:
                key = (kind, layer, f'geometri okunamadı: {error}')
                unsupported[key] = unsupported.get(key, 0) + 1
                continue
            if not vertices:
                continue
            if any(abs(v.z) > 1e-6 for v in vertices):
                key = (kind, layer, 'XY düzleminde değil (Z ≠ 0); kontrol edilmedi')
                unsupported[key] = unsupported.get(key, 0) + 1
                continue
            points = [(float(v.x), float(v.y)) for v in vertices]
            circle = None
            if kind == 'CIRCLE':
                c = entity.dxf.center
                circle = (float(c.x), float(c.y), float(entity.dxf.radius))
            if closed and points[0] != points[-1]:
                points.append(points[0])
            contours.append(dict(handle=handle, kind=kind, layer=str(layer), points=points, closed=bool(closed),
                                 circle=circle, curved=bool(curved)))

    visit(doc.modelspace())
    xs = [p[0] for c in contours for p in c['points']]
    ys = [p[1] for c in contours for p in c['points']]
    bounds = (min(xs), min(ys), max(xs), max(ys)) if xs else None
    if any(not math.isfinite(v) for v in (bounds or ())):
        raise ValueError('DXF sonlu olmayan koordinat içeriyor.')
    if path.read_bytes() != before:
        raise ValueError('DXF okunurken değişti; yeniden açın.')
    drawing = Drawing(contours=contours, unit='mm', source_unit=source_unit, bounds=bounds,
                      ignored=ignored, unsupported=[(k, l, r, n) for (k, l, r), n in sorted(unsupported.items())])
    return drawing, before
