"""Real hole packing, independent rejection, cut order and project compatibility."""

import csv
import json

import ezdxf
import pytest
from shapely.geometry import Polygon,box,Point,MultiPolygon

from modules.nesting.accounting import calculate
from modules.nesting.cutting import contour_plan
from modules.nesting.dxf_export import export_dxf
from modules.nesting.dxf_import import read_dxf
from modules.nesting.engine import nest
from modules.nesting.geometry import placed
from modules.nesting.materials import new_project
from modules.nesting.models import Part,Placement,Result
from modules.nesting.storage import load_project,save_project
from modules.nesting.validation import validate_result


def setup(parts,width=110,height=110):
    p=new_project();p.parts=parts
    p.sheets[0].width=width;p.sheets[0].height=height;p.sheets[0].stock=2
    p.options.margin=4;p.options.seconds=.7;p.options.quality='Hızlı'
    return p


def frame(size=90,inset=10):
    return Polygon(box(0,0,size,size).exterior,[box(inset,inset,size-inset,size-inset).exterior])


def manual_result(p,positions):
    return Result(p.fingerprint(),[Placement(p.parts[i].id,1,p.sheets[0].id,1,x,y,angle)
        for i,x,y,angle in positions],[],'test','1.3',0,1,'2026-10-21')


@pytest.mark.parametrize('code', ['=HYPERLINK("https://example.invalid")', '+1+2', '-1+2', '@SUM(1)', '  =1+2'])
def test_cut_order_csv_treats_imported_part_codes_as_text(tmp_path, code):
    p=setup([Part.create(code,box(0,0,20,20))])
    r=manual_result(p,[(0,5,5,0)])
    export_dxf(p,r,tmp_path/'cut')
    with (tmp_path/'cut/KESIM-SIRASI.csv').open(encoding='utf-8-sig') as stream:
        rows=list(csv.DictReader(stream,delimiter=';'))
    assert rows[0]['Parça']=="'"+code
    assert p.parts[0].code==code


def test_multiple_inserts_use_one_hole_and_reduce_sheets_without_double_counting_area():
    p=setup([Part.create('Frame',frame()),Part.create('Insert',box(0,0,25,25),quantity=4)])
    r=nest(p);assert validate_result(p,r)
    assert len(r.placements)==5 and len({x.sheet_number for x in r.placements})==1
    host=placed(p.parts[0],r.placements[0]);hole=Polygon(host.interiors[0])
    assert all(hole.covers(placed(p.part(x.part_id),x)) for x in r.placements[1:])
    totals=calculate(p,r)
    assert totals['net_area']==pytest.approx(sum(part.area*part.quantity for part in p.parts))
    assert totals['gross_area']==110*110
    assert totals['gross_weight']==pytest.approx(totals['net_weight']+totals['waste_weight'])


def test_circular_hole_hosts_small_parts_using_real_curved_clearance():
    geometry=box(0,0,100,100).difference(Point(50,50).buffer(35,quad_segs=48))
    p=setup([Part.create('Round hole',geometry,curve_tolerance=.02),
             Part.create('Small',box(0,0,12,12),quantity=4)],120,120)
    p.sheets[0].stock=1
    r=nest(p);assert validate_result(p,r)
    assert len(r.placements)==5
    host=placed(p.parts[0],r.placements[0]);hole=Polygon(host.interiors[0])
    for row in r.placements[1:]:
        small=placed(p.part(row.part_id),row)
        assert hole.covers(small) and host.distance(small)>=3.02-1e-6


def test_thin_frame_precedes_larger_net_area_insert_and_nested_frames_work():
    p=setup([Part.create('Thin frame',frame(100,5)),Part.create('Solid',box(0,0,65,65))],120,120)
    p.sheets[0].stock=1
    assert p.parts[0].area<p.parts[1].area
    r=nest(p);assert validate_result(p,r)
    assert r.placements[0].part_id==p.parts[0].id
    p=setup([Part.create('Outer',frame(120,10)),Part.create('Middle',frame(80,10)),
             Part.create('Core',box(0,0,40,40))],140,140)
    p.sheets[0].stock=1
    r=nest(p);assert validate_result(p,r)
    assert len({x.sheet_number for x in r.placements})==1
    contours=contour_plan(p,r,(p.sheets[0].id,1))
    codes=[(p.part(r.placements[c.placement_index].part_id).code,c.inner) for c in contours]
    assert codes==[('Core',False),('Middle',True),('Middle',False),('Outer',True),('Outer',False)]


