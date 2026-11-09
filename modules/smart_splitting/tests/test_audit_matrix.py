"""220 generated cases with an independent boundary/topology oracle."""
from shapely import affinity, union_all
from shapely.geometry import Point, Polygon
import pytest

from modules.nesting.models import Part
from modules.smart_splitting.splitter import split
from modules.smart_splitting.models import SplitSettings
from modules.smart_splitting.adapter import to_project
from modules.smart_splitting.dxf_export import export_segments


@pytest.mark.parametrize('kind',['disc','ring','ellipse','convex'])
def test_counts_angles_and_topology_matrix(kind,tmp_path):
    disc=Point(0,0).buffer(250,quad_segs=64)
    shapes=dict(disc=disc,ring=disc.difference(Point(0,0).buffer(100,quad_segs=48)),
        ellipse=affinity.scale(disc,1.5,.6),convex=Polygon([(0,0),(400,0),(500,200),(360,480),(140,500),(-30,250)]))
    original=shapes[kind]; source=Part.create(kind,original)
    for count in (2,3,4,5,6,7,8,12,16,32,64):
        for angle in (0.,13.7,90.,-73.3,359.9):
            result=split(source,SplitSettings(count=count,start_angle=angle,min_width=.01))
            parts=[s.nominal for s in result.segments]; assembled=union_all(parts)
            assert len(parts)==count and all(p.geom_type=='Polygon' and p.is_valid for p in parts)
            assert assembled.geom_type=='Polygon' and assembled.is_valid
            assert len(assembled.interiors)==len(original.interiors)
            assert original.boundary.hausdorff_distance(assembled.boundary)<1e-7,(kind,count,angle)
            assert original.symmetric_difference(assembled).area<1e-6
            assert abs(sum(p.area for p in parts)-original.area)<1e-6
            assert abs(result.seam_length-sum(s.seam_length for s in result.segments)/2)<1e-6
            assert all(s.number in result.segments[n-1].neighbors for s in result.segments for n in s.neighbors)
            if count in (2,7,64) and angle==13.7:
                to_project(result).validate()
                assert len(export_segments(result,tmp_path/str(count)))==count
