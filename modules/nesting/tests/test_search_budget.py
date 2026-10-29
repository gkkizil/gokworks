"""Automatic scheduling with exact geometry, fake clocks and legacy projects."""

from dataclasses import replace
import json
from threading import Event
from types import SimpleNamespace

import pytest
from shapely import union_all
from shapely.geometry import Point,box,Polygon,MultiPolygon

from modules.nesting import engine
from modules.nesting.materials import new_project
from modules.nesting.models import Part,Sheet,uid
from modules.nesting.search_budget import for_project,meaningful_improvement,uniform_stock_floor
from modules.nesting.storage import save_project,load_project
from modules.nesting.validation import validate_result


def project(quantity=3):
    p=new_project();p.parts=[Part.create('Rectangle',box(0,0,20,10),quantity=quantity)]
    p.sheets[0].width=p.sheets[0].height=100
    return p


def test_workload_accounts_for_instances_contours_and_allowed_rotations():
    p=project();small=for_project(p,0)
    p.parts[0].quantity=30;repeated=for_project(p,0)
    assert repeated.deadline>small.deadline
    p.parts[0]=Part.create('Curved',Point(30,30).buffer(20,quad_segs=64),quantity=30)
    curved=for_project(p,0)
    assert curved.deadline>repeated.deadline
    p.options.angles=list(range(360));many_angles=for_project(p,0)
    assert many_angles.deadline>curved.deadline
    p.parts[0].grain_locked=True
    assert for_project(p,0).deadline<many_angles.deadline
    p.parts[0].quantity=10000
    assert for_project(p,0).deadline<=for_project(p,0).hard_deadline==45


@pytest.mark.parametrize('quality,attempts,ceiling',[('Hızlı',4,15),('Dengeli',13,45),('Yüksek',41,90)])
def test_quality_scales_the_automatic_allowance_with_a_finite_cap(quality,attempts,ceiling):
    p=project();p.options.quality=quality
    budget=for_project(p,10)
    assert budget.automatic and 10<budget.deadline<=budget.hard_deadline==10+ceiling
    assert budget.max_attempts==attempts


def test_useful_work_extends_measured_allowance_and_progress_never_goes_backwards():
    budget=for_project(project(),0)
    initial=budget.deadline
    previous=budget.percent(initial*.9)
    assert budget.continue_after_trial(initial*.9,initial*.9,True)
    assert budget.deadline>initial and budget.percent(initial*.95)>=previous
    # Substantial improvement resets the plateau counter instead of stopping.
    assert budget.continue_after_trial(initial+1,1,False)
    assert budget.continue_after_trial(initial+2,1,False)
    assert budget.continue_after_trial(initial+3,1,True) and budget.stale==0
    assert not budget.continue_after_trial(budget.hard_deadline,1,True)
    assert budget.deadline<=budget.hard_deadline


def test_soft_estimate_can_extend_to_finish_bootstrap_but_hard_limit_cannot():
    budget=for_project(project(),0);initial=budget.deadline
    assert budget.allow_work(initial+.1) and budget.deadline>initial
    budget.completed=budget.minimum_attempts;budget.stale=1
    assert not budget.allow_work(budget.deadline+.1)
    budget.stale=0
    assert budget.allow_work(budget.deadline+.1)
    assert not budget.allow_work(budget.hard_deadline)


@pytest.mark.parametrize('shape',[
    Polygon([(0,0),(100,0),(100,20),(20,20),(20,80),(100,80),(100,100),(0,100)]),
    box(0,0,200,200).difference(Point(100,100).buffer(70,quad_segs=64)),
    MultiPolygon([box(0,0,40,40).difference(box(10,10,30,30)),box(80,0,90,20)]),
])
def test_indexed_convex_decomposition_retains_the_exact_material_and_holes(shape):
    pieces=engine.convex_parts(shape)
    assert union_all(pieces).equals(shape)
    assert sum(p.area for p in pieces)==pytest.approx(shape.area)
    assert all(p.equals(p.convex_hull) for p in pieces)
    for i,a in enumerate(pieces):
        assert all(a.intersection(b).area<1e-8 for b in pieces[i+1:])


def test_dense_rotation_baseline_falls_back_to_a_necessary_non_coarse_angle(monkeypatch):
    from shapely import affinity
    p=project(1);part=p.parts[0];part.geometry=Part.create('Bar',box(0,0,60,5)).geometry
    target=affinity.rotate(part.polygon,25,origin=(0,0));x0,y0,x1,y1=target.bounds
    p.sheets[0].width=x1-x0;p.sheets[0].height=y1-y0
    p.options.margin=p.options.gap=p.options.kerf=0;p.options.angles=list(range(360))
    r=engine.nest(p)
    assert validate_result(p,r) and r.placements[0].angle in (25,155,205,335)