def test_rotated_insert_fits_hole_but_grain_lock_is_preserved():
    host=Polygon(box(0,0,100,60).exterior,[box(10,10,90,40).exterior])
    p=setup([Part.create('Host',host),Part.create('Rotate',box(0,0,20,60))],115,75)
    p.sheets[0].stock=1
    r=nest(p);assert validate_result(p,r)
    small=next(x for x in r.placements if x.part_id==p.parts[1].id)
    assert small.angle in (90,270)
    p.parts[1].grain_locked=True
    r=nest(p);assert r.unplaced
    assert validate_result(p,r,complete=False)


@pytest.mark.parametrize('damage',['wall','clearance','curve_allowance','mismatch'])
def test_independent_verifier_rejects_invalid_hole_placement(damage):
    p=setup([Part.create('Host',frame()),Part.create('Small',box(0,0,20,20))])
    r=manual_result(p,[(0,5,5,0),(1,20,20,0)])
    assert validate_result(p,r)
    if damage=='wall':r.placements[1].x=10
    elif damage=='clearance':r.placements[1].x=16
    elif damage=='curve_allowance':p.parts[0].curve_tolerance=3
    else:p.parts[1].thickness=3
    r.digest=p.fingerprint()
    with pytest.raises(ValueError):validate_result(p,r)


def test_concave_hole_bbox_does_not_authorize_wall_overlap():
    hole=Polygon([(10,10),(80,10),(80,30),(30,30),(30,80),(10,80)])
    host=Polygon(box(0,0,90,90).exterior,[hole.exterior])
    p=setup([Part.create('Concave hole',host),Part.create('Too wide',box(0,0,30,30))])
    r=manual_result(p,[(0,5,5,0),(1,20,20,0)])
    assert Polygon(placed(p.parts[0],r.placements[0]).interiors[0]).envelope.covers(placed(p.parts[1],r.placements[1]))
    with pytest.raises(ValueError,match='çakışması'):validate_result(p,r)


def test_two_physical_sheets_reuse_their_own_holes():
    p=setup([Part.create('Frame',frame(),quantity=2),
             Part.create('Insert',box(0,0,25,25),quantity=8)])
    r=nest(p);assert validate_result(p,r)
    assert len(r.placements)==10 and len({x.sheet_number for x in r.placements})==2
    for number in (1,2):
        rows=[x for x in r.placements if x.sheet_number==number]
        assert len(rows)==5


def test_multiple_holes_of_one_part_are_separate_usable_regions():
    host=Polygon(box(0,0,190,90).exterior,
                 [box(10,10,80,80).exterior,box(110,10,180,80).exterior])
    p=setup([Part.create('Two holes',host),Part.create('Insert',box(0,0,50,50),quantity=2)],210,110)
    p.sheets[0].stock=1
    r=nest(p);assert validate_result(p,r)
    placed_host=placed(p.parts[0],r.placements[0]);used=set()
    for child in r.placements[1:]:
        geometry=placed(p.parts[1],child)
        used.update(i for i,ring in enumerate(placed_host.interiors) if Polygon(ring).covers(geometry))
    assert len(r.placements)==3 and used=={0,1}


