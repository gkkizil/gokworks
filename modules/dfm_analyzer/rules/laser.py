"""DFM-LAS: laser-cutting checks against the selected machine/material profile.

Limits are max(min_mm, factor_t × thickness) from the profile. A value exactly
at the limit passes. Widths are measured on the flattened contour, so they
carry the flattening accuracy (default 0.01 mm), recorded in each rule.
"""

from shapely.geometry import Polygon
from shapely.strtree import STRtree
from shapely import maximum_inscribed_circle

from .base import rule, Mark, NotEvaluated, ERROR, WARNING
from ..geometry.topology import hole_width, closest

EPS = 1e-6
ACCURACY = 'Ölçüm, eğri düzleştirme doğruluğu (varsayılan 0,01 mm) kadar sapabilir.'


def _fmt(value):
    return f'{value:.3f}'.rstrip('0').rstrip('.').replace('.', ',')


def _ring(polygon):
    return list(polygon.exterior.coords)


def _thin_regions(polygon, width, keep_away=None, accuracy=.01):
    """Regions of ``polygon`` narrower than ``width`` (morphological opening).

    Convex corners leave a residue of area ≤ r²(cot(θ/2) − (π−θ)/2) for a
    corner of angle θ; requiring area > r² keeps corners of about 50° and
    wider out of the result. Sharper tips are genuinely narrow and are kept.
    """
    r = width / 2 - EPS
    if r <= 0:
        return []
    opened = polygon.buffer(-r, quad_segs=16).buffer(r, quad_segs=16)
    residue = polygon.difference(opened)
    regions = []
    for g in getattr(residue, 'geoms', [residue]):
        if g.is_empty or g.geom_type != 'Polygon' or g.area <= r * r:
            continue
        if keep_away is not None and g.distance(keep_away) <= accuracy:
            continue
        radius = maximum_inscribed_circle(g, accuracy).length
        regions.append((g, 2 * radius))
    return regions


@rule('DFM-LAS-001', 'Minimum delik çapı', 'laser', severity=ERROR,
      description='Yuvarlak delik çapı profilin minimum kesilebilir çapından küçük.',
      uses='Yuvarlak delikler (CIRCLE veya yuvarlak kapalı kontur)',
      reference='Profil değeri (makine/proses verisi); evrensel bir standart değeri değildir.',
      assumptions='Yuvarlak delikte gerçek çap kullanılır.')
def hole_diameter(ctx, r, limit):
    found = []
    for part in ctx.topology.parts:
        for hole in part.holes:
            ctx.checkpoint()
            if not hole.round:
                continue
            d, line = hole_width(hole)
            if d < limit - EPS:
                found.append(ctx.finding(r, f'Ø{_fmt(d)} mm delik, sınır Ø{_fmt(limit)} mm.',
                                         f'Deliği en az Ø{_fmt(limit)} mm yapın; daha küçük delik gerekiyorsa delme/zımbalama '
                                         'gibi ayrı bir işlem planlayın veya makine için doğrulayın.',
                                         measured=d, limit=limit, part=part.name, entities=hole.handles,
                                         marks=[Mark('area', _ring(hole.polygon)), Mark('line', line, f'Ø{_fmt(d)}')]))
    return found


@rule('DFM-LAS-002', 'Minimum kanal / boşluk genişliği', 'laser', severity=ERROR,
      description='Yuvarlak olmayan bir boşluğun en dar geçidi profil sınırından dar.',
      uses='Yuvarlak olmayan iç boşluklar', assumptions='Genişlik = en büyük iç teğet dairenin çapı. ' + ACCURACY)
def cutout_width(ctx, r, limit):
    found = []
    for part in ctx.topology.parts:
        for hole in part.holes:
            ctx.checkpoint()
            if hole.round:
                continue
            w, line = hole_width(hole, ctx.accuracy)
            if w < limit - EPS:
                found.append(ctx.finding(r, f'Boşluğun en dar yeri {_fmt(w)} mm, sınır {_fmt(limit)} mm.',
                                         f'Kanalı en az {_fmt(limit)} mm genişletin veya makine için doğrulayın.',
                                         measured=w, limit=limit, part=part.name, entities=hole.handles,
                                         marks=[Mark('area', _ring(hole.polygon)), Mark('line', line, f'{_fmt(w)} mm')]))
    return found


