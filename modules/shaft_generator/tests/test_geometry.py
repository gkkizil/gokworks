import math
import pytest
from modules.shaft_generator.models import Project,Stage,Groove,Keyway,Chamfer,Fillet
from modules.shaft_generator.geometry import profile,treated_profile,check_profile,metres,radians,operation_plan


@pytest.mark.parametrize('stages',[[Stage(30,40)],[Stage(30,40),Stage(30,20)],[Stage(30,40),Stage(45,65),Stage(35,50),Stage(25,35)]])
def test_closed_profile_exact_dimensions_and_no_zero_shoulders(stages):
    p=Project(stages=stages);points=profile(p)
    assert points[0]==points[-1]==(0,0)
    assert max(x for x,y in points)==p.total_length
    assert max(y for x,y in points)==p.maximum_diameter/2
    assert all(a!=b for a,b in zip(points,points[1:]))
    assert metres(p.total_length)==pytest.approx(p.total_length/1000)
    assert radians(360)==pytest.approx(math.tau)


@pytest.mark.parametrize('points',[
    [(0,0),(1,1),(1,0)],[(0,0),(2,2),(0,2),(2,0),(0,0)],
    [(0,0),(2,0),(2,2),(1,0),(0,0)],[(0,0),(2,0),(2,0),(0,0)]])
def test_open_zero_length_and_self_intersecting_profiles_rejected(points):
    with pytest.raises(ValueError):check_profile(points)


def test_chamfer_and_fillet_are_true_size_and_profile_remains_closed():
    p=Project(stages=[Stage(30,40)]);s=p.stages[0]
    p.operations=[Chamfer(s.id,distance=2),Fillet(s.id,radius=3)]
    points=treated_profile(p)
    assert (0,13) in points and (2,15) in points
    assert (37,15) in points and (40,12) in points
    arc=points[points.index((37,15)):points.index((40,12))+1]
    assert all(math.dist((37,12),pt)==pytest.approx(3) for pt in arc)
    check_profile(points)


def test_plan_keeps_stage_ids_and_names_and_recomputes_offsets():
    p=Project();p.operations=[Groove(p.stages[1].id,offset=10)]
    plan=operation_plan(p);assert len(plan)==5
    assert plan[1]['start_m']==.04 and plan[-1]['name']=='SEGMAN_KANALI_01'
    p.stages[0].length=50
    assert operation_plan(p)[1]['start_m']==.05
    assert plan[1]['start_m']==.04  # Previous job payload is immutable data.


def test_combined_plan_treats_end_edges_before_channel_cuts_without_changing_operation_ids():
    p=Project(stages=[Stage(30,80)])
    sid=p.stages[0].id
    p.operations=[Keyway(sid,offset=10),Fillet(sid,edge='right'),
                  Groove(sid,offset=40),Chamfer(sid,edge='left')]
    plan=operation_plan(p)
    assert [row['kind'] for row in plan]==['revolve','chamfer','fillet','groove','keyway']
    assert [row['name'] for row in plan[1:]]==['PAH_01','RADYUS_01','SEGMAN_KANALI_01','KAMA_KANALI_01']
    assert {row['operation_id'] for row in plan[1:]}=={op.id for op in p.operations}


@pytest.mark.parametrize('constructor',[Chamfer,Fillet])
@pytest.mark.parametrize('edge',['left','right'])
def test_decimal_stage_boundaries_keep_edge_treatments_attached(constructor,edge):
    p=Project(stages=[Stage(30,.1),Stage(40,.2),Stage(50,.3),Stage(60,.4)])
    s=p.stages[-1]
    kwargs={'distance':.025} if constructor is Chamfer else {'radius':.025}
    p.operations=[constructor(s.id,edge=edge,**kwargs)]
    corner=(p.start(s.id) if edge=='left' else p.end(s.id),s.diameter/2)
    assert corner in profile(p) and corner not in treated_profile(p)
    assert p.boundaries[-1]==p.total_length
    check_profile(treated_profile(p))
