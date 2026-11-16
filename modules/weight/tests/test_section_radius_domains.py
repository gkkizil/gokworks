"""An area formula is valid only while its corner arcs fit without overlap."""

import pytest
from shapely.geometry import Point, box

from modules.weight.rules import calculate


@pytest.mark.parametrize('kind,h', (
    ('Eşit kollu köşebent', 50.),
    ('Farklı kollu köşebent', 80.),
))
def test_angle_toe_cannot_extend_through_the_wall(kind, h):
    with pytest.raises(ValueError, match='Uç yarıçapı'):
        calculate(kind=kind, b=50., h=h, t=2., r1=15.)


@pytest.mark.parametrize('b,h', ((10., 50.), (50., 10.)))
def test_root_and_toe_arcs_cannot_overlap_on_either_leg(b, h):
    with pytest.raises(ValueError, match='Kök ve uç'):
        calculate(kind='Farklı kollu köşebent', b=b, h=h, t=5., r1=5.)


@pytest.mark.parametrize('h', (20., 30.))
def test_touching_arcs_match_an_independent_geometric_area(h):
    # r2=t=5; r1+r2=b-t=15. Both valid equality boundaries are exercised.
    # Construct the cross section by adding the root and removing convex toe
    # regions from rectangles, rather than using the scalar area formula.
    b, t, root, toe = 20., 5., 10., 5.

    def circle(x, y, radius):
        return Point(x, y).buffer(radius, quad_segs=2048)

    section = box(0, 0, b, t).union(box(0, 0, t, h))
    root_region = box(t, t, t+root, t+root).difference(circle(t+root, t+root, root))
    horizontal_toe = box(b-toe, t-toe, b, t).difference(circle(b-toe, t-toe, toe))
    vertical_toe = box(t-toe, h-toe, t, h).difference(circle(t-toe, h-toe, toe))
    section = section.union(root_region).difference(horizontal_toe.union(vertical_toe))
    assert section.is_valid and section.geom_type == 'Polygon'
    result = calculate(kind='Farklı kollu köşebent', b=b, h=h, t=t, r1=root)
    # The geometry oracle uses inscribed polygons; retain its discretization
    # bound instead of demanding exact agreement with circular arcs.
    assert result.area_mm2 == pytest.approx(section.area, abs=1e-5)
