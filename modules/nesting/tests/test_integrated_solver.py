"""Sparrow is the primary seed; actual NFP refinement improves that same plan."""
from copy import deepcopy
from dataclasses import asdict
from threading import Event
import time

import pytest
from shapely.geometry import box, MultiPolygon, Polygon

from modules.nesting import engine, sparrow, solver
from modules.nesting.layout_score import layout_score
from modules.nesting.models import Part, Placement, Result
from modules.nesting.search_budget import SearchBudget
from modules.nesting.storage import save_project, load_project
from modules.nesting.validation import validate_result
from .test_hole_nesting import frame, setup


def project():
    p=setup([Part.create('Frame',frame()),Part.create('Insert',box(0,0,25,25),quantity=4)])
    p.options.seconds=6
    return p


def one_pass(seconds=2):
    start=time.monotonic()
    return SearchBudget(start,start+seconds,start+seconds,1)


def test_real_sparrow_seed_is_improved_in_place_using_holes_and_plate_evacuation():
    p=project(); source=deepcopy(asdict(p))
    seed=sparrow.nest(p); before=deepcopy(asdict(seed))
    assert not seed.unplaced and len({x.sheet_number for x in seed.placements})==2
    result=engine.nest(p,initial=seed,budget=one_pass())
    assert result.iterations==1 and validate_result(p,result)
    assert len({x.sheet_number for x in result.placements})==1
    host_before=next(x for x in seed.placements if x.part_id==p.parts[0].id)
    host_after=next(x for x in result.placements if x.part_id==p.parts[0].id)
    assert (host_before.part_id,host_before.instance)==(host_after.part_id,host_after.instance)
    assert layout_score(p,result)<layout_score(p,seed)
    assert asdict(p)==source and asdict(seed)==before


def test_partial_seed_is_completed_without_opening_another_sheet():
    p=project();p.sheets[0].stock=1
    seed=sparrow.nest(p)
    assert seed.unplaced and len(seed.placements)==1
    result=engine.nest(p,initial=seed,budget=one_pass())
    assert validate_result(p,result) and len(result.placements)==5
    assert {(x.sheet_id,x.sheet_number) for x in result.placements}=={(p.sheets[0].id,1)}


@pytest.mark.parametrize('legacy_engine',['GOKWORKS NFP','Sparrow','Sparrow + GOKWORKS'])
def test_default_pipeline_uses_sparrow_for_all_legacy_metadata_and_never_regresses(monkeypatch,legacy_engine):
    p=project();p.options.engine=legacy_engine
    real=sparrow.nest;seeds=[];reports=[]
    def record(*args,**kwargs):
        seed=real(*args,**kwargs);seeds.append(deepcopy(seed));return seed
    monkeypatch.setattr(sparrow,'nest',record)
    result=solver.nest(p,progress=lambda *row:reports.append(row))
    assert len(seeds)==1 and seeds[0].iterations>0
    assert result.engine=='Sparrow + GOKWORKS' and validate_result(p,result)
    assert layout_score(p,result)<=layout_score(p,seeds[0])
    assert len({x.sheet_number for x in result.placements})==1
    assert reports[-1][0]==100


def test_disconnected_geometry_is_refined_exactly_without_native_convex_hull():
    geometry=MultiPolygon([box(0,0,10,10),box(20,0,30,10)])
    p=setup([Part.create('Grouped',geometry,quantity=2)]);p.options.seconds=3
    before=deepcopy(p.parts[0].geometry)
    result=solver.nest(p)
    assert validate_result(p,result) and len(result.placements)==2
    assert p.parts[0].geometry==before and 'Sparrow denemeleri 0' in result.engine_version


def test_acute_clearance_footprint_uses_exact_contour_refinement_without_native_panic():
    p=setup([Part.create('Acute',Polygon([(0,0),(1,50),(0,100)]))])
    p.options.rotation=False;p.options.seconds=3;p.sheets[0].stock=1
    result=solver.nest(p)
    assert validate_result(p,result) and len(result.placements)==1
    assert p.parts[0].area==50


@pytest.mark.parametrize('interruption',['timeout','cancel'])
def test_refinement_interruption_retains_every_seed_instance(interruption):
    p=project();seed=sparrow.nest(p);before=deepcopy(asdict(seed))
    stop=Event();budget=one_pass()
    if interruption=='cancel':stop.set()
    else:budget.deadline=budget.hard_deadline=time.monotonic()-1
    result=engine.nest(p,initial=seed,budget=budget,stop=stop)
    assert validate_result(p,result) and layout_score(p,result)==layout_score(p,seed)
    assert len(result.placements)==len(seed.placements) and asdict(seed)==before
    assert result.stopped if interruption=='cancel' else result.timed_out


def test_failed_plate_evacuation_is_transactional():
    p=setup([Part.create('Frame',frame()),Part.create('Small',box(0,0,25,50)),
             Part.create('Long',box(0,0,80,15))]);p.options.rotation=False
    seed=Result(p.fingerprint(),[Placement(p.parts[i].id,1,p.sheets[0].id,number,x,y,0)
        for i,number,x,y in ((0,1,5,5),(1,2,5,5),(2,2,5,65))],[],
        'fixture','1',0,1,'2026-11-09')
    assert validate_result(p,seed)
    result=engine.nest(p,initial=seed,budget=one_pass())
    assert validate_result(p,result) and len(result.placements)==3
    assert len({x.sheet_number for x in result.placements})==2


def test_pre_cancel_starts_neither_native_nor_refinement(monkeypatch):
    p=project();stop=Event();stop.set()
    def forbidden(*args,**kwargs):raise AssertionError('Cancelled work must not start')
    monkeypatch.setattr(sparrow,'nest',forbidden);monkeypatch.setattr(engine,'nest',forbidden)
    result=solver.nest(p,stop=stop)
    assert result.stopped and result.iterations==0 and validate_result(p,result,complete=False)


def test_native_failure_is_explicit_and_not_hidden_by_refinement(monkeypatch):
    p=project()
    def failed(*args,**kwargs):raise ValueError('controlled native failure')
    def forbidden(*args,**kwargs):raise AssertionError('Must not hide native failure')
    monkeypatch.setattr(sparrow,'nest',failed);monkeypatch.setattr(engine,'nest',forbidden)
    with pytest.raises(ValueError,match='native failure'):solver.nest(p)


def test_integrated_result_saves_and_loads_with_its_provenance(tmp_path):
    p=project();result=solver.nest(p);path=tmp_path/'integrated.goknest.json'
    save_project(p,path,result);loaded,saved=load_project(path)
    assert loaded.options.engine=='Sparrow + GOKWORKS'
    assert saved==result and validate_result(loaded,saved)
    assert 'Sparrow 0.1.0' in saved.engine_version and 'GOKWORKS NFP 1.5' in saved.engine_version
