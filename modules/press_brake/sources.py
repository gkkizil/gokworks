"""Explicit online import into the user's library; no vendor CAD is bundled.

Technical profile snapshots retain their source, SHA and original arcs. The
upstream application's MIT licence does not relicense manufacturer drawings.
The import is initiated by the user and the resulting library stays local.
"""
from dataclasses import replace
from io import StringIO
from math import atan2, cos, degrees, hypot, isfinite, pi, sin, tan
import json
import urllib.error
import urllib.request

import ezdxf
from .models import Channel, Mount, Segment, Tool
from .tooling import Edge, sections
from modules.cad_converter.models import checkpoint

REVISION = '37e30d51ef842ea9ba2b2518ecb88a7736cf9872'
PROJECT = 'https://github.com/DenisPapushaJava/3d-bending-simulator'
STARTER = f'https://raw.githubusercontent.com/DenisPapushaJava/3d-bending-simulator/{REVISION}/src/project/data/starter-tools-v1.json'
LIMIT = 3*1024*1024


def manufacturer_tools():
    """Public technical facts, verified 2026-11-10; no substitute CAD shapes."""
    wila = 'https://www.wilatooling.com/products/press-brake-tooling/new-standard-tooling/new-standard-premium/'
    rolleri = 'https://www.rolleritools.com/tools-6437/press-brakes/tools/'
    note = 'Üretici ürün verisi. Gerçek kesit DXF ve tutucu verisi henüz eklenmedi.'
    rows = (
        Tool('catalog:wila:BIU-021', 'WILA', 'BIU-021', 'punch', 'New Standard Premium', 163, (0, 0), None,
             wila+'biu-021/', (), Mount('', ''), tip_angle=28, tip_radius=1, line_load=70, line_load_unit='ton/m',
             catalog_note=note+' CAD indirmesi WILA oturumu veya e-posta bağlantısı gerektirir.'),
        Tool('catalog:wila:OZU-313', 'WILA', 'OZU-313', 'die', 'New Standard Premium', 100, (0, 0), None,
             wila+'ozu-313/', (), Mount('', ''), channels=(Channel('V24', 24, 80, (0, 0), 5),),
             line_load=125, line_load_unit='ton/m', catalog_note=note+' CAD indirmesi WILA oturumu veya e-posta bağlantısı gerektirir.'),
        Tool('catalog:rolleri:04600', 'Rolleri', '04600', 'punch', 'R1 European · A', 104.91, (0, 0), None,
             rolleri+'type-r1-punches/04600', (), Mount('', ''), tip_angle=90, tip_radius=.2,
             line_load=500, line_load_unit='kN/m', catalog_note=note+' Katalog boyları: 835 ve 415 mm; fiilî adet bilinmiyor.'),
        Tool('catalog:rolleri:07500', 'Rolleri', '07500', 'die', 'R1 European · A', 60, (0, 0), None,
             rolleri+'type-r1-dies/07500-7119', (), Mount('', ''), channels=(Channel('V12', 12, 90, (0, 0)),),
             line_load=950, line_load_unit='kN/m', catalog_note=note+' Omuz R: açıklama ve özellik tablosu çelişiyor; bilinmiyor bırakıldı.'),
    )
    return tuple(replace(t, catalog_url=t.source).validate() for t in rows)


def _contains(edge, angle):
    delta = ((angle-edge.a0)*(1 if edge.sweep > 0 else -1)) % (2*pi)
    return delta <= abs(edge.sweep)+1e-7 or abs(delta-2*pi) < 1e-7


def _extents(edges):
    points = [p for e in edges for p in (e.start, e.end)]
    points += [(e.center[0]+e.radius*cos(a), e.center[1]+e.radius*sin(a))
               for e in edges if e.center for a in (0, pi/2, pi, -pi/2) if _contains(e, a)]
    return min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)


def _rotate(edges, angle):
    def point(p):
        return (p[0]*cos(angle)-p[1]*sin(angle), p[0]*sin(angle)+p[1]*cos(angle))
    return tuple(Edge(point(e.start), point(e.end), point(e.center) if e.center else None,
                      e.radius, e.a0+angle, e.sweep) for e in edges)


def _channel(edges, opening, angle, rotation):
    rotated = _rotate(edges, rotation); top = _extents(rotated)[3]
    lips = [e for e in rotated if e.center and abs(e.center[1]+e.radius-top) < 1e-4 and _contains(e, pi/2)]
    found = []
    for left in lips:
        for right in lips:
            tilt = abs(left.sweep)
            if (right.center[0] <= left.center[0] or abs(right.radius-left.radius) > 1e-4
                    or abs(right.center[1]-left.center[1]) > 1e-4
                    or abs(abs(right.sweep)-tilt) > 1e-5 or abs(pi-2*tilt-angle) > 1e-5
                    or not _contains(left, pi/2-tilt) or not _contains(right, pi/2+tilt)):
                continue
            measured = right.center[0]-left.center[0]-2*left.radius*tan(tilt/2)
            if abs(measured-opening) < 1e-4:
                found.append(Channel(f'V{opening:g}', opening, degrees(angle),
                                     ((left.center[0]+right.center[0])/2, top), left.radius, degrees(rotation)))
    if len(found) != 1:
        raise ValueError(f'V{opening:g}: kesitte tek bir doğrulanmış çalışma ağzı bulunamadı.')
    return found[0]


