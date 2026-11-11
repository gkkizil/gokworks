"""Extract framed drawing cells without treating drawing borders as cut contours.

No color, layer name, title or fixed page layout identifies a cell. A rectangular
border must enclose both a quantity annotation and independent cut geometry.
Ambiguous or unassigned geometry fails the entire source; partial imports cannot
quietly omit a part. The strict DXF reader still validates every extracted cell.
"""

from dataclasses import replace
from collections import defaultdict
from itertools import chain
import math
from pathlib import Path
import re

import ezdxf
from ezdxf import units
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize_full
from shapely.strtree import STRtree

from .dxf_import import (ANNOTATIONS, SUPPORTED, MissingUnits, check_cancel,
                         flatten_entity, open_dxf, read_dxf)
from .models import integer, number


QUANTITY = re.compile(r'(?<![\w.,/])([+-]?\d+(?:[.,]\d+)?)\s*(?:adet|ad\.?|pcs?|qty)(?!\w)', re.I)
PREFIX_QUANTITY = re.compile(r'(?<!\w)(?:qty|adet)\s*[:=]\s*([+-]?\d+(?:[.,]\d+)?)(?![\w.,])', re.I)


def _view_heading(insert):
    """Recognize a CAD view caption, never a general block containing text.

    A standard VIEW/DETAIL/SCALE heading has a LETTER/SCALE attribute and
    at most one straight underline. Closed contours and arbitrary attribute
    tags cannot be discarded by this rule. Names, colors and layers vary.
    """
    block = insert.block()
    if block is None: return False
    entities = list(block)
    if any(e.dxftype() not in {'LINE','TEXT','MTEXT','ATTDEF','ATTRIB'} for e in entities): return False
    if sum(e.dxftype()=='LINE' for e in entities)>1: return False
    tags = {e.dxf.tag.upper() for e in [*entities,*insert.attribs] if e.dxftype() in ('ATTDEF','ATTRIB')}
    if not tags or not tags <= {'LETTER','SCALE'}: return False
    return any(re.fullmatch(r'\s*(?:VIEW|DETAIL|SCALE)\s*',e.plain_text(),re.I)
               for e in entities if e.dxftype() in ('TEXT','MTEXT'))


def _entities(entities, excluded, stop, depth=0, inherited=None, _budget=None):
    budget = [0] if _budget is None else _budget
    if depth == 0:
        excluded = {str(name).casefold() for name in excluded}
    if depth > 20:
        raise ValueError('İç içe BLOCK derinliği 20 sınırını aşıyor.')
    for entity in entities:
        check_cancel(stop)
        budget[0] += 1
        if budget[0] > 200000:
            raise ValueError('DXF 200.000 öğe sınırını aşıyor.')
        layer = inherited if entity.dxf.layer == '0' and inherited else entity.dxf.layer
        if layer.casefold() in excluded:
            continue
        if entity.dxftype() == 'INSERT':
            if entity.mcount > 1000:
                raise ValueError('DXF BLOCK tekrar sınırı aşıldı (1000).')
            for insert in entity.multi_insert() if entity.mcount > 1 else [entity]:
                skipped = []
                virtual = insert.virtual_entities(skipped_entity_callback=lambda e, reason: skipped.append(reason))
                if _view_heading(insert):
                    virtual = [e for e in virtual if e.dxftype()!='LINE']
                yield from _entities(chain(virtual, insert.attribs), excluded, stop, depth+1, layer, budget)
                if skipped:
                    raise ValueError('BLOCK dönüşümü okunamadı: ' + '; '.join(skipped))
        elif entity.dxftype() in SUPPORTED | ANNOTATIONS:
            copy = entity.copy()
            copy.dxf.layer = layer
            yield copy
        else:
            raise ValueError(f'{entity.dxftype()}: desteklenmeyen kesim objesi. Katmanı dışlayın veya DXF geometrisine dönüştürün.')


def _quantity(entity):
    if entity.dxftype() not in ('TEXT', 'MTEXT', 'ATTRIB'):
        return None
    text = entity.plain_text()
    matches = list({m.span(1):m for pattern in (QUANTITY,PREFIX_QUANTITY) for m in pattern.finditer(text)}.values())
    if not matches:
        return None
    # A cell must contain exactly one declaration, even if duplicate values agree.
    if len(matches) != 1:
        raise ValueError(f'Bir yazıda birden fazla adet var: {text!r}. Her parça için tek adet yazın.')
    literal = matches[0].group(1)
    if not re.fullmatch(r'\+?\d+',literal):
        raise ValueError(f'Çizimdeki adet: tam sayı yazın; ondalık/binlik ayırıcı kullanmayın ({literal!r}).')
    quantity = integer(literal, 'Çizimdeki adet')
    if entity.dxftype() == 'MTEXT':
        position = entity.dxf.insert
    else:
        _, first, second = entity.get_placement()
        position = (first + second) / 2 if second is not None else first
    return quantity, Point(position.x, position.y), text