def test_portable_hole_result_and_legacy_project_need_no_new_setting(tmp_path):
    p=setup([Part.create('Frame',frame()),Part.create('Insert',box(0,0,25,25))])
    r=nest(p);path=tmp_path/'holes.json';save_project(p,path,r)
    loaded,saved=load_project(path)
    assert saved==r
    # Old 1.2 projects have the same options schema and remain valid. The next
    # placement automatically uses holes without asking for an opt-in setting.
    old=Result(p.fingerprint(),[Placement(p.parts[0].id,1,p.sheets[0].id,1,5,5,0),
               Placement(p.parts[1].id,1,p.sheets[0].id,2,5,5,0)],[],
               'GOKWORKS NFP','1.2',0,1,'2026-10-21')
    save_project(p,path,old,overwrite=True)
    data=json.loads(path.read_text())
    assert 'nest_in_holes' not in data['project']['options']
    loaded,saved=load_project(path)
    assert saved.engine_version=='1.2' and validate_result(loaded,saved)
    assert len({p.sheet_number for p in nest(loaded).placements})==1
    data['project']['options']['gap']+=1;path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='değişti'):load_project(path)


def test_analytic_dxf_and_cut_csv_put_child_before_surrounding_hole(tmp_path):
    doc=ezdxf.new();doc.units=4;m=doc.modelspace()
    m.add_lwpolyline([(0,0),(100,0),(100,100),(0,100)],close=True);m.add_circle((50,50),35)
    source=tmp_path/'host.dxf';doc.saveas(source);original=source.read_bytes()
    host=read_dxf(source,tolerance=.02)[0];host.code='Host'
    p=setup([host,Part.create('Insert',frame(20,5))],120,120)
    r=nest(p);assert validate_result(p,r)
    paths=export_dxf(p,r,tmp_path/'cut')
    exported=ezdxf.readfile(paths[0]);cutting=[e for e in exported.modelspace() if e.dxf.layer.startswith('PART_') and e.dxf.layer in ('PART_OUTER','PART_INNER')]
    assert [e.dxftype() for e in cutting]==['LWPOLYLINE','LWPOLYLINE','CIRCLE','LWPOLYLINE']
    assert [e.get_xdata('GOKWORKS_NEST')[-1].value for e in cutting]==[1,2,3,4]
    with (tmp_path/'cut/KESIM-SIRASI.csv').open(encoding='utf-8-sig') as stream:
        rows=list(csv.DictReader(stream,delimiter=';'))
    assert [row['Parça'] for row in rows]==['Insert','Insert','Host','Host']
    assert [row['Kontur türü'] for row in rows]==['İç kontur','Dış kontur','İç kontur','Dış kontur']
    assert source.read_bytes()==original
    assert 'CAM' in (tmp_path/'cut/KESIM-NOTLARI.txt').read_text()


@pytest.mark.parametrize('separate',[True,False])
def test_cut_csv_and_dxf_metadata_keep_each_physical_plates_order(tmp_path,separate):
    p=setup([Part.create('Frame',frame(),quantity=2),Part.create('Insert',box(0,0,50,50),quantity=2)])
    r=nest(p);assert validate_result(p,r)
    paths=export_dxf(p,r,tmp_path/'cut',separate=separate)
    assert len(paths)==(2 if separate else 1)
    observed={}
    for path in paths:
        for entity in ezdxf.readfile(path).modelspace():
            if entity.dxf.layer not in ('PART_OUTER','PART_INNER'):continue
            plate,sequence=[tag.value for tag in entity.get_xdata('GOKWORKS_NEST')]
            observed.setdefault(plate,[]).append(sequence)
    assert observed=={1:[1,2,3],2:[1,2,3]}
    with (tmp_path/'cut/KESIM-SIRASI.csv').open(encoding='utf-8-sig') as stream:
        rows=list(csv.DictReader(stream,delimiter=';'))
    assert [(int(row['Plaka']),int(row['Kontur sırası'])) for row in rows]==[
        (1,1),(1,2),(1,3),(2,1),(2,2),(2,3)]


def test_multipart_groups_and_material_inside_a_hole_are_not_ignored():
    host=MultiPolygon([frame(),box(40,40,50,50)])
    p=setup([Part.create('Frame with island',host),Part.create('Insert',box(0,0,20,20))])
    r=manual_result(p,[(0,5,5,0),(1,40,40,0)])
    with pytest.raises(ValueError,match='çakışması'):validate_result(p,r)
