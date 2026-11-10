"""Strict 1:1 mm DXF sections. Analytical line/arc edges survive extrusion."""
from dataclasses import dataclass
from io import StringIO
from math import atan2, cos, sin, pi
from pathlib import Path
import ezdxf
from ezdxf.math import bulge_to_arc
from shapely.geometry import Polygon
from .models import Region


@dataclass(frozen=True)
class Edge:
    start: tuple
    end: tuple
    center: tuple | None = None
    radius: float = 0
    a0: float = 0
    sweep: float = 0

    def reversed(self):
        return Edge(self.end, self.start, self.center, self.radius, self.a0+self.sweep, -self.sweep)

    def samples(self):
        if not self.center:
            return [self.start, self.end]
        # Polygon for containment only; OCCT consumes the exact arc below.
        count = max(4, int(abs(self.sweep)*max(20, (self.radius/.002)**.5)))
        if count > 100000:
            raise ValueError('Takım kesiti yay örnekleme sınırını aşıyor.')
        return [(self.center[0]+self.radius*cos(self.a0+self.sweep*i/count),
                 self.center[1]+self.radius*sin(self.a0+self.sweep*i/count)) for i in range(count+1)]


def _entities(doc):
    def visit(entities, depth=0):
        if depth > 16:
            raise ValueError('DXF iç içe blok sınırını aşıyor.')
        for e in entities:
            layer = doc.layers.get(e.dxf.layer)
            if layer.is_off() or layer.is_frozen() or not layer.dxf.get('plot', 1):
                continue
            if e.dxf.layer.casefold().startswith(('defpoints', 'aux', 'helper', 'construction', 'yardım', 'yardim')):
                continue
            kind = e.dxftype()
            if kind == 'INSERT':
                yield from visit(e.virtual_entities(), depth+1)
            elif kind in ('ELLIPSE', 'SPLINE', '3DFACE'):
                raise ValueError(kind+': takım kesitinde yalnız düzlemsel çizgi ve dairesel yay destekleniyor.')
            elif kind in ('LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'POLYLINE'):
                yield e
            # Never explode DIMENSION/HATCH into apparently cuttable lines.
    yield from visit(doc.modelspace())


def _edges(doc):
    result = []
    for e in _entities(doc):
        kind = e.dxftype()
        if kind in ('LWPOLYLINE', 'POLYLINE'):
            if tuple(e.dxf.extrusion) != (0, 0, 1) or (kind == 'LWPOLYLINE' and abs(e.dxf.elevation) > 1e-6):
                raise ValueError('Takım polilinesi XY düzleminde (Z=0, normal +Z) olmalı.')
            if kind == 'POLYLINE' and any(abs(v.dxf.location.z) > 1e-6 for v in e.vertices):
                raise ValueError('3B poliline takım kesiti olarak desteklenmiyor.')
            vertices = list(e.get_points('xyb')) if kind == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y, v.dxf.bulge) for v in e.vertices]
            if len(vertices) < 2:
                raise ValueError('Boş poliline takım konturu olamaz.')
            for i in range(len(vertices) if e.is_closed else len(vertices)-1):
                a, b = vertices[i], vertices[(i+1) % len(vertices)]
                if abs(a[2]) < 1e-12:
                    result.append(Edge(tuple(a[:2]), tuple(b[:2])))
                else:
                    c, a0, a1, r = bulge_to_arc(a[:2], b[:2], a[2])
                    ccw = (a1-a0) % (2*pi)
                    start = atan2(a[1]-c.y, a[0]-c.x)
                    result.append(Edge(tuple(a[:2]), tuple(b[:2]), (c.x, c.y), r, start, ccw if a[2] > 0 else -ccw))
        elif kind == 'LINE':
            if abs(e.dxf.start.z) > 1e-6 or abs(e.dxf.end.z) > 1e-6:
                raise ValueError('Takım kesiti XY düzleminde olmalı (Z=0).')
            result.append(Edge(tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]))
        else:
            if abs(e.dxf.center.z) > 1e-6 or tuple(e.dxf.extrusion) != (0, 0, 1):
                raise ValueError('Takım yayı XY düzleminde olmalı (normal +Z).')
            a0 = e.dxf.start_angle*pi/180 if kind == 'ARC' else 0
            sweep = ((e.dxf.end_angle-e.dxf.start_angle) % 360)*pi/180 if kind == 'ARC' else 2*pi
            c, r = tuple(e.dxf.center)[:2], e.dxf.radius
            result.append(Edge((c[0]+r*cos(a0), c[1]+r*sin(a0)),
                               (c[0]+r*cos(a0+sweep), c[1]+r*sin(a0+sweep)), c, r, a0, sweep))
    if not result or len(result) > 20000:
        raise ValueError('Takım kesiti yok veya 20.000 kenar sınırı aşıldı.')
    return result


