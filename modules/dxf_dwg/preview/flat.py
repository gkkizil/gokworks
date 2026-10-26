"""Display actual exported DXF entities, preserving holes, bends and colours."""

import math
from pathlib import Path

import ezdxf
from ezdxf import units, colors

from modules.cad_converter.models import checkpoint
from modules.nesting.dxf_import import flatten_entity, SUPPORTED
from .models import Flat, Stroke

MAX_POINTS = 200000


def read_flat(path, description='DXF çıktısı', stop=None):
    path = Path(path)
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError('Açınım önizlemesi 50 MB sınırını aşıyor.')
    doc = ezdxf.readfile(path)
    code = doc.header.get('$INSUNITS', 0)
    warnings = []
    if code:
        scale = units.conversion_factor(code, units.MM)
    else:
        scale = 1.
        warnings.append('DXF birimi tanımlı değil; çizim birimi gösteriliyor, mm ölçümü yapılmadı.')
    strokes, unsupported = [], set()
    point_count = 0
    length = 0.

    def visit(entities, parent_layer=None, depth=0):
        nonlocal point_count, length
        if depth > 16:
            raise ValueError('Açınımdaki BLOCK derinliği sınırı aşıldı.')
        for entity in entities:
            checkpoint(stop)
            layer_name = parent_layer if entity.dxf.layer == '0' and parent_layer else entity.dxf.layer
            layer = doc.layers.get(layer_name)
            if layer.is_off() or layer.is_frozen() or entity.dxf.get('invisible', 0):
                continue
            kind = entity.dxftype()
            if kind == 'INSERT':
                if entity.mcount > 1000:
                    raise ValueError('Açınım BLOCK tekrar sınırı aşıldı.')
                skipped = []
                for insert in entity.multi_insert() if entity.mcount > 1 else (entity,):
                    visit(insert.virtual_entities(skipped_entity_callback=lambda *a: skipped.append(True)), layer_name, depth + 1)
                if skipped:
                    unsupported.add('dönüştürülemeyen BLOCK öğesi')
                continue
            if kind not in SUPPORTED:
                if kind not in ('TEXT', 'MTEXT', 'DIMENSION', 'LEADER', 'MLEADER', 'POINT', 'HATCH'):
                    unsupported.add(kind)
                continue
            points, closed, _ = flatten_entity(entity, max(.02 / scale, 1e-6))
            points = [(float(p[0]) * scale, float(p[1]) * scale) for p in points]
            if closed and points and points[-1] != points[0]:
                points.append(points[0])
            point_count += len(points)
            if point_count > MAX_POINTS or not all(math.isfinite(v) for p in points for v in p):
                raise ValueError('Açınım nokta sınırı aşıldı veya koordinatlar geçersiz.')
            if len(points) < 2:
                continue
            aci = entity.dxf.get('color', 256)
            aci = abs(layer.dxf.color) if aci in (0, 256) else abs(aci)
            rgb = entity.rgb or layer.rgb
            if rgb is None:
                rgb = colors.aci2rgb(aci if 1 <= aci <= 255 else 7)
            color = '#%02x%02x%02x' % tuple(rgb)
            if min(rgb) > 220:
                color = '#475569'  # white BYLAYER remains visible on white paper
            bend = any(word in layer_name.casefold() for word in ('bend', 'bük', 'buk'))
            strokes.append(Stroke(tuple(points), color, layer_name, bend))
            if not bend:
                length += sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    visit(doc.modelspace())
    if not strokes:
        raise ValueError('Açınımda görüntülenebilir kesim konturu bulunamadı.')
    if unsupported:
        warnings.append('Gösterilemeyen DXF öğeleri: ' + ', '.join(sorted(unsupported)))
    coordinates = [p for s in strokes for p in s.points]
    bounds = (min(p[0] for p in coordinates), min(p[1] for p in coordinates),
              max(p[0] for p in coordinates), max(p[1] for p in coordinates))
    return Flat(tuple(strokes), bounds, description, length if code and not unsupported else None, tuple(warnings))
