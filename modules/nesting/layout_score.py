"""One physical objective for the Sparrow seed and GOKWORKS improvements."""
from collections import defaultdict

from shapely import affinity


def plate_strip_area(sheet, rows, bounds):
    """Occupied edge strip estimate, retaining either horizontal or vertical remnants."""
    right = max((p.x+bounds(p.part_id,p.angle)[2] for p in rows),default=0.)
    top = max((p.y+bounds(p.part_id,p.angle)[3] for p in rows),default=0.)
    return min(sheet.height*right,sheet.width*top)


def layout_score(project, result, bounds=None):
    if bounds is None:
        source = {p.id:p.polygon for p in project.parts}; cache = {}
        def bounds(part_id, angle):
            key = (part_id,angle)
            if key not in cache:
                cache[key] = affinity.rotate(source[part_id],angle,origin=(0,0)).bounds
            return cache[key]
    groups = defaultdict(list)
    for p in result.placements: groups[(p.sheet_id,p.sheet_number)].append(p)
    sheets = {s.id:s for s in project.sheets}
    return (len(result.unplaced),len(groups),
            sum(sheets[key[0]].width*sheets[key[0]].height for key in groups),
            sum(plate_strip_area(sheets[key[0]],rows,bounds) for key,rows in groups.items()))
