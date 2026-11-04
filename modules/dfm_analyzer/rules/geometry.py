"""DFM-GEO: geometry hygiene. Facts about the drawing, independent of the machine."""

from .base import rule, Mark, NotEvaluated, ERROR, WARNING, INFO


def _fmt(value):
    return f'{value:.3f}'.rstrip('0').rstrip('.').replace('.', ',')


@rule('DFM-GEO-001', 'Açık kontur', 'geometry', severity=ERROR, needs_limit=False,
      description='Bir kesim yolunun uçları buluşmuyor.', uses='Açık LINE/ARC/POLYLINE uçları',
      assumptions='Uçlar 0,001 mm içinde ise birleşik kabul edilir.')
def open_contour(ctx, r, limit):
    found = []
    for point, gap, handle in ctx.topology.open_ends:
        text = f'en yakın açık uca {_fmt(gap)} mm' if gap is not None else 'eşleşecek başka açık uç yok'
        found.append(ctx.finding(r, f'Kesim konturu açık: uç x={_fmt(point[0])}, y={_fmt(point[1])} mm ({text}).',
                                 'Konturu CAD programında kapatın veya bu çizgi kesim dışıysa katmanını dışlayın.',
                                 measured=gap, marks=[Mark('point', [point], 'açık uç')], entities=[handle]))
    for handles, points in ctx.topology.open_paths:
        if any(f.entities and f.entities[0] in handles for f in found):
            continue
        found.append(ctx.finding(r, 'Kapanmayan kontur zinciri.', 'Konturu kapatın.',
                                 marks=[Mark('path', points)], entities=handles))
    return found


@rule('DFM-GEO-002', 'Küçük uç boşluğu köprülendi', 'geometry', severity=WARNING, needs_limit=False,
      description='Profilin kapanma toleransı içindeki uç boşlukları birleştirildi.', uses='Açık uç çiftleri',
      assumptions='Yalnız karşılıklı en yakın iki uç birleştirilir.')
def bridged_gaps(ctx, r, limit):
    tolerance = ctx.profile.closure_tolerance
    return [ctx.finding(r, f'{_fmt(gap)} mm uç boşluğu analiz için birleştirildi.',
                        'CAM yazılımı aynı toleransla birleştirmiyorsa uçları CAD programında kapatın.',
                        measured=gap, limit=tolerance, marks=[Mark('line', [a, b], f'{_fmt(gap)} mm')], entities=handles)
            for a, b, gap, handles in ctx.topology.bridged]


@rule('DFM-GEO-003', 'Dallanan kontur', 'geometry', severity=ERROR, needs_limit=False,
      description='Bir noktada ikiden fazla kesim çizgisi birleşiyor.', uses='Kontur uç noktaları',
      assumptions='Kopya çizgi veya kontura değen yardımcı çizgi olabilir.')
def branches(ctx, r, limit):
    return [ctx.finding(r, f'{len(handles)} çizgi aynı noktada birleşiyor (x={_fmt(p[0])}, y={_fmt(p[1])} mm).',
                        'Fazla çizgiyi silin veya yardımcı çizgiyi ayrı bir katmana alıp dışlayın.',
                        marks=[Mark('point', [p], 'dallanma')], entities=handles)
            for p, handles in ctx.topology.branches]


@rule('DFM-GEO-004', 'Sıfır uzunluklu nesne', 'geometry', severity=WARNING, needs_limit=False,
      description='0,001 mm’den kısa nesne; analizde yok sayıldı.', uses='Tüm kesim nesneleri')
def zero_length(ctx, r, limit):
    return [ctx.finding(r, 'Sıfır uzunluklu nesne yok sayıldı.', 'Nesneyi silin.',
                        marks=[Mark('point', [p])], entities=[h]) for h, p in ctx.topology.zero_length]


@rule('DFM-GEO-005', 'Yinelenen geometri', 'geometry', severity=WARNING, needs_limit=False,
      description='Aynı kontur iki kez çizilmiş; kopya yok sayıldı.', uses='Tüm kesim nesneleri',
      assumptions='Noktalar 0,001 mm içinde aynıysa kopya kabul edilir.')
def duplicates(ctx, r, limit):
    return [ctx.finding(r, f'Kopya kontur (aynısı: {of}). Makine aynı yolu iki kez kesebilir.',
                        'Kopyayı silin.', marks=[Mark('path', points)], entities=[h, of])
            for h, of, points in ctx.topology.duplicates]


@rule('DFM-GEO-006', 'Üst üste binen çizgiler', 'geometry', severity=ERROR, needs_limit=False,
      description='İki kontur bir bölümde üst üste biniyor (ortak kesim hattı).', uses='Kontur kesişimleri')
def overlaps(ctx, r, limit):
    return [ctx.finding(r, f'{_fmt(length)} mm uzunlukta üst üste binen kesim çizgisi.',
                        'Fazla çizgiyi silin. Ortak hat kesimi isteniyorsa CAM aşamasında bilinçli tanımlayın.',
                        measured=length, marks=[Mark('path', p) for p in pieces], entities=handles)
            for handles, pieces, length in ctx.topology.overlaps]


