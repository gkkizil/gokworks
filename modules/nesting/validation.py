"""Independent verification; no NFP caches or placement candidate code reused."""

from collections import Counter, defaultdict
import math

from shapely.geometry import box
from shapely.strtree import STRtree

from modules.nesting.geometry import placed

EPS = 1e-6


def validate_result(project, result, *, complete=True, stop=None):
    project.validate()
    if any(type(getattr(result,key)) is not bool for key in ('stopped','timed_out')):
        raise ValueError('Yerleşim durdurma ve süre bilgisi doğru/yanlış olmalı.')
    if result.digest != project.fingerprint():
        raise ValueError('Ayarlar veya parçalar değişti. Yeniden otomatik yerleşim yapın.')
    if complete and result.unplaced:
        raise ValueError(f'{len(result.unplaced)} parça yerleşmedi. Sac stokunu/ölçüsünü ve yerleşim koşullarını kontrol edin.')
    from modules.nesting.dxf_import import check_cancel
    parts = {part.id:part for part in project.parts}
    sheets = {sheet.id:sheet for sheet in project.sheets}
    groups = defaultdict(list); counts = Counter(); instances = set(); stocks = defaultdict(set)
    for p in result.placements:
        check_cancel(stop)
        if p.part_id not in parts or p.sheet_id not in sheets:
            raise ValueError('Yerleşimde tanımsız parça veya sac kimliği.')
        part, sheet = parts[p.part_id], sheets[p.sheet_id]
        if type(p.sheet_number) is not int or p.sheet_number < 1:
            raise ValueError('Geçersiz levha numarası.')
        if not all(math.isfinite(v) for v in (p.x, p.y, p.angle)):
            raise ValueError('Sonlu olmayan yerleşim koordinatı.')
        if part.material != sheet.material or not math.isclose(part.thickness, sheet.thickness, abs_tol=1e-7):
            raise ValueError('Parça malzemesi veya kalınlığı sacla eşleşmiyor.')
        allowed = [0] if not project.options.rotation else project.options.angles
        if project.options.grain_locked or part.grain_locked:
            allowed = [a for a in allowed if math.isclose(a % 180, 0, abs_tol=1e-7)]
        if not any(abs((p.angle-a+180) % 360-180) < EPS for a in allowed):
            raise ValueError('İzin verilmeyen dönüş açısı / hadde yönü.')
        if type(p.instance) is not int or not 1 <= p.instance <= part.quantity or (part.id, p.instance) in instances:
            raise ValueError('Yinelenmiş veya geçersiz parça örneği.')
        instances.add((part.id, p.instance)); counts[part.id] += 1
        stocks[sheet.id].add(p.sheet_number)
        geometry = placed(part, p)
        margin = project.options.margin+part.geometry_error+project.options.kerf/2
        if not box(margin-EPS, margin-EPS, sheet.width-margin+EPS, sheet.height-margin+EPS).covers(geometry):
            raise ValueError(part.code + ': sac kenar payı aşıldı.')
        collision = geometry
        groups[(sheet.id, p.sheet_number)].append((collision, part))
    for rows in groups.values():
        shapes = [g for g,_ in rows]; tree = STRtree(shapes)
        largest_error = max(part.geometry_error for _,part in rows)
        for i,(collision,part) in enumerate(rows):
            check_cancel(stop)
            search = max(project.options.gap,project.options.kerf)+part.geometry_error+largest_error+EPS
            for j in tree.query(collision,predicate='dwithin',distance=search):
                if j <= i: continue
                other,other_part = rows[j]
                required = max(project.options.gap,project.options.kerf)+part.geometry_error+other_part.geometry_error
                if collision.intersection(other).area > EPS or collision.distance(other)+EPS < required:
                    raise ValueError(part.code + ': parça çakışması veya yetersiz kesim aralığı.')
    for sheet_id, used in stocks.items():
        if len(used) > sheets[sheet_id].stock:
            raise ValueError('Sac stok adedi aşıldı.')
    expected = sum(p.quantity for p in project.parts)
    if any(counts[p.id] > p.quantity for p in project.parts) or len(result.placements)+len(result.unplaced) != expected:
        raise ValueError('İstenen adet ile yerleşen / yerleşmeyen adet toplamı tutarsız.')
    missing = Counter({p.id:p.quantity-counts[p.id] for p in project.parts if p.quantity != counts[p.id]})
    if Counter(result.unplaced) != missing:
        raise ValueError('Yerleşmeyen parça kimlikleri veya adetleri tutarsız.')
    return True