@rule('DFM-LAS-003', 'Delik – dış kenar et kalınlığı', 'laser', severity=WARNING,
      description='Bir delik/boşluk ile parçanın dış kenarı arasındaki malzeme profil sınırından ince.',
      uses='İç boşluklar ve dış hat', assumptions='En kısa sınırdan sınıra mesafe. ' + ACCURACY)
def edge_distance(ctx, r, limit):
    found = []
    for part in ctx.topology.parts:
        edge = part.outline.polygon.exterior
        for hole in part.holes:
            ctx.checkpoint()
            d, line = closest(hole.polygon.exterior, edge)
            if d < limit - EPS:
                found.append(ctx.finding(r, f'Delik ile dış kenar arası {_fmt(d)} mm, sınır {_fmt(limit)} mm (fark {_fmt(limit - d)} mm).',
                                         'Deliği dış kenardan uzaklaştırın veya bu makine/malzeme için minimum malzeme '
                                         'mesafesini doğrulayın; ince et ısıyla şekil bozabilir.',
                                         measured=d, limit=limit, part=part.name, entities=hole.handles,
                                         marks=[Mark('area', _ring(hole.polygon)), Mark('line', line, f'{_fmt(d)} mm')]))
    return found


@rule('DFM-LAS-004', 'Delikler arası malzeme köprüsü', 'laser', severity=WARNING,
      description='İki delik/boşluk arasındaki malzeme profil sınırından ince.',
      uses='İç boşluk çiftleri', assumptions='En kısa sınırdan sınıra mesafe. ' + ACCURACY)
def web_width(ctx, r, limit):
    found = []
    for part in ctx.topology.parts:
        rings = [h.polygon.exterior for h in part.holes]
        if len(rings) < 2:
            continue
        tree = STRtree(rings)
        for i, ring in enumerate(rings):
            ctx.checkpoint()
            for j in tree.query(ring, predicate='dwithin', distance=limit):
                j = int(j)
                if j <= i:
                    continue
                d, line = closest(ring, rings[j])
                if d < limit - EPS:
                    a, b = part.holes[i], part.holes[j]
                    found.append(ctx.finding(r, f'İki delik arası köprü {_fmt(d)} mm, sınır {_fmt(limit)} mm.',
                                             'Delikleri birbirinden uzaklaştırın, birleştirip tek boşluk yapın veya '
                                             'makine için minimum köprüyü doğrulayın.',
                                             measured=d, limit=limit, part=part.name, entities=a.handles + b.handles,
                                             marks=[Mark('area', _ring(a.polygon)), Mark('area', _ring(b.polygon)),
                                                    Mark('line', line, f'{_fmt(d)} mm')]))
    return found


@rule('DFM-LAS-005', 'İnce malzeme (parmak, dil)', 'laser', severity=WARNING,
      description='Dış hattın oluşturduğu bir dil/parmak profil sınırından ince.',
      uses='Parça malzemesi (delik ve kenar arası köprüler LAS-003/004’te)',
      assumptions='Morfolojik açma; ~50°’den geniş köşeler bulgu sayılmaz. ' + ACCURACY)
def feature_width(ctx, r, limit):
    found = []
    for part in ctx.topology.parts:
        ctx.checkpoint()
        holes = None
        if part.holes:
            from shapely import union_all
            holes = union_all([h.polygon.exterior for h in part.holes])
        for region, width in _thin_regions(part.material, limit, holes, ctx.accuracy):
            found.append(ctx.finding(r, f'Yaklaşık {_fmt(width)} mm genişliğinde ince malzeme, sınır {_fmt(limit)} mm.',
                                     'Dili/parmağı genişletin veya kısaltın; ince bölge kesimde ısıyla eğilebilir.',
                                     measured=width, limit=limit, part=part.name, entities=part.outline.handles,
                                     marks=[Mark('area', _ring(region), f'≈{_fmt(width)} mm')]))
    return found


