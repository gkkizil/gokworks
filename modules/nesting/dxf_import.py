"""Strict DXF modelspace contours, explicit units, blocks and portable source geometry."""

from collections import Counter, defaultdict
import math
import hashlib
from io import StringIO
from pathlib import Path

import ezdxf
from ezdxf import units
from ezdxf.math import Matrix44, Vec3, arc_angle_span_deg, arc_segment_count
from shapely import affinity, union_all
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize_full
from shapely.strtree import STRtree
from shapely.validation import explain_validity

from modules.nesting.models import Part, number

SUPPORTED = {'LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ELLIPSE'}
ANNOTATIONS = {'TEXT', 'MTEXT', 'DIMENSION', 'LEADER', 'MLEADER', 'POINT', 'HATCH', 'SOLID', 'ATTDEF', 'ATTRIB'}
POINT_LIMIT = 20000


def _point_limit():
    return ValueError('DXF, 20000 kontur noktası sınırını aşıyor. Eğri toleransını gözden geçirin.')


def flatten_entity(entity, tolerance, *, stop=None):
    """Use native circular/elliptic evaluators: cubic Beziers add their own error."""
    kind = entity.dxftype()
    check_cancel(stop)
    # Reject nonfinite curve parameters before entering adaptive subdivision,
    # which cannot converge on NaN control points.
    def finite(values):
        if not all(math.isfinite(value) for value in values):
            raise ValueError('DXF sonlu olmayan koordinat veya eğri parametresi içeriyor.')
    for value in entity.dxf.all_existing_dxf_attribs().values():
        if isinstance(value, (int, float)):
            finite((value,))
        elif isinstance(value, Vec3):
            finite(value)
    if kind == 'SPLINE':
        for vertices in (entity.control_points, entity.fit_points):
            if len(vertices) > POINT_LIMIT:
                raise _point_limit()
            for vertex in vertices:
                check_cancel(stop); finite(vertex)
        finite(entity.knots); finite(entity.weights)
    elif kind == 'POLYLINE':
        if len(entity.vertices) > POINT_LIMIT:
            raise _point_limit()
        for vertex in entity.vertices:
            finite(vertex.dxf.location)
            finite((vertex.dxf.bulge, vertex.dxf.start_width, vertex.dxf.end_width))
    elif kind == 'LWPOLYLINE':
        if len(entity) > POINT_LIMIT:
            raise _point_limit()
        for vertex in entity:
            finite(vertex)
    def collect(vertices):
        result = []
        for vertex in vertices:
            check_cancel(stop)
            if not all(math.isfinite(value) for value in vertex):
                raise ValueError('DXF sonlu olmayan koordinat içeriyor.')
            result.append(vertex)
            if len(result) > POINT_LIMIT:
                raise _point_limit()
        return result
    if kind == 'LINE':
        return collect((entity.dxf.start, entity.dxf.end)), False, False
    if kind in ('CIRCLE','ARC'):
        radius = entity.dxf.radius
        if not math.isfinite(radius) or radius <= 0:
            raise ValueError('DXF geçersiz yay/daire yarıçapı içeriyor.')
        span = 360 if kind == 'CIRCLE' else arc_angle_span_deg(entity.dxf.start_angle, entity.dxf.end_angle)
        if not math.isfinite(span):
            raise ValueError('DXF sonlu olmayan yay açısı içeriyor.')
        # ezdxf's circular evaluator allocates numpy.linspace(count+1) before
        # yielding a point. Reject the count before that allocation happens.
        if arc_segment_count(radius, math.radians(span), tolerance)+1 > POINT_LIMIT:
            raise _point_limit()
        return collect(entity.flattening(tolerance)), kind == 'CIRCLE', True
    if kind == 'ELLIPSE':
        closed = abs((entity.dxf.end_param-entity.dxf.start_param)-2*math.pi) < 1e-8
        return collect(entity.flattening(tolerance, segments=8)), closed, True
    if kind == 'SPLINE':
        return collect(entity.flattening(tolerance, segments=8)), entity.closed, True
    if kind in ('LWPOLYLINE','POLYLINE'):
        points = []; curved = False
        for child in entity.virtual_entities():
            vertices, _, child_curved = flatten_entity(child,tolerance,stop=stop)
            points.extend(vertices if not points else vertices[1:]); curved |= child_curved
            if len(points) > POINT_LIMIT:
                raise _point_limit()
        return points, entity.closed if kind == 'LWPOLYLINE' else entity.is_closed, curved
    raise ValueError('Desteklenmeyen DXF konturu: '+kind)


class MissingUnits(ValueError):
    pass