def _frame_lines(lines, epsilon, stop):
    """Join only endpoint copies, within the configured physical tolerance.

    These lines are for discovering annotation frames, not manufacturing
    contours. Never node crossings or rewrite the source cut geometry.
    """
    buckets = defaultdict(list)
    def endpoint(point):
        key = tuple(math.floor(v/epsilon) for v in point)
        nearby = [p for i in (-1,0,1) for j in (-1,0,1)
                  for p in buckets[(key[0]+i,key[1]+j)]
                  # Unit conversion has finite precision (including inch/mm).
                  if math.dist(point,p)<=epsilon or math.isclose(math.dist(point,p),epsilon,rel_tol=1e-10,abs_tol=0.)]
        if nearby: return min(nearby,key=lambda p:(math.dist(point,p),p))
        buckets[key].append(point)
        return point
    result = []
    for line in lines:
        check_cancel(stop)
        coords = list(line.coords)
        coords[0] = endpoint(coords[0]); coords[-1] = endpoint(coords[-1])
        joined = LineString(coords)
        if joined.length>epsilon and joined.is_simple: result.append(joined)
    return result


def _is_frame(polygon, epsilon):
    if polygon.is_empty or not polygon.is_valid or polygon.area<=0: return False
    rectangle = polygon.minimum_rotated_rectangle
    if polygon.boundary.hausdorff_distance(rectangle.boundary)<=epsilon: return True
    # CAD drawing borders may be slightly sheared four-sided cells. This is
    # an annotation-only rule: retain the actual border, do not square parts.
    corners = list(polygon.simplify(epsilon,preserve_topology=True).exterior.coords)[:-1]
    if len(corners)!=4 or not polygon.equals(polygon.convex_hull): return False
    for i,point in enumerate(corners):
        a = tuple(x-y for x,y in zip(corners[i-1],point))
        b = tuple(x-y for x,y in zip(corners[(i+1)%4],point))
        product = math.hypot(*a)*math.hypot(*b)
        if product==0 or abs(sum(x*y for x,y in zip(a,b)))/product>math.sin(math.radians(1)):
            return False
    return True