@rule('DFM-LAS-006', 'Dar kenar çentiği', 'laser', severity=WARNING,
      description='Dış hattaki bir çentik/kanal profil sınırından dar.',
      uses='Dış hat', assumptions='Morfolojik kapama; ~50°’den geniş iç köşeler bulgu sayılmaz. ' + ACCURACY)
def notch_width(ctx, r, limit):
    found = []
    radius = limit / 2 - EPS
    for part in ctx.topology.parts:
        ctx.checkpoint()
        outline = Polygon(part.outline.polygon.exterior)
        closed = outline.buffer(radius, quad_segs=16).buffer(-radius, quad_segs=16)
        residue = closed.difference(outline)
        for g in getattr(residue, 'geoms', [residue]):
            if g.is_empty or g.geom_type != 'Polygon' or g.area <= radius * radius:
                continue
            width = 2 * maximum_inscribed_circle(g, ctx.accuracy).length
            found.append(ctx.finding(r, f'Yaklaşık {_fmt(width)} mm genişliğinde kenar çentiği, sınır {_fmt(limit)} mm.',
                                     f'Çentiği en az {_fmt(limit)} mm genişletin veya makine için doğrulayın.',
                                     measured=width, limit=limit, part=part.name, entities=part.outline.handles,
                                     marks=[Mark('area', _ring(g), f'≈{_fmt(width)} mm')]))
    return found


@rule('DFM-LAS-007', 'Malzeme ve kalınlık profil kapsamı', 'laser', severity=ERROR, needs_limit=False,
      description='Seçilen malzeme/kalınlık profilin kesim kapsamında değil.', uses='Malzeme ve sac kalınlığı girdisi')
def material_scope(ctx, r, limit):
    if ctx.thickness is None:
        raise NotEvaluated('Sac kalınlığı girilmedi.')
    found = []
    low, high = ctx.profile.thickness_range or (None, None)
    if low is not None and not low - EPS <= ctx.thickness <= high + EPS:
        found.append(ctx.finding(r, f'{_fmt(ctx.thickness)} mm kalınlık profil aralığının ({_fmt(low)}–{_fmt(high)} mm) dışında.',
                                 'Başka bir makine/profil seçin veya kapasiteyi doğrulayın.',
                                 measured=ctx.thickness, limit=high if ctx.thickness > high else low))
    materials = ctx.profile.materials
    if materials and ctx.material and ctx.material.casefold() not in {m.casefold() for m in materials}:
        found.append(ctx.finding(r, f'“{ctx.material}” malzemesi profilde tanımlı değil.',
                                 'Malzemeyi profile ekleyin veya uygun profili seçin.'))
    return found


@rule('DFM-LAS-008', 'Parça sac/tabla ölçüsüne sığıyor mu', 'laser', severity=ERROR, needs_limit=False,
      description='Parça profilin kullanılabilir tabla ölçüsüne (90° döndürülmüş dahil) sığmıyor.',
      uses='Parça dış hattı', assumptions='Eksen hizalı sınır kutusu; serbest açı yerleşimi dikkate alınmaz.')
def envelope(ctx, r, limit):
    size = ctx.profile.envelope
    if not size:
        raise NotEvaluated('Profilde tabla ölçüsü tanımlı değil.')
    width, height = sorted(size)
    found = []
    for part in ctx.topology.parts:
        minx, miny, maxx, maxy = part.outline.polygon.bounds
        a, b = sorted((maxx - minx, maxy - miny))
        if a > width + EPS or b > height + EPS:
            found.append(ctx.finding(r, f'{part.name} {_fmt(maxx - minx)} × {_fmt(maxy - miny)} mm; tabla {_fmt(size[0])} × {_fmt(size[1])} mm.',
                                     'Parçayı bölün veya daha büyük tablalı makine seçin.', part=part.name,
                                     marks=[Mark('area', _ring(part.outline.polygon))]))
    return found