@rule('DFM-GEO-007', 'Kendi kendini kesen kontur', 'geometry', severity=ERROR, needs_limit=False,
      description='Bir kontur kendisini kesiyor veya kendine değiyor.', uses='Kapalı ve açık konturlar')
def self_intersections(ctx, r, limit):
    return [ctx.finding(r, 'Kontur kendi kendini kesiyor; geçerli bir kesim yolu değil.',
                        'Konturu CAD programında düzeltin.',
                        marks=[Mark('point', [p], 'kesişim') for p in points[:10]], entities=[h])
            for h, points in ctx.topology.self_intersections]


@rule('DFM-GEO-008', 'Birbirini kesen veya değen konturlar', 'geometry', severity=ERROR, needs_limit=False,
      description='İki ayrı kontur kesişiyor veya bir noktada değiyor.', uses='Kontur çiftleri')
def crossings(ctx, r, limit):
    return [ctx.finding(r, f'İki kontur {len(points)} noktada kesişiyor veya değiyor.',
                        'Konturları ayırın; delik veya çentik dış kenara değiyorsa birleştirip tek kontur yapın.',
                        marks=[Mark('point', [p], 'kesişim') for p in points[:10]], entities=handles)
            for handles, points in ctx.topology.crossings]


@rule('DFM-GEO-009', 'Serbest kalan iç parça', 'geometry', severity=ERROR, needs_limit=False,
      description='Bir boşluğun içindeki malzeme kesimden sonra düşer.', uses='İç içe kontur derinliği',
      assumptions='Ayrı parça olarak bilinçli yerleştirildiyse bu bulgu kabul edilebilir.')
def islands(ctx, r, limit):
    return [ctx.finding(r, f'{p.name} bir boşluğun içinde; kesimden sonra serbest kalır.',
                        'Köprü (mikro bağlantı) ekleyin veya ayrı parça olarak bilinçli ise not alın.',
                        marks=[Mark('area', list(p.outline.polygon.exterior.coords))], entities=p.outline.handles,
                        part=p.name)
            for p in ctx.topology.parts if p.island]


@rule('DFM-GEO-010', 'Çok kısa segment', 'geometry', severity=INFO, needs_limit=False,
      description='Profilin kısa segment sınırından kısa düz parçalar (yay düzleştirmesi hariç).',
      uses='Düz segmentler')
def short_segments(ctx, r, limit):
    items = ctx.topology.short_segments
    if not items:
        return []
    limit_mm = ctx.profile.short_segment
    shortest = min(items, key=lambda s: s[3])
    return [ctx.finding(r, f'{len(items)} adet {_fmt(limit_mm)} mm’den kısa segment (en kısa {_fmt(shortest[3])} mm).',
                        'Gereksiz kısa parçaları birleştirin; makine yavaşlayabilir veya yanma izi bırakabilir.',
                        measured=shortest[3], limit=limit_mm,
                        marks=[Mark('line', [a, b]) for _, a, b, _ in items[:50]], entities=sorted({s[0] for s in items}))]


@rule('DFM-GEO-011', 'Kontrol edilemeyen nesneler', 'geometry', severity=INFO, needs_limit=False,
      description='Desteklenmeyen veya okunamayan DXF nesneleri.', uses='Tüm DXF nesneleri')
def unsupported(ctx, r, limit):
    if ctx.drawing.unsupported:
        details = '; '.join(f'{n} × {k} ({layer or "—"}): {reason}' for k, layer, reason, n in ctx.drawing.unsupported)
        raise NotEvaluated('Bu nesneler kontrol edilmedi: ' + details)
    return []


@rule('DFM-GEO-012', 'Birim makullüğü', 'geometry', severity=WARNING, needs_limit=False,
      description='Parça ölçüsü seçilen birimde olağandışı.', uses='Parça sınır kutusu',
      assumptions='0,5 mm’den küçük veya 20 m’den büyük parça olağandışı kabul edilir.')
def units(ctx, r, limit):
    found = []
    for p in ctx.topology.parts:
        minx, miny, maxx, maxy = p.outline.polygon.bounds
        size = max(maxx - minx, maxy - miny)
        if size < .5 or size > 20000:
            found.append(ctx.finding(r, f'{p.name} en büyük ölçüsü {_fmt(size)} mm; birim yanlış olabilir.',
                                     'DXF birimini (mm / inch) kontrol edin.', measured=size, part=p.name,
                                     marks=[Mark('area', list(p.outline.polygon.exterior.coords))]))
    return found


@rule('DFM-GEO-013', 'Kapalı parça bulunamadı', 'geometry', severity=ERROR, needs_limit=False,
      description='Çizimde kapalı bir dış hat yok.', uses='Kapalı konturlar')
def no_parts(ctx, r, limit):
    if ctx.topology.parts:
        return []
    return [ctx.finding(r, 'Kapalı parça dış hattı bulunamadı; parça kontrolleri yapılamadı.',
                        'Açık kontur ve kesişim bulgularını giderin.')]