def read_drawing(filename, *, material='S235JR', thickness=2, quantity=1, unit=None,
                 tolerance=.02, join_tolerance=.001, excluded_layers=None, grouped=False, stop=None):
    check_cancel(stop)
    if grouped:
        raise ValueError('Çerçeveli toplu çizimde tek grup seçimini kapatın; her çerçeve ayrı parçadır.')
    tolerance = number(tolerance, 'Eğri toleransı', positive=True)
    join_tolerance = number(join_tolerance, 'Uç birleştirme toleransı', positive=True)
    if tolerance > 1 or join_tolerance > .1:
        raise ValueError('Eğri toleransı en fazla 1 mm; uç birleştirme toleransı en fazla 0,1 mm olabilir.')
    filename = Path(filename)
    if filename.stat().st_size > 100*1024*1024:
        raise ValueError('DXF dosyası 100 MB sınırını aşıyor.')
    before = filename.read_bytes()
    doc = open_dxf(filename)
    code = doc.header.get('$INSUNITS', 0)
    if not code:
        if unit not in ('mm', 'cm', 'inch'):
            raise MissingUnits(filename.name + ': DXF birimi tanımlı değil. mm, cm veya inch seçin.')
        code = {'mm': units.MM, 'cm': units.CM, 'inch': units.IN}[unit]
    try:
        scale = units.conversion_factor(code, units.MM)
    except (TypeError, ValueError, KeyError):
        raise ValueError('DXF $INSUNITS birimi desteklenmiyor.') from None
    epsilon = join_tolerance / scale
    excluded = set(excluded_layers or [])
    excluded.update(layer.dxf.name for layer in doc.layers if layer.is_off() or layer.is_frozen())
    records, labels, straight = [], [], []
    point_count = 0
    for entity in _entities(doc.modelspace(), excluded, stop):
        if entity.dxftype() not in SUPPORTED:
            label = _quantity(entity)
            if label is not None:
                labels.append(label)
            continue
        vertices, closed, curved = flatten_entity(entity, tolerance / scale, stop=stop)
        if not vertices:
            continue
        if any(abs(v.z) > epsilon for v in vertices):
            raise ValueError('Kesim konturları XY düzleminde (Z=0) olmalı; 3B konturlar otomatik izdüşürülmez.')
        points = [(v.x, v.y) for v in vertices]
        if closed:
            points[-1] = points[0]
        line = LineString(points)
        if line.length <= epsilon or not line.is_simple:
            raise ValueError('Sıfır uzunluklu veya kendi kendini kesen kontur bulundu.')
        records.append((entity, line))
        if not curved:
            straight.append(line)
        point_count += len(points)
        if point_count > 20000:
            raise ValueError('DXF, 20000 kontur noktası sınırını aşıyor. Eğri toleransını gözden geçirin.')
    if not labels:
        raise ValueError('Toplu çizimde adet yazısı bulunamadı. TEXT/MTEXT/ATTRIB olarak ör. “7 adet” yazın; '
                         'normal parçalar için çerçeveli toplu çizim seçimini kapatın.')
    # Polygonization does not node crossing helper lines into invented rectangles.
    faces, _, _, _ = polygonize_full(_frame_lines(straight,epsilon,stop))
    rectangles = {}
    for face in faces.geoms:
        check_cancel(stop)
        for ring in [face.exterior, *face.interiors]:
            polygon = Polygon(ring)
            if _is_frame(polygon,epsilon):
                rectangles[polygon.normalize().wkb] = polygon
    frames = list(rectangles.values())
    frame_tree = STRtree(frames)
    lines = [line for _, line in records]
    tree = STRtree(lines)
    selected = {}
    for count, position, text in labels:
        check_cancel(stop)
        candidates = []
        for raw_index in frame_tree.query(position,predicate='within'):
            i = int(raw_index)
            frame = frames[i]
            if any(frame.contains(lines[int(j)]) for j in tree.query(frame)):
                candidates.append(i)
        if not candidates:
            raise ValueError(f'{text!r}: adet yazısı ve parça içeren kapalı dikdörtgen çerçeve bulunamadı. '
                             'Çerçeveyi kapatın veya yardımcı katmanları dışlayın.')
        chosen = min(candidates, key=lambda i: frames[i].area)
        if chosen in selected:
            raise ValueError(f'Bir çerçevede birden fazla adet yazısı var ({selected[chosen][1]!r}, {text!r}). '
                             'Her çerçevede tek parça ve tek adet yazısı bırakın.')
        selected[chosen] = count, text
    chosen = sorted(selected, key=lambda i: (-frames[i].centroid.y, frames[i].centroid.x))
    for n, i in enumerate(chosen):
        check_cancel(stop)
        if any(frames[i].intersection(frames[j]).area > epsilon**2 for j in chosen[n+1:]):
            raise ValueError('Parça çerçeveleri çakışıyor veya iç içe; adet eşleştirmesi belirsiz.')
    assignments = {i: [] for i in chosen}
    used = set()
    for i in chosen:
        frame = frames[i]
        band = frame.boundary.buffer(epsilon)
        for raw_index in tree.query(frame):
            index = int(raw_index)
            line = lines[index]
            if line.difference(band).length <= epsilon:
                used.add(index)  # Border only; never pass it to the cut reader.
            elif frame.contains(line):
                assignments[i].append(index)
                used.add(index)
    # An enclosing page border is also drawing metadata, regardless of its color.
    for frame in frames:
        if all(frame.contains(frames[i]) for i in chosen):
            band = frame.boundary.buffer(epsilon)
            for raw_index in tree.query(band):
                index = int(raw_index)
                if lines[index].difference(band).length <= epsilon:
                    used.add(index)
    unassigned = set(range(len(records))) - used
    if unassigned:
        layers = ', '.join(sorted({records[i][0].dxf.layer for i in unassigned}))
        raise ValueError(f'{len(unassigned)} geometri nesnesi adetli bir çerçeveye atanamadı. '
                         f'Eksik adet/çerçeveyi düzeltin veya yardımcı katmanı dışlayın. Katmanlar: {layers}.')
    result = []
    for n, i in enumerate(chosen, 1):
        check_cancel(stop)
        extracted = ezdxf.new('R2018')
        extracted.units = code
        for index in sorted(assignments[i]):
            entity = records[index][0].copy()
            entity.dxf.layer = '0'
            extracted.modelspace().add_entity(entity)
        try:
            parts = read_dxf(filename, material=material, thickness=thickness, quantity=selected[i][0],
                             tolerance=tolerance, join_tolerance=join_tolerance, stop=stop, _document=extracted)
        except ValueError as error:
            raise ValueError(f'Çerçeve {n} ({selected[i][1]}): {error}') from error
        if len(parts) != 1:
            raise ValueError(f'Çerçeve {n}: {len(parts)} bağımsız parça var. Her parçayı kendi çerçevesi ve adediyle ayırın.')
        result.append(replace(parts[0], code=f'{filename.stem}-{n:02d}', notes=[*parts[0].notes,
            'Toplu çizimde dışlanan katmanlar: ' + ', '.join(sorted(excluded)),
            f'Toplu çizim çerçevesi {n}; adet yazısı: {selected[i][1]}. Çerçeve ve açıklama yazıları kesimden çıkarıldı.']))
    if sum(part.quantity for part in result) > 10000:
        raise ValueError('Bir projede en fazla 10000 parça örneği desteklenir; çizimdeki adetleri azaltın.')
    check_cancel(stop)
    if filename.read_bytes() != before:
        raise ValueError('DXF okunurken değişti; yeniden yükleyin.')
    return result
