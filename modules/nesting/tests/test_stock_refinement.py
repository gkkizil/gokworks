"""Finite-stock quality and independent geometry checks around real layouts."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from threading import Event
from types import SimpleNamespace
import time

import pytest
from shapely.geometry import box, Polygon

from modules.nesting import engine
from modules.nesting.accounting import calculate
from modules.nesting.geometry import placed
from modules.nesting.materials import new_project
from modules.nesting.models import Part, Sheet, Placement, Result
from modules.nesting.search_budget import SearchBudget
from modules.nesting.validation import validate_result


def project(parts, sheets):
    p=new_project(); p.parts=parts; p.sheets=sheets
    p.options.margin=1; p.options.gap=3; p.options.kerf=.2
    p.options.rotation=False
    return p


def seed(p, positions):
    rows=[Placement(p.parts[i].id,instance,p.sheets[s].id,n,x,y,angle)
          for i,instance,s,n,x,y,angle in positions]
    result=Result(p.fingerprint(),rows,[],'fixture','1',0.,0,'')
    assert validate_result(p,result)
    return result


def refine(p, initial=None, stop=None):
    start=time.monotonic()
    return engine.nest(p,initial=initial,stop=stop,budget=SearchBudget(start,start+5,start+5,1))


def test_an_earlier_small_offcut_can_evacuate_into_a_later_large_plate():
    p=project([Part.create('Small bracket',box(0,0,20,80)),Part.create('Large bracket',box(0,0,70,80))],
              [Sheet('small','Offcut',30,100,stock=1),Sheet('large','Plate',100,100,stock=1)])
    initial=seed(p,[(0,1,0,1,1.1,1.1,0),(1,1,1,1,1.1,1.1,0)])
    before=deepcopy(asdict(initial)); source=deepcopy(asdict(p))
    result=refine(p,initial)
    assert validate_result(p,result) and not result.unplaced
    assert {(r.sheet_id,r.sheet_number) for r in result.placements}=={('large',1)}
    assert calculate(p,result)['waste_area']==2800
    assert asdict(p)==source and asdict(initial)==before


def test_exact_concave_repair_removes_a_plate_when_corner_moves_cannot():
    bracket=Polygon([(0,0),(100,0),(100,20),(20,20),(20,80),(100,80),(100,100),(0,100)])
    p=project([Part.create('C bracket',bracket),Part.create('Insert',box(0,0,50,40))],
              [Sheet('s','Plate',100,100,stock=2)])
    p.options.margin=p.options.gap=p.options.kerf=0
    initial=seed(p,[(0,1,0,1,0,0,0),(1,1,0,2,0,0,0)])
    result=refine(p,initial)
    assert validate_result(p,result) and {r.sheet_number for r in result.placements}=={1}
    shapes=[placed(p.part(r.part_id),r) for r in result.placements]
    assert shapes[0].intersection(shapes[1]).area<1e-6
    assert calculate(p,result)['waste_area']==2800


@pytest.mark.parametrize('locked',[False,True])
def test_smaller_stock_requires_a_real_allowed_rotation(locked):
    p=project([Part.create('Bar',box(0,0,60,20),grain_locked=locked)],
              [Sheet('large','Plate',100,100,stock=1),Sheet('small','Offcut',30,70,stock=1)])
    p.options.rotation=True
    initial=seed(p,[(0,1,0,1,1.1,1.1,0)])
    result=refine(p,initial)
    assert validate_result(p,result)
    assert result.placements[0].sheet_id==('large' if locked else 'small')
    assert result.placements[0].angle in ((0,180) if locked else (90,270))


@pytest.mark.parametrize('unusable',['empty','material','thickness','dimensions'])
def test_ineligible_smaller_stocks_cannot_replace_the_source(unusable):
    p=project([Part.create('Bar',box(0,0,60,20))],
              [Sheet('large','Plate',100,100,stock=1),Sheet('small','Offcut',70,40,stock=1)])
    s=p.sheets[1]
    if unusable=='empty':s.stock=0
    elif unusable=='material':s.material='AISI 304'
    elif unusable=='thickness':s.thickness=3
    else:s.width=5;s.height=500
    result=refine(p,seed(p,[(0,1,0,1,1.1,1.1,0)]))
    assert validate_result(p,result) and result.placements[0].sheet_id=='large'


def test_small_stock_quantity_is_reserved_once_and_numbering_stays_unique():
    p=project([Part.create('Bracket',box(0,0,60,60),quantity=2)],
              [Sheet('large','Plate',100,100,stock=2),Sheet('small','Offcut',70,70,stock=1)])
    initial=seed(p,[(0,1,0,1,1.1,1.1,0),(0,2,0,2,1.1,1.1,0)])
    result=refine(p,initial)
    assert validate_result(p,result)
    assert Counter(r.sheet_id for r in result.placements)=={'small':1,'large':1}
    assert {r.instance for r in result.placements}=={1,2}
    assert {r.sheet_number for r in result.placements}=={1}


def test_rebuilding_drops_unused_target_plates_from_stock_reservations():
    from modules.nesting.stock_refinement import refine_stock
    p=project([Part.create('Bracket',box(0,0,5,5),quantity=3)],
              [Sheet(k,k,100,100,stock=1) for k in ('source','a','b')])
    initial=seed(p,[(0,1,0,1,2,2,0),(0,2,1,1,2,2,0),(0,3,2,1,2,2,0)])
    plates=[(s,1,[r for r in initial.placements if r.sheet_id==s.id]) for s in p.sheets]
    rebuilding=False; committed=[]
    def place(part,sheet,previous,precise):
        nonlocal rebuilding
        if sheet.id!='a':return None
        if not previous:rebuilding=True
        if rebuilding:return (2+10*len(previous),2,0)
        return None  # Simulate a failed heuristic move before a full rebuild.
    result,counts=refine_stock(p,plates,place,lambda *args:(0,0,5,5),lambda:None,
                              lambda rows:committed.append(deepcopy(rows)))
    assert counts=={'a':1} and len(result)==1 and len(result[0][2])==3
    assert all(rows for _,_,rows in committed[-1])
    assert validate_result(p,Result(p.fingerprint(),result[0][2],[],'fixture','1',0.,0,''))


@pytest.mark.parametrize('interruption',['cancel','timeout'])
def test_a_completed_stock_repair_survives_interruption_of_the_next_draft(monkeypatch,interruption):
    p=project([Part.create('Steel',box(0,0,20,20)),Part.create('Stainless',box(0,0,20,20),material='AISI 304')],
              [Sheet('steel','Plate',100,100,stock=1),Sheet('stainless','Plate',100,100,material='AISI 304',stock=1),
               Sheet('steel-small','Offcut',50,50,stock=1),Sheet('stainless-small','Offcut',50,50,material='AISI 304',stock=1)])
    initial=seed(p,[(0,1,0,1,1.1,1.1,0),(1,1,1,1,1.1,1.1,0)])
    before=deepcopy(asdict(initial)); stop=Event(); original=engine.refine_stock
    def repair(project,plates,place,bounds,checkpoint,commit):
        def committed(draft):
            commit(draft)
            if interruption=='cancel':stop.set()
            else:monkeypatch.setattr(engine,'time',SimpleNamespace(monotonic=lambda:time.monotonic()+100))
        return original(project,plates,place,bounds,checkpoint,committed)
    monkeypatch.setattr(engine,'refine_stock',repair)
    result=refine(p,initial,stop)
    assert validate_result(p,result) and not result.unplaced
    assert calculate(p,result)['gross_area']==12500
    assert asdict(initial)==before
    assert result.stopped if interruption=='cancel' else not result.stopped
    assert result.timed_out==(interruption=='timeout')


def test_incomplete_demand_opens_needed_stock_before_expensive_plate_repairs(monkeypatch):
    p=project([Part.create('Bracket',box(0,0,60,60),quantity=2)],[Sheet('s','Plate',100,100,stock=2)])
    initial=Result(p.fingerprint(),[Placement(p.parts[0].id,1,'s',3,1.1,1.1,0)],
                   [p.parts[0].id],'fixture','1',0.,0,'')
    assert validate_result(p,initial,complete=False)
    def forbidden(*args):raise AssertionError('Finish demand before plate repair')
    monkeypatch.setattr(engine,'refine_stock',forbidden)
    result=refine(p,initial)
    assert validate_result(p,result) and not result.unplaced
    assert {r.sheet_number for r in result.placements}=={1,2}


def test_bounds_filter_matches_unfiltered_search_with_different_curve_allowances(monkeypatch):
    p=project([Part.create('A',box(0,0,12,8),quantity=40,curve_tolerance=.03),
               Part.create('B',box(0,0,9,7),quantity=40,curve_tolerance=.08)],
              [Sheet('s','Plate',250,250,stock=1)])
    indexed=refine(p)
    class Unfiltered:
        T=None
    monkeypatch.setattr(engine,'asarray',lambda rows:Unfiltered())
    brute=refine(p)
    assert indexed.placements==brute.placements and not indexed.unplaced
    assert validate_result(p,indexed)
    shapes=[(r,p.part(r.part_id),placed(p.part(r.part_id),r)) for r in indexed.placements]
    for i,(a,part,shape) in enumerate(shapes):
        edge=p.options.margin+p.options.kerf/2+part.geometry_error
        assert box(edge-1e-6,edge-1e-6,250-edge+1e-6,250-edge+1e-6).covers(shape)
        for b,other,g in shapes[i+1:]:
            assert shape.intersection(g).area<1e-6
            assert shape.distance(g)+1e-6>=3+part.geometry_error+other.geometry_error


def test_bounds_filter_keeps_the_material_hole_available_in_a_dense_layout():
    frame=Polygon(box(0,0,600,600).exterior,[box(30,30,570,570).exterior])
    p=project([Part.create('Frame',frame),Part.create('Insert',box(0,0,20,20),quantity=70)],
              [Sheet('s','Plate',610,610,stock=1)])
    result=refine(p)
    assert validate_result(p,result) and not result.unplaced
    host=next(placed(p.part(r.part_id),r) for r in result.placements if r.part_id==p.parts[0].id)
    hole=Polygon(host.interiors[0])
    for row in result.placements:
        if row.part_id==p.parts[1].id:
            g=placed(p.part(row.part_id),row)
            assert hole.covers(g) and host.distance(g)+1e-6>=3