def sections(text, *, accept_unitless=False):
    doc = ezdxf.read(StringIO(text))
    unit = int(doc.header.get('$INSUNITS', 0))
    if unit != 4 and not (unit == 0 and accept_unitless):
        raise ValueError('DXF birimi mm olmalı. Birimsiz çizim için 1 birim = 1 mm seçeneğini doğrulayın.')
    pending, loops = _edges(doc), []
    def near(a, b):
        return sum((x-y)**2 for x, y in zip(a, b)) < 1e-12
    while pending:
        chain = [pending.pop(0)]
        while not near(chain[0].start, chain[-1].end):
            matches = [(i, e if near(e.start, chain[-1].end) else e.reversed()) for i, e in enumerate(pending)
                       if near(e.start, chain[-1].end) or near(e.end, chain[-1].end)]
            if len(matches) != 1:
                raise ValueError('Açık, dallanan veya belirsiz takım konturu. Yardımcı geometrileri ayrı katmanda gizleyin.')
            i, edge = matches[0]; chain.append(edge); pending.pop(i)
        points = [p for edge in chain for p in edge.samples()[:-1]]
        polygon = Polygon(points)
        Region.from_polygon(polygon)
        loops.append((tuple(chain), polygon))
    # Even nesting = solid island; direct odd children = holes. Never choose
    # the biggest contour silently when there are multiple tool sections.
    loops.sort(key=lambda item: -item[1].area)
    parents = []
    for i, (_, p) in enumerate(loops):
        containers = [j for j in range(i) if loops[j][1].contains(p)]
        if any(p.intersects(other) and not p.within(other) for _, other in loops[:i]):
            raise ValueError('Takım konturları kesişiyor veya birbirine değiyor.')
        parents.append(containers[-1] if containers else None)
    def depth(i):
        return 0 if parents[i] is None else 1+depth(parents[i])
    result = []
    for i, (edges, p) in enumerate(loops):
        if depth(i) % 2:
            continue
        children = [j for j in range(len(loops)) if parents[j] == i]
        region = Region.from_polygon(Polygon(p.exterior.coords, [loops[j][1].exterior.coords for j in children]))
        result.append((region, edges, tuple(loops[j][0] for j in children)))
    return tuple(result)


def read_sections(path, *, accept_unitless=False):
    doc = ezdxf.readfile(str(path))
    output = StringIO(); doc.write(output)
    text = output.getvalue()
    return text, sections(text, accept_unitless=accept_unitless)


def save_catalog(tools, path):
    """Atomic user library; native DXF is retained with source provenance."""
    from dataclasses import asdict
    import json
    from modules.tolerance_stack.storage import atomic_write
    data = json.dumps({'schema': 1, 'tools': [asdict(t) for t in tools if not t.demo]}, ensure_ascii=False, indent=2)
    atomic_write(Path(path), lambda p: p.write_text(data, encoding='utf-8'), overwrite=True)


def load_catalog(path):
    import json
    from .models import Channel, Mount, Segment, Tool
    p = Path(path)
    if not p.exists():
        return ()
    data = json.loads(p.read_text(encoding='utf-8'))
    if data.get('schema') != 1:
        raise ValueError('Desteklenmeyen takım kütüphanesi sürümü.')
    tools = []
    for row in data['tools']:
        row['section'] = Region(tuple(map(tuple, row['section']['outer'])), tuple(tuple(map(tuple, h)) for h in row['section']['holes'])) if row['section'] else None
        row['holder_section'] = Region(tuple(map(tuple, row['holder_section']['outer'])), tuple(tuple(map(tuple, h)) for h in row['holder_section']['holes'])) if row['holder_section'] else None
        row['segments'] = tuple(Segment(**s) for s in row['segments'])
        row['holder_segments'] = tuple(Segment(**s) for s in row.get('holder_segments', ()))
        row['mount_reference'] = tuple(row['mount_reference'])
        row['tip'] = tuple(row['tip']) if row.get('tip') is not None else None
        row['channels'] = tuple(Channel(**dict(s, center=tuple(s['center']))) for s in row['channels'])
        row['catalog_segments'] = tuple(tuple(s) for s in row.get('catalog_segments', ()))
        row['mount'] = Mount(**row['mount'])
        tools.append(Tool(**row).validate())
    return tuple(tools)
