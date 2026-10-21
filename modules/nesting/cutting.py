"""Contour-level cut precedence, independent of the placement search.

Every closed contour inside another has a smaller enclosed area. Ascending
enclosed area therefore puts child parts before their surrounding hole, and a
part's own holes before its outer outline, including nested/multipart groups.
This is an ordering proposal, not a kerf-compensated CAM toolpath.
"""

from dataclasses import dataclass
from shapely.geometry import Polygon

from modules.nesting.geometry import rings, placed


@dataclass(frozen=True)
class CutContour:
    sequence: int
    placement_index: int
    ring_index: int
    inner: bool
    area: float
    coordinates: tuple


def contour_plan(project, result, key, *, stop=None):
    from modules.nesting.dxf_import import check_cancel
    contours=[]
    for index,placement in enumerate(result.placements):
        if (placement.sheet_id,placement.sheet_number) != key:
            continue
        check_cancel(stop)
        geometry=placed(project.part(placement.part_id),placement)
        for ring_index,(inner,coordinates) in enumerate(rings(geometry)):
            contours.append((Polygon(coordinates).area,inner,index,ring_index,tuple(coordinates)))
    contours.sort(key=lambda row:(row[0],row[1],row[2],row[3]))
    return [CutContour(sequence,index,ring_index,inner,area,coords)
            for sequence,(area,inner,index,ring_index,coords) in enumerate(contours,1)]
