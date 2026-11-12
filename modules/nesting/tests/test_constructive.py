"""Constructive portfolio: physical improvements, exact safety and interruptions."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from threading import Event
from types import SimpleNamespace
import math
import time

import pytest
from shapely import affinity
from shapely.geometry import box, Polygon, MultiPolygon

from modules.nesting import constructive, engine, solver, sparrow
from modules.nesting.geometry import placed
from modules.nesting.layout_score import layout_score
from modules.nesting.materials import new_project
from modules.nesting.models import Part, Sheet, Placement, Result
from modules.nesting.search_budget import SearchBudget
from modules.nesting.validation import validate_result


def job(sizes=((5,2),(5,6),(4,5),(6,4),(7,7),(5,5))):
    p = new_project()
    p.parts = [Part.create(str(i),box(0,0,w,h)) for i,(w,h) in enumerate(sizes)]
    p.sheets = [Sheet('s','Plate',10,10,stock=10)]
    p.options.margin = p.options.gap = p.options.kerf = 0
    p.options.rotation = False
    return p


def baseline(p):
    now = time.monotonic()
    return engine.nest(p,budget=SearchBudget(now,now+5,now+5,1))


def test_maxrects_reaches_two_plate_area_bound_where_corner_seed_needs_three():
    p = job(); source = deepcopy(asdict(p)); before = baseline(p)
    result = constructive.nest(p,initial=before,deadline=time.monotonic()+2)
    assert layout_score(p,before)[1] == 3
    assert layout_score(p,result)[1] == math.ceil(sum(part.area for part in p.parts)/100) == 2
    assert validate_result(p,result) and asdict(p) == source
    assert {(r.part_id,r.instance) for r in result.placements} == {(r.part_id,r.instance) for r in before.placements}


def test_maxrects_slots_cover_free_cells_without_occupying_either_used_rectangle():
    used = [(2.,2.,6.,5.),(7.,4.,10.,9.)]
    free = [(0.,0.,10.,10.)]
    for rectangle in used:
        free = constructive._split(free,rectangle,lambda:None)
    assert len(free) == len(set(free))
    for i,a in enumerate(free):
        assert all(i == j or not (b[0]<=a[0] and b[1]<=a[1] and a[2]<=b[2] and a[3]<=b[3]) for j,b in enumerate(free))
        assert all(box(*a).intersection(box(*u)).area == 0 for u in used)
    for x in range(10):
        for y in range(10):
            occupied = any(a<x+.5<c and b<y+.5<d for a,b,c,d in used)
            assert any(a<=x+.5<=c and b<=y+.5<=d for a,b,c,d in free) != occupied


@pytest.mark.parametrize('locked', [False,True])
def test_only_real_allowed_angles_can_fit_a_narrow_stock(locked):
    p = job(((60,20),)); p.options.rotation = True
    p.parts[0].grain_locked = locked
    p.sheets[0].width,p.sheets[0].height = 30,70
    result = constructive.nest(p,deadline=time.monotonic()+1)
    assert validate_result(p,result,complete=False)
    assert len(result.placements) == (0 if locked else 1)
    if not locked: assert result.placements[0].angle in (90.,270.)


def test_continuous_mode_uses_geometry_alignment_without_rotating_the_source():
    p = job(((60,20),)); p.options.rotation = True; p.options.angles = None
    p.parts[0].geometry = Part.create('tilted',affinity.rotate(box(0,0,60,20),23,origin=(0,0))).geometry
    source = deepcopy(p.parts[0].geometry)
    p.sheets[0].width,p.sheets[0].height = 61,21
    result = constructive.nest(p,deadline=time.monotonic()+1)
    assert validate_result(p,result) and p.parts[0].geometry == source
    assert min(abs((result.placements[0].angle-a+180)%360-180) for a in (337,157)) < 1e-6


def test_mixed_stocks_error_allowances_and_disconnected_geometry_are_verified_independently():
    p = job(); p.options.gap = 2; p.options.kerf = .3; p.options.margin = 1
    p.parts = [Part.create('A',box(-4,-3,8,5),quantity=6,curve_tolerance=.03),
               Part.create('B',box(0,0,9,7),material='AISI 304',quantity=3,endpoint_error=.04),
               Part.create('C',MultiPolygon([box(0,0,3,5),box(6,0,9,5)]),thickness=3,quantity=2)]
    p.sheets = [Sheet('steel','Steel',50,50,stock=1),
                Sheet('stainless','Stainless',50,50,material='AISI 304',stock=1),
                Sheet('thick','Thick',50,50,thickness=3,stock=1)]
    source = deepcopy(asdict(p)); result = constructive.nest(p,deadline=time.monotonic()+2)
    assert validate_result(p,result) and asdict(p) == source
    assert Counter(r.part_id for r in result.placements) == {part.id:part.quantity for part in p.parts}
    for a in result.placements:
        part = p.part(a.part_id); shape = placed(part,a)
        margin = 1+.15+part.geometry_error
        assert box(margin-1e-6,margin-1e-6,50-margin+1e-6,50-margin+1e-6).covers(shape)
        for b in result.placements:
            if a is b or (a.sheet_id,a.sheet_number) != (b.sheet_id,b.sheet_number): continue
            other = p.part(b.part_id); target = placed(other,b)
            assert shape.intersection(target).area < 1e-6
            assert shape.distance(target)+1e-6 >= 2+part.geometry_error+other.geometry_error


def test_conservative_boxes_cannot_replace_a_better_hole_nested_incumbent():
    p = job(); p.sheets[0].width = p.sheets[0].height = 100; p.sheets[0].stock = 1
    p.parts = [Part.create('Frame',Polygon(box(0,0,100,100).exterior,[box(10,10,90,90).exterior])),
               Part.create('Insert',box(0,0,20,20),quantity=3)]
    poses = [Placement(p.parts[0].id,1,'s',1,0,0,0)]+[
        Placement(p.parts[1].id,i,'s',1,10+20*(i-1),10,0) for i in range(1,4)]
    initial = Result(p.fingerprint(),poses,[],'fixture','1',0,1,'')
    before = deepcopy(asdict(initial))
    result = constructive.nest(p,initial=initial,deadline=time.monotonic()+1)
    assert validate_result(p,result) and result.placements == initial.placements
    assert asdict(initial) == before


@pytest.mark.parametrize('interruption', ['cancel','timeout'])
def test_no_proposals_after_interruption_and_complete_seed_is_retained(monkeypatch,interruption):
    p = job(); initial = baseline(p); before = deepcopy(asdict(initial)); stop = Event()
    deadline = time.monotonic()+1
    if interruption == 'cancel': stop.set()
    else: deadline -= 2
    def forbidden(*args): raise AssertionError('No new orientation work after interruption')
    monkeypatch.setattr(constructive,'search_angles',forbidden)
    result = constructive.nest(p,initial=initial,deadline=deadline,stop=stop)
    assert validate_result(p,result) and result.placements == initial.placements
    assert asdict(initial) == before
    assert result.stopped == (interruption == 'cancel')
    assert result.timed_out == (interruption == 'timeout')


def test_cancelled_split_retains_only_completed_instances(monkeypatch):
    p = job(((2,2),)*4); stop = Event(); split = constructive._split
    def cancel(free,used,checkpoint):
        result = split(free,used,checkpoint); stop.set(); return result
    monkeypatch.setattr(constructive,'_split',cancel)
    result = constructive.nest(p,deadline=time.monotonic()+1,stop=stop)
    assert result.stopped and len(result.placements) == 1 and len(result.unplaced) == 3
    assert validate_result(p,result,complete=False)


def test_large_repeated_demand_obeys_a_single_deadline_without_losing_counts(monkeypatch):
    p = job(((2,2),)); p.parts[0].quantity = 10000; clock = [0.]
    def tick():
        clock[0] += .001; return clock[0]
    monkeypatch.setattr(constructive,'time',SimpleNamespace(monotonic=tick))
    result = constructive.nest(p,deadline=.03)
    assert result.timed_out and result.iterations == 1 and clock[0] < .05
    assert len(result.placements)+len(result.unplaced) == 10000
    assert validate_result(p,result,complete=False)


def test_integrated_pipeline_retains_the_best_constructive_contender(monkeypatch):
    p = job(); p.options.seconds = 4; initial = baseline(p); seen = []
    monkeypatch.setattr(sparrow,'nest',lambda *args,**kwargs:deepcopy(initial))
    def failed_improvement(project,**kwargs):
        seen.append(layout_score(project,kwargs['initial'])[1])
        return deepcopy(initial)
    monkeypatch.setattr(engine,'nest',failed_improvement)
    result = solver.nest(p)
    assert seen == [2] and validate_result(p,result) and layout_score(p,result)[1] == 2