def test_forty_one_instances_complete_before_detailed_dense_angle_optimization(monkeypatch):
    p=project();p.options.quality='Yüksek';p.options.angles=list(range(360))
    quantities=(4,2,12,15,3,3,1,1)
    p.parts=[Part.create(f'Profile-{i}',box(0,0,35+i*2,25+i),quantity=q)
             for i,q in enumerate(quantities)]
    p.sheets[0].width=250;p.sheets[0].height=300
    clock=[0.];monkeypatch.setattr(engine,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def too_expensive(*args):
        clock[0]=1000.;args[1]()
    monkeypatch.setattr(engine,'convex_parts',too_expensive)
    r=engine.nest(p)
    assert r.timed_out and not r.unplaced and len(r.placements)==41
    assert validate_result(p,r)


def test_real_repeated_layout_stops_after_reaching_the_uniform_stock_bound():
    p=project();r=engine.nest(p)
    assert validate_result(p,r) and len(r.placements)==3
    assert r.iterations==2 and not r.timed_out and not r.stopped
    assert p.options.seconds is None


def test_stock_bound_does_not_certify_mixed_size_or_ambiguous_groups():
    p=project();assert uniform_stock_floor(p)==(1,10000.)
    p.sheets.append(Sheet(uid(),'Smaller',50,100))
    assert uniform_stock_floor(p) is None
    p.sheets.pop();p.parts.append(Part.create('Nearly equal',box(0,0,10,10),thickness=2+1e-8))
    assert uniform_stock_floor(p) is None


def test_smallest_stock_is_still_tried_before_early_completion():
    p=project(1);p.sheets.append(Sheet(uid(),'Small',50,50))
    r=engine.nest(p)
    assert validate_result(p,r) and r.placements[0].sheet_id==p.sheets[1].id


def test_dense_refinement_finishes_an_improved_complete_interlocking_plan():
    from .test_nesting import concave_project
    p=concave_project();p.options.seconds=None;p.options.rotation=True
    p.options.angles=list(range(360))
    r=engine.nest(p)
    assert validate_result(p,r) and len(r.placements)==2
    assert len({x.sheet_number for x in r.placements})==1


def test_auto_nfp_timeout_retains_the_completed_valid_baseline(monkeypatch):
    from .test_nesting import concave_project
    p=concave_project();p.options.seconds=None;clock=[0.]
    monkeypatch.setattr(engine,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def expensive(*args):
        clock[0]=1000.;args[1]()
    monkeypatch.setattr(engine,'convex_parts',expensive)
    r=engine.nest(p)
    assert len(r.placements)==2 and not r.unplaced and r.timed_out and not r.stopped
    assert validate_result(p,r)


@pytest.mark.parametrize('needs_precise_fit',[False,True])
def test_slow_refinement_yields_then_retries_without_losing_parts(monkeypatch,needs_precise_fit):
    from .test_nesting import concave_project
    p=concave_project() if needs_precise_fit else project()
    p.options.seconds=None;clock=[0.];calls=[];original=engine.minkowski
    monkeypatch.setattr(engine,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def slow_first(a,b,guard,**kwargs):
        calls.append(True)
        if len(calls)==1:clock[0]+=1.
        guard()
        return original(a,b,guard,**kwargs)
    monkeypatch.setattr(engine,'minkowski',slow_first)
    r=engine.nest(p)
    assert calls and not r.timed_out and not r.stopped and not r.unplaced
    assert r.iterations==(3 if needs_precise_fit else 2)
    assert len({(x.sheet_id,x.sheet_number) for x in r.placements})==1
    assert validate_result(p,r)


def test_automatic_search_still_obeys_cancellation_and_preserves_instance_counts():
    p=project();stop=Event();stop.set();r=engine.nest(p,stop=stop)
    assert r.stopped and not r.timed_out and len(r.unplaced)==3 and not r.placements
    assert validate_result(p,r,complete=False)


def test_tiny_height_changes_do_not_reset_convergence_but_better_counts_do():
    previous=(0,2,10000,100.)
    assert not meaningful_improvement((0,2,10000,99.999999999),previous)
    assert meaningful_improvement((0,2,10000,90.),previous)
    assert meaningful_improvement((0,1,20000,200.),previous)
    assert meaningful_improvement((0,3,30000,300.),(1,1,10000,100.))


@pytest.mark.parametrize('seconds',[None,7.])
def test_automatic_and_legacy_numeric_projects_round_trip_without_losing_results(tmp_path,seconds):
    p=project();p.options.seconds=seconds;r=engine.nest(p)
    if seconds is not None:r=replace(r,engine_version='1.3')
    path=tmp_path/'project.goknest.json';save_project(p,path,r)
    payload=json.loads(path.read_text())
    assert payload['version']==1 and payload['project']['options']['seconds']==seconds
    loaded,result=load_project(path)
    assert loaded.options.seconds==seconds and result==r and validate_result(loaded,result)
    if seconds is not None:
        budget=for_project(loaded,0)
        assert not budget.automatic and budget.deadline==budget.hard_deadline==seconds


@pytest.mark.parametrize('seconds',[0,-1,601,float('nan'),float('inf')])
def test_invalid_legacy_numeric_deadlines_are_still_rejected(seconds):
    p=project();p.options.seconds=seconds
    with pytest.raises(ValueError):p.validate()
