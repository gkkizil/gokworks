"""Independent conservation, connectedness and finite geometric constraints."""
from itertools import combinations
import math

from shapely import union_all
from shapely.geometry import Polygon


def width(polygon):
    coordinates=list(polygon.minimum_rotated_rectangle.exterior.coords)
    return min(math.dist(a,b) for a,b in zip(coordinates,coordinates[1:]))


def validate_partition(source, segments, count):
    if len(segments)!=count: raise ValueError(f'İstenen {count} geçerli segment üretilemedi.')
    epsilon=max(1e-6,source.area*1e-9)
    for g in segments:
        if g.geom_type!='Polygon' or g.is_empty or not g.is_valid or g.area<=epsilon:
            raise ValueError('Bağlantısız ada, sıfır alan veya geçersiz segment oluştu; segment sayısı korunamadı.')
    area_delta=abs(source.area-sum(g.area for g in segments))
    assembled=union_all(segments)
    symmetric=source.symmetric_difference(assembled).area
    overlap=sum(a.intersection(b).area for a,b in combinations(segments,2))
    if max(area_delta,symmetric,overlap)>epsilon:
        raise ValueError('Alan korunumu, simetrik fark veya segment çakışma doğrulaması başarısız.')
    x0,y0,x1,y1=source.bounds
    contour_epsilon=max(1e-7,max(x1-x0,y1-y0)*1e-10)
    if (assembled.geom_type!='Polygon' or not assembled.is_valid
            or len(assembled.interiors)!=len(source.interiors)
            or source.boundary.hausdorff_distance(assembled.boundary)>contour_epsilon):
        raise ValueError('Bölümlerin birleşim konturunda bağlantı, yarık veya kontur sapması bulundu.')
    return area_delta,symmetric


def validate_manufacturing(polygon, settings):
    minimum=width(polygon)
    if minimum+1e-7<settings.min_width:
        raise ValueError(f'Minimum segment genişliği ihlali: {minimum:.3f} < {settings.min_width:g} mm.')
    if settings.min_web:
        eroded=polygon.buffer(-settings.min_web/2)
        if eroded.is_empty or eroded.geom_type!='Polygon':
            raise ValueError('Minimum et kalınlığı ön kontrolü: erozyonda parça yok oluyor veya dar boğaz ayrılıyor.')
        holes=[Polygon(r) for r in polygon.interiors]
        outside=polygon.exterior
        if any(h.distance(outside)+1e-7<settings.min_web for h in holes) or any(
                a.distance(b)+1e-7<settings.min_web for a,b in combinations(holes,2)):
            raise ValueError('Minimum et kalınlığı: delik–dış kenar veya delikler arası mesafe yetersiz.')
    return minimum
