from dataclasses import replace
from threading import Event

import pytest
from modules.smart_splitting.models import SplitSettings, PROFILES
from modules.smart_splitting.optimizer import optimize, metrics
from modules.nesting.validation import validate_result
from .test_geometry import circle_dxf
from modules.smart_splitting.analysis import load_parts


@pytest.mark.parametrize('count,bolts',[(4,False),(6,True)])
def test_real_nesting_same_settings_baseline_vs_candidates(tmp_path,count,bolts):
    p=load_parts(circle_dxf(tmp_path/'D1800.dxf',radius=900,bolts=bolts),tolerance=.2)[0]
    settings=SplitSettings(count=count,sheet_width=1500,sheet_height=3000,hole_clearance=5 if bolts else 0,profile='Hızlı')
    result=optimize(p,settings)
    assert validate_result(result.project,result.nesting)
    assert len(result.nesting.placements)==count and not result.nesting.unplaced
    assert len(result.solution.segments)==count
    assert len(result.candidates)>=2
    feasible=[r for r in result.candidates if r.status=='Geçerli']
    assert feasible
    assert metrics(result.project,result.nesting)[0]==min(r.sheets for r in feasible)
    if feasible[0].label=='Eşit açısal başlangıç':
        assert metrics(result.project,result.nesting)[0]<=feasible[0].sheets


def test_no_feasible_solution_and_cancel_never_produce_partial_success(tmp_path):
    p=load_parts(circle_dxf(tmp_path/'A.dxf',radius=100),tolerance=.2)[0]
    with pytest.raises(ValueError,match='Uygulanabilir'): optimize(p,SplitSettings(count=4,sheet_width=10,sheet_height=10))
    stop=Event(); stop.set()
    with pytest.raises(InterruptedError): optimize(p,SplitSettings(),stop=stop)


def test_profile_budgets_are_explicit_and_input_settings_do_not_mutate(tmp_path):
    assert PROFILES=={'Hızlı':(3,2.),'Dengeli':(7,3.),'Detaylı':(13,5.)}
    p=load_parts(circle_dxf(tmp_path/'A.dxf',radius=100),tolerance=.2)[0]
    settings=SplitSettings(count=2,quantity=2)
    result=optimize(p,settings)
    assert settings==replace(settings) and result.solution.settings.count==2
    assert sum(p.quantity for p in result.project.parts)==4


def test_cancel_after_baseline_keeps_only_a_verified_complete_plan(tmp_path):
    part=load_parts(circle_dxf(tmp_path/'A.dxf',radius=100),tolerance=.2)[0]
    stop=Event()
    def progress(index,total,label):
        if index==1: stop.set()
    result=optimize(part,SplitSettings(count=4),stop=stop,progress=progress)
    assert result.stopped and len(result.nesting.placements)==4
    assert validate_result(result.project,result.nesting)


def test_one_kernel_failure_is_reported_and_never_replaces_a_valid_candidate(tmp_path,monkeypatch):
    from shapely.errors import GEOSException
    import modules.smart_splitting.optimizer as engine
    real=engine.nest; calls=[]
    def one_failure(project,**kwargs):
        calls.append(1)
        if len(calls)==1: raise GEOSException('TopologyException: controlled candidate failure')
        return real(project,**kwargs)
    monkeypatch.setattr(engine,'nest',one_failure)
    part=load_parts(circle_dxf(tmp_path/'A.dxf',radius=100),tolerance=.2)[0]
    result=engine.optimize(part,SplitSettings(count=4))
    assert 'TopologyException' in result.candidates[0].status
    assert result.best_label!='Eşit açısal başlangıç'
    assert validate_result(result.project,result.nesting)
