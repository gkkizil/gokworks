"""Source validation and explicitly approximate contour classifications."""
from shapely.geometry import Polygon
import math

from modules.nesting.dxf_import import read_dxf


def validate_source(part):
    g=part.polygon
    if (g.geom_type!='Polygon' or not g.is_valid or g.is_empty or g.area<=0
            or not math.isfinite(g.area) or any(not math.isfinite(v) for v in g.bounds)):
        raise ValueError('Tek, kapalı ve bağlantılı bir kaynak parça seçin; ada/grup geometrisi bölünemez.')
    return g


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
    circle_score=4*3.141592653589793*exterior.area/exterior.length**2
    kind='Halka / delikli daire' if circle_score>.995 and g.interiors else 'Daire' if circle_score>.995 else 'Genel kontur'
    return dict(kind=kind,area=g.area,bounds=g.bounds,holes=len(g.interiors),
                bounds_center=((x0+x1)/2,(y0+y1)/2),centroid=(g.centroid.x,g.centroid.y),
                hole_bounds=[Polygon(ring).bounds for ring in g.interiors])
