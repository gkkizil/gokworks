from dataclasses import replace
from threading import Event
import math

import ezdxf
import pytest
from shapely import union_all
from shapely.geometry import LineString, Point, Polygon, box, mapping

from modules.nesting.models import Part
from modules.nesting.dxf_import import read_dxf, MissingUnits
from modules.smart_splitting.analysis import analyze, load_parts
from modules.smart_splitting.models import SplitSettings
from modules.smart_splitting.splitter import split
from modules.smart_splitting.validation import validate_partition
from modules.smart_splitting.dxf_export import export_segments
from modules.smart_splitting.adapter import to_project


def circle_dxf(path, *, radius=900, bore=0, bolts=False, units=4):
    doc=ezdxf.new(); doc.units=units; m=doc.modelspace(); m.add_circle((0,0),radius)
    if bore: m.add_circle((0,0),bore)
    if bolts:
        for i in range(6):
            angle=math.radians(i*60); m.add_circle((radius*.7*math.cos(angle),radius*.7*math.sin(angle)),radius*.025)
    doc.saveas(path); return path


def check(solution):
    assert len(solution.segments)==solution.settings.count
    assert all(s.nominal.is_valid and s.nominal.geom_type=='Polygon' for s in solution.segments)
    assert sum(s.nominal.area for s in solution.segments)==pytest.approx(solution.source.area,rel=1e-9)
    assert union_all([s.nominal for s in solution.segments]).symmetric_difference(solution.source.polygon).area<1e-5
    for i,a in enumerate(solution.segments):
        assert len(a.neighbors)>0 and a.seam_length>0
        for b in solution.segments[i+1:]: assert a.nominal.intersection(b.nominal).area<1e-5
    project=to_project(solution); project.validate()
    assert len(project.parts)==solution.settings.count
    assert sum(p.quantity for p in project.parts)==solution.settings.count*solution.settings.quantity


@pytest.mark.parametrize('radius,count,bore',[(500,4,0),(900,6,0),(600,8,300)])
def test_required_circles_and_ring_exact_count_area_seams_and_dxf(tmp_path,radius,count,bore):
    source=load_parts(circle_dxf(tmp_path/'source.dxf',radius=radius,bore=bore))[0]
    original=(tmp_path/'source.dxf').read_bytes()
    solution=split(source,SplitSettings(count=count))
    check(solution)
    assert solution.seam_length==pytest.approx(count*(radius-bore),abs=.7)
    outputs=export_segments(solution,tmp_path/'out')
    assert len(outputs)==count
    assert all(len(read_dxf(p,tolerance=.05))==1 for p in outputs)
    assert (tmp_path/'source.dxf').read_bytes()==original


def test_smart_angles_avoid_bolt_holes_and_can_be_asymmetric(tmp_path):
    p=load_parts(circle_dxf(tmp_path/'bolts.dxf',radius=500))[0]
    # One large off-axis hole forces only one ray away from its equal angle.
    g=p.polygon.difference(Point(850,500).buffer(45,quad_segs=20))
    p=Part.create('BOLT',g)
    settings=SplitSettings(count=4,hole_clearance=15,min_width=20)
    with pytest.raises(ValueError,match='kritik delik'): split(p,settings)
    solution=split(p,settings,mode='smart'); check(solution)
    assert solution.angles[0]!=0 and solution.angles[1]==90
    hole=Polygon(g.interiors[0])
    assert all(edge.distance(hole)>=15-1e-5 for s in solution.segments for edge in s.seam_edges)


def test_asymmetric_general_contour_and_center_difference():
    g=Polygon([(0,0),(500,0),(520,200),(400,460),(180,510),(0,300)])
    part=Part.create('ASYM',g)
    assert analyze(part)['centroid']!=analyze(part)['bounds_center']
    solution=split(part,SplitSettings(count=5,center_mode='centroid')); check(solution)


def test_cut_through_inner_hole_is_nominally_valid_and_warned():
    part=Part.create('HOLE',box(0,0,100,100).difference(Point(75,50).buffer(10)))
    result=split(part,SplitSettings(count=4,start_angle=0))
    check(result)
    assert any('delik/slotları açıyor' in s for s in result.warnings)


def test_open_self_crossing_and_unit_errors_are_not_repaired_silently(tmp_path):
    for i,vertices in enumerate([[(0,0),(20,0),(20,20)],[(0,0),(20,20),(20,0),(0,20),(0,0)]]):
        doc=ezdxf.new(); doc.units=4; doc.modelspace().add_lwpolyline(vertices); path=tmp_path/f'bad{i}.dxf'; doc.saveas(path)
        with pytest.raises(ValueError): load_parts(path)
    path=circle_dxf(tmp_path/'unitless.dxf',units=0)
    with pytest.raises(MissingUnits): load_parts(path)
    assert load_parts(path,unit='mm')


def test_inch_and_mm_physical_equivalence(tmp_path):
    mm=load_parts(circle_dxf(tmp_path/'mm.dxf',radius=254,units=4))[0]
    inch=load_parts(circle_dxf(tmp_path/'inch.dxf',radius=10,units=1))[0]
    a,b=(split(p,SplitSettings(count=4)) for p in (mm,inch))
    assert mm.polygon.hausdorff_distance(inch.polygon)<1e-6
    assert [s.nominal.area for s in a.segments]==pytest.approx([s.nominal.area for s in b.segments])