def _open_contour(ends, records, stop=None):
    """Describe where the contour is open or branches, and how far the gaps are."""
    loose = [point for point, count in ends.items() if count == 1]
    branches = [point for point, count in ends.items() if count > 2]
    gap = None
    if loose:
        check_cancel(stop)
        if len(loose) == 1:
            gap = math.inf
        else:
            tree = STRtree([Point(p) for p in loose])
            pairs = tree.query_nearest(tree.geometries, exclusive=True, all_matches=False)
            # Keep the diagnostic's original Euclidean distance calculation;
            # only candidate discovery changes from O(n²) to an indexed query.
            gap = max(math.dist(loose[int(i)], loose[int(j)]) for i,j in pairs.T)
        check_cancel(stop)
    bad = set(loose) | set(branches)
    layers = sorted({str(entity.dxf.layer) for entity, line in records
                     if tuple(line.coords[0]) in bad or tuple(line.coords[-1]) in bad})
    where = (branches or loose)[0]
    parts = []
    if branches:
        parts.append(f'{len(branches)} noktada ikiden fazla çizgi birleşiyor (ör. x={where[0]:.3f}, y={where[1]:.3f} mm); '
                     'üst üste binen kopya çizgiler veya kontura değen büküm/yardımcı çizgiler olabilir')
    if loose:
        text = f'{len(loose)} açık uç var'
        if gap is not None and math.isfinite(gap):
            text += f'; en büyük uç boşluğu {gap:.4f} mm'
        if not branches:
            text += f' (ör. x={where[0]:.3f}, y={where[1]:.3f} mm)'
        parts.append(text)
    message = 'Açık veya dallanan kontur: ' + '; '.join(parts) + '.'
    if layers:
        message += ' İlgili katmanlar: ' + ', '.join(layers) + '. Yardımcı bir katmansa dışlayın'
        message += '; boşluk küçükse uç birleştirme toleransını artırın.' if loose else '.'
    return OpenContour(message, gap=gap if gap is not None and math.isfinite(gap) else None,
                       branching=bool(branches), layers=layers)


def check_cancel(stop):
    if stop is not None and stop.is_set():
        raise InterruptedError('İşlem durduruldu.')


def open_dxf(path):
    """ezdxf.readfile with a Turkish, actionable message for unreadable files.

    A missing file or a permission problem keeps its OSError type; an empty,
    binary or structurally broken DXF becomes a ValueError the import list shows.
    """
    path = Path(path)
    try:
        return ezdxf.readfile(path)
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        raise
    except (OSError, ezdxf.DXFError, UnicodeError) as error:
        if path.is_file() and path.stat().st_size == 0:
            raise ValueError(f'{path.name}: dosya boş (0 bayt); geçerli bir DXF değil.') from error
        raise ValueError(f'{path.name}: geçerli bir DXF dosyası okunamadı (bozuk, ikili veya DXF olmayan içerik). '
                         'Dosyayı CAD programında açıp yeniden DXF olarak kaydedin.') from error


def layers(path):
    doc = open_dxf(path)
    return [(layer.dxf.name, not layer.is_off() and not layer.is_frozen()) for layer in doc.layers]


def _entities(entities, doc, excluded, stop, depth=0, inherited=None, _budget=None):
    budget = [0] if _budget is None else _budget
    if depth == 0:
        excluded = {str(name).casefold() for name in excluded}
    if depth > 20:
        raise ValueError('İç içe BLOCK derinliği 20 sınırını aşıyor.')
    for e in entities:
        check_cancel(stop)
        budget[0] += 1
        if budget[0] > 200000:
            raise ValueError('DXF 200.000 öğe sınırını aşıyor.')
        layer = inherited if e.dxf.layer == '0' and inherited else e.dxf.layer
        if layer.casefold() in excluded:
            continue
        if e.dxftype() == 'INSERT':
            if e.mcount > 1000:
                raise ValueError('DXF BLOCK tekrar sınırı aşıldı (1000).')
            skipped = []
            inserts = e.multi_insert() if e.mcount > 1 else [e]
            for insert in inserts:
                virtual = insert.virtual_entities(skipped_entity_callback=lambda entity, reason: skipped.append(reason))
                yield from _entities(virtual, doc, excluded, stop, depth+1, layer, budget)
                if skipped:
                    raise ValueError('BLOCK dönüşümü okunamadı: ' + '; '.join(skipped))
        elif e.dxftype() in SUPPORTED:
            yield e
        elif e.dxftype() not in ANNOTATIONS:
            raise ValueError(f'{e.dxftype()}: desteklenmeyen kesim objesi. Katmanı dışlayın veya DXF geometrisine dönüştürün.')


class OpenContour(ValueError):
    """Open or branching ends, with what a user (or an automatic retry) needs."""
    def __init__(self, message, *, gap, branching, layers):
        super().__init__(message)
        self.gap, self.branching, self.layers = gap, branching, layers


AUTO_JOIN_LIMIT = .05   # mm: largest end gap closed automatically (well below cutting tolerances)