def _drawing(row):
    drawing = row['drawing']
    if drawing.get('millimeters') is not True or not 3 <= len(drawing['edges']) <= 20000:
        raise ValueError('Kaynak kesiti 1:1 mm ve sınırlı bir kapalı kontur olmalı.')
    doc = ezdxf.new(); doc.header['$INSUNITS'] = 4
    model = doc.modelspace()
    for edge in drawing['edges']:
        start, end, center = edge['start'], edge['end'], edge['center']
        if not all(isinstance(p, (list, tuple)) and len(p) == 2 and all(isfinite(v) and abs(v) <= 1e6 for v in p)
                   for p in (start, end)):
            raise ValueError('Kaynak kenar koordinatları geçersiz.')
        if center is not None and (not isinstance(center, (list, tuple)) or len(center) != 2
                                   or not all(isfinite(v) and abs(v) <= 1e6 for v in center)):
            raise ValueError('Kaynak yay merkezi geçersiz.')
        if center is None:
            model.add_line(start, end)
        else:
            radius = hypot(start[0]-center[0], start[1]-center[1]); sweep = edge['sweepRadians']
            if not isfinite(radius) or not isfinite(sweep) or radius <= 0 or not 0 < abs(sweep) <= 2*pi+1e-7:
                raise ValueError('Kaynak yayı geçersiz.')
            if abs(abs(sweep)-2*pi) < 1e-7:
                model.add_circle(center, radius)
            else:
                a, b = (start, end) if sweep > 0 else (end, start)
                model.add_arc(center, radius, degrees(atan2(a[1]-center[1], a[0]-center[0])),
                              degrees(atan2(b[1]-center[1], b[0]-center[0])))
    stream = StringIO(); doc.write(stream)
    return stream.getvalue()


def parse_starter(text, stop=None):
    if len(text.encode('utf-8')) > LIMIT:
        raise ValueError('Kaynak takım kataloğu boyut sınırını aştı.')
    data = json.loads(text)
    if data.get('format') != 'bending-tool-catalog' or data.get('version') != 5 or not 1 <= len(data.get('tools', ())) <= 512:
        raise ValueError('Kaynak takım kataloğunun biçimi desteklenmiyor.')
    result = []
    for row in data['tools']:
        checkpoint(stop)
        try:
            if row.get('parametersConfirmed') is not True or row.get('teaching') is not False:
                raise ValueError('Çalışma ölçüleri doğrulanmamış profil.')
            dxf = _drawing(row); contours = sections(dxf)
            if len(contours) != 1:
                raise ValueError('Kaynak kayıtta birden fazla takım gövdesi var.')
            region, edges, holes = contours[0]
            angle = float(row['angleRadians']); kind = row['kind']
            tip = None; channels = []
            if kind == 'punch':
                bottom = _extents(edges)[1]
                noses = [e for e in edges if e.center and abs(e.radius-row['noseRadiusMm']) < 1e-4
                         and abs(pi-abs(e.sweep)-angle) < 1e-5 and _contains(e, -pi/2)
                         and abs(e.center[1]-e.radius-bottom) < 1e-4]
                if len(noses) != 1:
                    raise ValueError('Kesitte uç açısı ve uç R ile eşleşen tek çalışma ucu yok.')
                tip = (noses[0].center[0], bottom)
            elif kind == 'die':
                settings = row.get('grooveSettings') or [dict(rotationRadians=0., angleRadians=angle) for _ in row['openingsMm']]
                if len(settings) != len(row['openingsMm']):
                    raise ValueError('V kanalı ve çalışma yönü sayıları eşleşmiyor.')
                channels = [_channel(edges, opening, setting['angleRadians'], setting['rotationRadians'])
                            for opening, setting in zip(row['openingsMm'], settings)]
            else:
                raise ValueError('Üst/alt takım tipi desteklenmiyor.')
            length = float(row['lengthMm'])
            source = f"{PROJECT}/blob/{REVISION}/src/project/data/starter-tools-v1.json · {row['drawing']['sourceFile']} · SHA256 {row['drawing']['sha256']}"
            tool = Tool('source:'+row['id'], 'Üretici belirtilmemiş' if row['manufacturer'] == 'Не указан' else row['manufacturer'],
                        row['code'], kind, 'Kaynak DXF profili', float(row['heightMm']), (0, 0), region, source,
                        (Segment(-length/2, length),), Mount('', ''), tip_angle=degrees(angle) if kind == 'punch' else None,
                        tip_radius=row['noseRadiusMm'] if kind == 'punch' else None, tip=tip, channels=tuple(channels),
                        section_dxf=dxf, catalog_url=PROJECT+'/blob/'+REVISION+'/docs/starter-tool-library.md',
                        catalog_note='Gerçek DXF kesiti. Montaj datumu ve tutucu bilinmiyor. Kaynak segment adetleri örnek settir; fiilî stok değildir.',
                        catalog_segments=tuple((float(s['lengthMm']), s['quantity']) for s in row['segments']))
            result.append(tool.validate())
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{row.get('code', 'Kaynak takım')}: {error}") from error
    if len({t.id for t in result}) != len(result):
        raise ValueError('Kaynak takım kimlikleri yineleniyor.')
    return tuple(result)


def download_starter(stop=None, opener=None):
    checkpoint(stop)
    request = urllib.request.Request(STARTER, headers={'User-Agent': 'GOKWORKS-tool-catalog/1', 'Accept': 'application/json'})
    try:
        with (opener or urllib.request.urlopen)(request, timeout=20) as response:
            raw = response.read(LIMIT+1)
    except (OSError, urllib.error.URLError) as error:
        raise ValueError('Takım kaynağı indirilemedi; mevcut kütüphane korunuyor: '+str(error)) from error
    checkpoint(stop)
    if len(raw) > LIMIT:
        raise ValueError('Kaynak takım kataloğu boyut sınırını aştı.')
    return parse_starter(raw.decode('utf-8'), stop)


def merged_catalog(existing, incoming):
    """Preserve already edited/owned profiles and avoid duplicate imports."""
    ids = {t.id for t in existing}
    return tuple(existing)+tuple(t for t in incoming if t.id not in ids)
