"""Source validation and explicitly approximate contour classifications."""
from shapely.geometry import Polygon
import math



def read_dxf(*args, **kwargs):
    # ezdxf (~0,25 s) loads with the first DXF read, not with the page.
    from modules.nesting.dxf_import import read_dxf as read
    return read(*args, **kwargs)


def validate_source(part):
    g=part.polygon
    if (g.geom_type!='Polygon' or not g.is_valid or g.is_empty or g.area<=0
            or not math.isfinite(g.area) or not math.isfinite(g.length)
            or any(not math.isfinite(v) for v in g.bounds)):
        raise ValueError('Tek, kapalı ve bağlantılı bir kaynak parça seçin; ada/grup geometrisi bölünemez.')
    return g


def centroid(g):
    """Area centroid that stays finite for any valid (finite) source.

    GEOS squares coordinates while integrating: a valid source around 1e150 mm
    returns NaN. The shape is scaled to its own size first and back afterwards;
    for ordinary parts the result equals g.centroid to rounding.
    """
    from shapely import affinity
    x0,y0,x1,y1=g.bounds
    cx,cy=(x0+x1)/2,(y0+y1)/2
    size=max(x1-x0,y1-y0) or 1.0
    unit=affinity.scale(affinity.translate(g,-cx,-cy),1/size,1/size,origin=(0,0))
    c=unit.centroid
    point=(cx+c.x*size,cy+c.y*size)
    if not all(math.isfinite(v) for v in point):
        raise ValueError('Kaynak parçanın ağırlık merkezi hesaplanamadı; geometriyi kontrol edin.')
    return point


def load_parts(path, *, unit=None, tolerance=.05, stop=None):
    """DXF directly; DWG through Nesting's converter (installed ODA, else the bundled LibreDWG)."""
    from pathlib import Path
    if Path(path).suffix.lower()=='.dwg':
        from modules.nesting.dwg_import import read_dwg
        parts=read_dwg(path,unit=unit,tolerance=tolerance,stop=stop)
    else:
        parts=read_dxf(path,unit=unit,tolerance=tolerance,stop=stop)
    for part in parts: validate_source(part)
    return parts


def analyze(part):
    g=validate_source(part); x0,y0,x1,y1=g.bounds
    exterior=Polygon(g.exterior)
    # Divide before scaling/squaring: finite area/perimeter can still overflow
    # the original intermediate products for a large but valid source.
    circle_score=(exterior.area/exterior.length)/exterior.length*(4*math.pi)
    kind='Halka / delikli daire' if circle_score>.995 and g.interiors else 'Daire' if circle_score>.995 else 'Genel kontur'
    return dict(kind=kind,area=g.area,bounds=g.bounds,holes=len(g.interiors),
                bounds_center=((x0+x1)/2,(y0+y1)/2),centroid=centroid(g),
                hole_bounds=[Polygon(ring).bounds for ring in g.interiors])