def read_dxf(filename, *, join_tolerance=.001, drawing_layout=False, **options):
    """Read cut contours; tiny end gaps are closed automatically and reported.

    CAD exports (e.g. SOLIDWORKS flat patterns with splines) can leave end
    gaps of a few micrometres, above the strict 0.001 mm default. When every
    open end has exactly one partner within AUTO_JOIN_LIMIT and nothing
    branches, the file is read again with that join tolerance; the gap is
    already part of the collision clearance (endpoint_error).
    """
    if drawing_layout:
        from .drawing_import import read_drawing
        return read_drawing(filename, join_tolerance=join_tolerance, **options)
    try:
        return _read_dxf(filename, join_tolerance=join_tolerance, **options)
    except OpenContour as error:
        if error.branching or error.gap is None or error.gap > AUTO_JOIN_LIMIT or error.gap <= join_tolerance:
            raise
        widened = min(.1, max(join_tolerance, error.gap * 1.01 + 1e-6))
        parts = _read_dxf(filename, join_tolerance=widened, **options)
        for part in parts:
            part.notes.insert(0, f'DXF uçlarında en çok {error.gap:.4f} mm boşluk vardı; otomatik birleştirildi '
                                 f'(tolerans {widened:.4f} mm).')
        return parts


def _read_dxf(filename, *, material='S235JR', thickness=2, quantity=1, unit=None,
              tolerance=.02, join_tolerance=.001, excluded_layers=None, grouped=False, stop=None,
              _document=None):
    check_cancel(stop)
    tolerance = number(tolerance, 'Eğri toleransı', positive=True)
    join_tolerance = number(join_tolerance, 'Uç birleştirme toleransı', positive=True)
    if tolerance > 1 or join_tolerance > .1:
        raise ValueError('Eğri toleransı en fazla 1 mm; uç birleştirme toleransı en fazla 0,1 mm olabilir.')
    filename = Path(filename)
    if filename.stat().st_size > 100*1024*1024:
        raise ValueError('DXF dosyası 100 MB sınırını aşıyor; kesim katmanlarını ayrı dosyaya aktarın.')
    before = filename.read_bytes()
    doc = _document if _document is not None else open_dxf(filename)
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
    records = []; ends = Counter(); curved = False; endpoint_error = 0.; point_count = 0
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
            vertices, closed, has_curves = flatten_entity(entity,tolerance,stop=stop)
        except InterruptedError:
            raise
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
        point_count += len(line.coords)
        if point_count > 20000:
            raise ValueError('DXF, 20000 kontur noktası sınırını aşıyor. Eğri toleransını gözden geçirin.')
    if not records:
        raise ValueError('Seçilen katmanlarda kesim konturu yok.')
    if any(v != 2 for v in ends.values()):
        raise _open_contour(ends, records, stop)
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
    boundaries = [p.boundary for p in loops]
    boundary_tree = STRtree(boundaries)
    for i, p in enumerate(loops):
        check_cancel(stop)
        if not p.is_valid or p.area <= 0:
            raise ValueError('Geçersiz kontur: ' + explain_validity(p))
        if any(int(j)>i for j in boundary_tree.query(boundaries[i],predicate='intersects')):
            raise ValueError('Konturlar birbirine değiyor veya çakışıyor; üretim geometrisini ayırın.')
    loop_tree = STRtree(loops)
    parents = {}
    for i, p in enumerate(loops):
        check_cancel(stop)
        # STRtree evaluates input.within(candidate), exactly candidate.contains(input).
        parents[i] = sorted(int(j) for j in loop_tree.query(p,predicate='within') if int(j)!=i)
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
    source_sha256 = hashlib.sha256(before).hexdigest()
    short_records = {i for i,line in enumerate(lines) if line.length <= join_tolerance*2}
    for index, g in enumerate(components):
        check_cancel(stop)
        minx, miny, _, _ = g.bounds
        normalized = affinity.translate(g, -minx, -miny)
        original = ezdxf.new('R2018'); original.units = units.MM
        boundary_band = g.boundary.buffer(join_tolerance*2)
        # Broad phase only. The unchanged exact difference test decides inclusion.
        # Short lines can satisfy the historical residual-length test even when
        # outside the band, so include them explicitly rather than alter outputs.
        candidates = sorted(set(map(int,tree.query(boundary_band))) | short_records)
        for candidate in candidates:
            check_cancel(stop)
            entity, line = records[candidate]
            if line.difference(boundary_band).length <= join_tolerance*2:
                copy = entity.copy(); copy.transform(Matrix44.translate(-minx, -miny, 0))
                copy.dxf.layer = '0'; original.modelspace().add_entity(copy)
        stream = StringIO(); original.write(stream)
        result.append(Part.create(filename.stem + (f'-{index+1:02d}' if len(components) > 1 else ''), normalized,
                                 material, thickness, quantity=quantity, source=str(filename.resolve()),
                                 source_sha256=source_sha256, source_unit=source_unit,
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