def test_minimum_width_web_and_impossible_counts_are_hard_gates():
    part=Part.create('THIN',box(0,0,100,10))
    with pytest.raises(ValueError,match='genişliği'): split(part,SplitSettings(count=2,min_width=20))
    with pytest.raises(ValueError,match='et kalınlığı'): split(part,SplitSettings(count=2,min_web=25))
    with pytest.raises(ValueError,match='geçersiz segment|segment üretilemedi'):
        split(part,SplitSettings(count=6,center=(-100,0)))
    dumbbell=box(0,0,20,20).union(box(40,0,60,20)).union(box(20,8,40,12))
    with pytest.raises(ValueError): split(Part.create('NECK',dumbbell),SplitSettings(count=2,min_web=6))


def test_forbidden_regions_and_positive_hole_clearance_are_enforced():
    part=Part.create('A',Point(50,50).buffer(50))
    settings=SplitSettings(count=4,forbidden=(mapping(box(60,45,100,55)),))
    with pytest.raises(ValueError,match='yasaklı'): split(part,settings)
    check(split(part,settings,mode='smart'))


def test_original_quantity_and_stable_segment_identity():
    p=Part.create('SERIES',Point(100,100).buffer(100))
    settings=SplitSettings(count=6,quantity=5)
    a,b=split(p,settings),split(p,settings)
    check(a); assert [s.id for s in a.segments]==[s.id for s in b.segments]
    assert sum(p.quantity for p in to_project(a).parts)==30


def test_gap_allowance_and_kerf_are_separate_from_nominal_validation(tmp_path):
    p=Part.create('WELD',box(0,0,100,100))
    base=SplitSettings(count=2,start_angle=0,kerf=.4)
    gap=split(p,replace(base,weld_gap=2))
    allowance=split(p,replace(base,allowance=2))
    check(gap); check(allowance)
    assert sum(s.blank.area for s in gap.segments)<p.area
    assert sum(s.blank.area for s in allowance.segments)>p.area
    assert split(p,base).area_delta<1e-8
    export_segments(gap,tmp_path/'gap'); export_segments(allowance,tmp_path/'allowance')


def test_cancellation_invalid_parameters_and_independent_partition_validation():
    p=Part.create('A',box(0,0,100,100)); stop=Event(); stop.set()
    with pytest.raises(InterruptedError): split(p,SplitSettings(),stop=stop)
    for settings in (SplitSettings(count=1),SplitSettings(count=65),SplitSettings(count=6,quantity=2000),
                     SplitSettings(start_angle=math.nan),SplitSettings(weld_gap=1,allowance=1)):
        with pytest.raises(ValueError): split(p,settings)
    with pytest.raises(ValueError): validate_partition(p.polygon,[p.polygon,p.polygon],2)


def test_intact_circle_holes_survive_native_and_split_arcs_have_bounded_polylines(tmp_path):
    path=circle_dxf(tmp_path/'native.dxf',radius=100)
    doc=ezdxf.readfile(path); doc.modelspace().add_circle((40,40),4); doc.saveas(path)
    p=load_parts(path)[0]; s=split(p,SplitSettings(count=4))
    files=export_segments(s,tmp_path/'out')
    assert sum(len(ezdxf.readfile(f).modelspace().query('CIRCLE')) for f in files)==1
    assert all(ezdxf.readfile(f).units==4 for f in files)


@pytest.mark.parametrize('kind',['LINE','ARC','CIRCLE','LWPOLYLINE','POLYLINE','SPLINE'])
def test_supported_source_entities_split_export_and_reimport(tmp_path,kind):
    doc=ezdxf.new(); doc.units=4; m=doc.modelspace()
    if kind=='CIRCLE': m.add_circle((0,0),40)
    elif kind=='ARC': m.add_arc((0,0),40,0,180); m.add_line((-40,0),(40,0))
    elif kind=='LWPOLYLINE': m.add_lwpolyline([(0,0,1),(80,0,1)],format='xyb',close=True)
    elif kind=='POLYLINE': m.add_polyline2d([(0,0),(80,0),(80,40),(0,40)],close=True)
    elif kind=='SPLINE': m.add_spline([(0,0),(40,20),(80,0)]); m.add_line((80,0),(0,0))
    else:
        corners=[(0,0),(80,0),(80,40),(0,40)]
        for a,b in zip(corners,corners[1:]+corners[:1]): m.add_line(a,b)
    path=tmp_path/(kind+'.dxf'); doc.saveas(path)
    part=load_parts(path)[0]; result=split(part,SplitSettings(count=4,min_width=.1)); check(result)
    assert len(export_segments(result,tmp_path/'out'))==4


def test_slot_is_a_protected_inner_contour_in_smart_mode():
    slot=LineString([(650,500),(800,500)]).buffer(15)
    source=Part.create('SLOT',Point(500,500).buffer(500).difference(slot))
    settings=SplitSettings(count=4,hole_clearance=10)
    with pytest.raises(ValueError): split(source,settings)
    solution=split(source,settings,mode='smart'); check(solution)
    assert all(edge.distance(slot)>=10-1e-5 for s in solution.segments for edge in s.seam_edges)


def test_export_failure_and_cancel_are_atomic(tmp_path,monkeypatch):
    import modules.smart_splitting.dxf_export as exporter
    solution=split(Part.create('A',box(0,0,100,100)),SplitSettings(count=4))
    existing=tmp_path/'existing'; existing.mkdir(); marker=existing/'keep.txt'; marker.write_text('unchanged')
    with pytest.raises(FileExistsError): export_segments(solution,existing)
    assert marker.read_text()=='unchanged'
    stop=Event(); stop.set()
    with pytest.raises(InterruptedError): export_segments(solution,tmp_path/'cancelled',stop=stop)
    assert not (tmp_path/'cancelled').exists()
    def broken(*args,**kwargs): raise ValueError('controlled reimport failure')
    monkeypatch.setattr(exporter,'read_dxf',broken)
    with pytest.raises(ValueError): export_segments(solution,tmp_path/'invalid')
    assert not (tmp_path/'invalid').exists()
