"""Strict DXF modelspace contours, explicit units, blocks and portable source geometry."""

from collections import Counter, defaultdict
import math
import hashlib
from io import StringIO
from pathlib import Path

import ezdxf
from ezdxf import units
from ezdxf.math import Matrix44
from shapely import affinity, union_all
from shapely.geometry import LineString, Polygon, MultiPolygon
from shapely.ops import polygonize_full
from shapely.strtree import STRtree
from shapely.validation import explain_validity

from modules.nesting.models import Part, number

SUPPORTED = {'LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ELLIPSE'}
ANNOTATIONS = {'TEXT', 'MTEXT', 'DIMENSION', 'LEADER', 'MLEADER', 'POINT', 'HATCH', 'SOLID', 'ATTDEF', 'ATTRIB'}


def flatten_entity(entity, tolerance):
    """Use native circular/elliptic evaluators: cubic Beziers add their own error."""
    kind = entity.dxftype()
    if kind == 'LINE':
        return [entity.dxf.start, entity.dxf.end], False, False
    if kind in ('CIRCLE','ARC'):
        return list(entity.flattening(tolerance)), kind == 'CIRCLE', True
    if kind == 'ELLIPSE':
        closed = abs((entity.dxf.end_param-entity.dxf.start_param)-2*math.pi) < 1e-8
        return list(entity.flattening(tolerance, segments=8)), closed, True
    if kind == 'SPLINE':
        return list(entity.flattening(tolerance, segments=8)), entity.closed, True
    if kind in ('LWPOLYLINE','POLYLINE'):
        points = []; curved = False
        for child in entity.virtual_entities():
            vertices, _, child_curved = flatten_entity(child,tolerance)
            points.extend(vertices if not points else vertices[1:]); curved |= child_curved
        return points, entity.closed if kind == 'LWPOLYLINE' else entity.is_closed, curved
    raise ValueError('Desteklenmeyen DXF konturu: '+kind)


class MissingUnits(ValueError):
    pass


def check_cancel(stop):
    if stop is not None and stop.is_set():
        raise InterruptedError('İşlem durduruldu.')


def layers(path):
    doc = ezdxf.readfile(path)
    return [(layer.dxf.name, not layer.is_off() and not layer.is_frozen()) for layer in doc.layers]


def _entities(entities, doc, excluded, stop, depth=0, inherited=None):
    if depth > 20:
        raise ValueError('İç içe BLOCK derinliği 20 sınırını aşıyor.')
    for e in entities:
        check_cancel(stop)
        layer = inherited if e.dxf.layer == '0' and inherited else e.dxf.layer
        if layer in excluded:
            continue
        if e.dxftype() == 'INSERT':
            skipped = []
            inserts = e.multi_insert() if e.mcount > 1 else [e]
            for insert in inserts:
                virtual = list(insert.virtual_entities(skipped_entity_callback=lambda entity, reason: skipped.append(reason)))
                if skipped:
                    raise ValueError('BLOCK dönüşümü okunamadı: ' + '; '.join(skipped))
                yield from _entities(virtual, doc, excluded, stop, depth+1, layer)
        elif e.dxftype() in SUPPORTED:
            yield e
        elif e.dxftype() not in ANNOTATIONS:
            raise ValueError(f'{e.dxftype()}: desteklenmeyen kesim objesi. Katmanı dışlayın veya DXF geometrisine dönüştürün.')


