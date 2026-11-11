"""Independent assembled-boundary, offsets and public-input regression checks."""
from dataclasses import replace
import pytest
from shapely import affinity, union_all
from shapely.geometry import Point, Polygon, box

from modules.nesting.models import Part
from modules.smart_splitting.models import SplitSettings
from modules.smart_splitting.splitter import split
from modules.smart_splitting.validation import validate_partition


@pytest.mark.parametrize('count,angle',[(2,0),(3,90),(4,-73.3),(6,359.9),(32,13.7),(64,0)])
def test_assembled_boundary_has_no_slit_or_spike_despite_negligible_area_error(count,angle):
    source=Point(0,0).buffer(250,quad_segs=64)
    result=split(Part.create('DISC',source),SplitSettings(count=count,start_angle=angle,min_width=.01))
    assembled=union_all([s.nominal for s in result.segments])
    assert assembled.geom_type=='Polygon'
    assert len(assembled.interiors)==len(source.interiors)
    assert source.boundary.hausdorff_distance(assembled.boundary)<1e-7
    assert abs(source.area-sum(s.nominal.area for s in result.segments))<1e-6


def test_independent_validator_rejects_an_almost_zero_area_but_long_slit():
    original=box(0,0,100,100)
    # Tiny area loss can pass the original area-only gates, while the cut leaves
    # a 50 mm crack on the assembled contour.
    upper=box(0,50+1e-10,100,100)
    lower=box(0,0,100,50)
    with pytest.raises(ValueError,match='kontur|birleşim|bağlantı'):
        validate_partition(original,[upper,lower],2)


def test_numeric_range_and_type_validation_never_leak_type_or_geometry_errors():
    source=Part.create('A',box(0,0,100,100))
    bad=[dict(min_width='1'),dict(start_angle='a'),dict(start_angle=True),dict(angles=('a',)),
         dict(angles=None),dict(center=('a',2)),dict(center=5),dict(forbidden=(None,)),
         dict(profile=[]),dict(material=42),dict(center=(1e308,1e308))]
    for changes in bad:
        with pytest.raises(ValueError): split(source,replace(SplitSettings(count=4),**changes))
    for angles in (12,('a','b','c','d'),(0,90,180,True)):
        with pytest.raises(ValueError): split(source,SplitSettings(count=4),angles=angles)


def test_translated_geometry_and_large_start_angle_are_equivalent():
    source=Polygon([(0,0),(400,0),(500,200),(360,480),(140,500),(-30,250)])
    a=split(Part.create('A',source),SplitSettings(count=7,start_angle=13.7,min_width=.1))
    offset=(1750.,-825.)
    b=split(Part.create('B',affinity.translate(source,*offset)),SplitSettings(count=7,start_angle=373.7,min_width=.1))
    for first,second in zip(a.segments,b.segments):
        restored=affinity.translate(second.nominal,-offset[0],-offset[1])
        assert first.nominal.symmetric_difference(restored).area<1e-6


def test_circle_classification_has_no_overflow_for_finite_large_area_and_perimeter():
    from modules.smart_splitting.analysis import analyze
    normal=Part.create('Normal circle',Point(0,0).buffer(5,quad_segs=32))
    large=Part.create('Large circle',Point(0,0).buffer(5e153,quad_segs=32))
    assert analyze(normal)['kind']==analyze(large)['kind']=='Daire'


def test_source_with_finite_area_but_overflowed_perimeter_is_rejected():
    import numpy as np
    from modules.smart_splitting.analysis import analyze
    with np.errstate(over='ignore',invalid='ignore'):
        with pytest.raises(ValueError,match='kaynak parça'):
            analyze(Part.create('Too long',box(0,0,1e200,1)))


@pytest.mark.parametrize('count',[2,3,4,6,8])
def test_weld_gap_removes_only_material_near_actual_joining_edges(count):
    original=Point(0,0).buffer(250,quad_segs=64)
    result=split(Part.create('A',original),SplitSettings(count=count,weld_gap=2,min_width=.01))
    assert all(s.blank.geom_type=='Polygon' and s.blank.is_valid for s in result.segments)
    assembled=union_all([s.blank for s in result.segments])
    assert assembled.difference(original).area<1e-6
    assert assembled.area<original.area
    assert all(a.blank.intersection(b.blank).area<1e-6 for i,a in enumerate(result.segments) for b in result.segments[i+1:])


def test_detailed_profile_center_search_keeps_explicit_centers_fixed():
    from modules.smart_splitting.splitter import candidates
    source=Part.create('A',Point(100,100).buffer(100))
    auto=list(candidates(source,SplitSettings(count=6,profile='Detaylı')))
    fixed=list(candidates(source,SplitSettings(count=6,profile='Detaylı',center=(101,99))))
    assert len(auto)==len(fixed)==13
    assert any(settings.center is not None for _,settings,_,_ in auto)
    assert all(settings.center==(101,99) for _,settings,_,_ in fixed)
    for _,settings,angles,mode in auto:
        result=split(source,settings,mode=mode,angles=angles)
        assert len(result.segments)==6