def read_dxf(filename, *, material='S235JR', thickness=2, quantity=1, unit=None,
             tolerance=.02, join_tolerance=.001, excluded_layers=None, grouped=False, stop=None):
    tolerance = number(tolerance, 'Eğri toleransı', positive=True)
    join_tolerance = number(join_tolerance, 'Uç birleştirme toleransı', positive=True)
    if tolerance > 1 or join_tolerance > .1:
        raise ValueError('Eğri toleransı en fazla 1 mm; uç birleştirme toleransı en fazla 0,1 mm olabilir.')
    filename = Path(filename)
    if filename.stat().st_size > 100*1024*1024:
        raise ValueError('DXF dosyası 100 MB sınırını aşıyor; kesim katmanlarını ayrı dosyaya aktarın.')
    before = filename.read_bytes()
    doc = ezdxf.readfile(filename)
    code = doc.header.get('$INSUNITS', 0)
    if not code:
        if unit not in ('mm', 'cm', 'inch'):
            raise MissingUnits(filename.name + ': DXF birimi tanımlı değil. mm, cm veya inch seçin.')
        code = {'mm': units.MM, 'cm': units.CM, 'inch': units.IN}[unit]
    try:
        scale = units.conversion_factor(code, units.MM)
        source_unit = units.unit_name(code)
    except (TypeError, ValueError, KeyError):
        raise ValueError('DXF $INSUNITS birimi desteklenmiyor.') from None
    excluded = set(excluded_layers or [])
    excluded.update(layer.dxf.name for layer in doc.layers if layer.is_off() or layer.is_frozen())
    records = []; ends = Counter(); curved = False; endpoint_error = 0.
    endpoints = defaultdict(list)
    def snap(point):
        nonlocal endpoint_error
        key = tuple(math.floor(c/join_tolerance) for c in point)
        for i in (-1,0,1):
            for j in (-1,0,1):
                for candidate in endpoints[(key[0]+i,key[1]+j)]:
                    distance = math.dist(point,candidate)
                    if distance <= join_tolerance:
                        endpoint_error = max(endpoint_error,distance)
                        return candidate
        endpoints[key].append(point)
        return point
    for entity in _entities(doc.modelspace(), doc, excluded, stop):
        entity = entity.copy()
        entity.transform(Matrix44.scale(scale))
        try:
            vertices, closed, has_curves = flatten_entity(entity,tolerance)
        except Exception as error:
            raise ValueError(f'{entity.dxftype()} geometrisi okunamadı: {error}') from error
        if not vertices:
            continue
        if max(abs(v.z-vertices[0].z) for v in vertices) > join_tolerance or abs(vertices[0].z) > join_tolerance:
            raise ValueError('Kesim konturları XY düzleminde (Z=0) olmalı; 3B konturlar otomatik izdüşürülmez.')
        points = [(v.x, v.y) for v in vertices]
        if closed:
            points[-1] = points[0]
        else:
            points[0] = snap(points[0]); points[-1] = snap(points[-1])
            ends[points[0]] += 1; ends[points[-1]] += 1
        line = LineString(points)
        if line.length <= join_tolerance or not line.is_simple:
            raise ValueError('Sıfır uzunluklu veya kendi kendini kesen kontur bulundu.')
        curved |= has_curves
        records.append((entity, line))
        if sum(len(r[1].coords) for r in records) > 20000:
            raise ValueError('DXF, 20000 kontur noktası sınırını aşıyor. Eğri toleransını gözden geçirin.')
    if not records:
        raise ValueError('Seçilen katmanlarda kesim konturu yok.')
    if any(v != 2 for v in ends.values()):
        raise ValueError('Açık veya dallanan kontur bulundu. DXF uçlarını kapatın ya da yardımcı katmanları dışlayın.')
    lines = [r[1] for r in records]; tree = STRtree(lines)
    for i, line in enumerate(lines):
        check_cancel(stop)
        if any(int(j) > i for j in tree.query(line, predicate='crosses')):
            raise ValueError('Kesim konturları birbirini kesiyor; geometriyi düzeltin.')
    merged = union_all(lines)
    if sum(l.length for l in lines)-merged.length > join_tolerance:
        raise ValueError('Üst üste binen veya yinelenmiş kesim çizgileri bulundu.')
    faces, cuts, dangles, invalid = polygonize_full(merged)
    if not cuts.is_empty or not dangles.is_empty or not invalid.is_empty:
        raise ValueError('Açık, hatalı veya kendi kendini kesen kesim konturu bulundu.')
    # polygonize returns each face and hole again; extract unique closed rings,
    # then classify by containment depth (outer, hole, island, ...).
    rings = {}
    for face in faces.geoms:
        for ring in [face.exterior, *face.interiors]:
            p = Polygon(ring)
            rings[p.normalize().wkb] = p
    loops = list(rings.values())
    for i, p in enumerate(loops):
        if not p.is_valid or p.area <= 0:
            raise ValueError('Geçersiz kontur: ' + explain_validity(p))
        for other in loops[i+1:]:
            if p.boundary.intersects(other.boundary):
                raise ValueError('Konturlar birbirine değiyor veya çakışıyor; üretim geometrisini ayırın.')
    parents = {i: [j for j, q in enumerate(loops) if j != i and q.contains(p)] for i, p in enumerate(loops)}
    components = []
    for i, outer in enumerate(loops):
        depth = len(parents[i])
        if depth % 2:
            continue
        holes = [list(p.exterior.coords) for j, p in enumerate(loops)
                 if len(parents[j]) == depth+1 and i in parents[j]]
        components.append(Polygon(outer.exterior, holes))
    if not components:
        raise ValueError('Kapalı parça bulunamadı.')
    if grouped:
        components = [union_all(components)]
    result = []
    for index, g in enumerate(components):
        check_cancel(stop)
        minx, miny, _, _ = g.bounds
        normalized = affinity.translate(g, -minx, -miny)
        original = ezdxf.new('R2018'); original.units = units.MM
        for entity, line in records:
            if line.difference(g.boundary.buffer(join_tolerance*2)).length <= join_tolerance*2:
                copy = entity.copy(); copy.transform(Matrix44.translate(-minx, -miny, 0))
                copy.dxf.layer = '0'; original.modelspace().add_entity(copy)
        stream = StringIO(); original.write(stream)
        result.append(Part.create(filename.stem + (f'-{index+1:02d}' if len(components) > 1 else ''), normalized,
                                 material, thickness, quantity=quantity, source=str(filename.resolve()),
                                 source_sha256=hashlib.sha256(before).hexdigest(), source_unit=source_unit,
                                 curve_tolerance=tolerance if curved else 0, join_tolerance=join_tolerance,
                                 endpoint_error=endpoint_error,
                                 original_dxf=stream.getvalue(), notes=[
                                     f'Uç birleştirme toleransı: {join_tolerance:g} mm.',
                                     f'Birleştirilen uçlarda en büyük hareket: {endpoint_error:g} mm; çarpışma payına eklendi.',
                                     f'Eğriler en fazla {tolerance:g} mm kiriş sapmasıyla düzleştirildi.' if curved else 'Doğrusal kontur.',
                                     'Dışlanan katmanlar: ' + ', '.join(sorted(excluded))]))
    if filename.read_bytes() != before:
        raise ValueError('DXF okunurken değişti; yeniden yükleyin.')
    return result
