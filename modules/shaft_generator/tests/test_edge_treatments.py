"""Bulk UI intent reaches ordinary, independently validated native operations."""
from copy import deepcopy

import pytest

from modules.shaft_generator.edge_treatments import circular_edges,plan_treatments
from modules.shaft_generator.models import (Project,Stage,Chamfer,Fillet,Groove,Keyway,Bore,CosmeticThread)
from modules.shaft_generator.geometry import operation_plan,check_profile,treated_profile
from modules.shaft_generator.validation import validate


@pytest.mark.parametrize('kind', ['chamfer','fillet'])
def test_default_shaft_has_eight_distinct_corners_and_unchanged_transport(kind):
    p=Project();before=p.to_dict();batch=plan_treatments(p,kind,1.)
    assert p.to_dict()==before and batch.edge_count==8 and batch.added==8
    assert batch.updated==batch.preserved==batch.straight_joints==0
    assert len(batch.project.operations)==8 and not validate(batch.project)
    assert {(op.stage_id,op.edge) for op in batch.project.operations}=={(stage.id,side) for stage in p.stages for side in ('left','right')}
    plan=operation_plan(batch.project)
    assert [row['kind'] for row in plan]==['revolve']*4+[kind]*8
    assert {row['operation_id'] for row in plan[4:]}=={op.id for op in batch.project.operations}
    assert batch.project.to_dict()['version']==1
    check_profile(treated_profile(batch.project))


@pytest.mark.parametrize('kind',['chamfer','fillet'])
def test_equal_diameter_stages_skip_both_nonexistent_shoulder_edges(kind):
    p=Project(stages=[Stage(30,40),Stage(30,20),Stage(45,60)])
    a,b,c=p.stages
    batch=plan_treatments(p,kind,.5)
    assert batch.edge_count==4 and batch.straight_joints==1
    assert {(op.stage_id,op.edge) for op in batch.project.operations}=={(a.id,'left'),(b.id,'right'),(c.id,'left'),(c.id,'right')}
    assert len({(edge.position,edge.radius) for edge in circular_edges(p)})==4
    assert plan_treatments(Project(stages=[Stage(30,40),Stage(30,20)]),kind,1.).edge_count==2


def test_preserve_is_default_idempotent_and_explicit_replace_keeps_operation_ids():
    p=Project();stage=p.stages[0]
    existing=Fillet(stage.id,edge='left',radius=.8);p.operations=[existing]
    batch=plan_treatments(p,'chamfer',1.)
    assert batch.preserved==1 and batch.added==7 and batch.updated==0
    old=next(o for o in batch.project.operations if o.id==existing.id)
    assert isinstance(old,Fillet) and old.radius==.8
    repeat=plan_treatments(batch.project,'chamfer',1.)
    assert repeat.preserved==8 and repeat.added==repeat.updated==0
    assert repeat.project.to_dict()==batch.project.to_dict()
    updated=plan_treatments(batch.project,'fillet',.5,replace_existing=True)
    assert updated.updated==8 and updated.added==updated.preserved==0
    assert {o.id for o in updated.project.operations}=={o.id for o in batch.project.operations}
    assert all(isinstance(o,Fillet) and o.radius==.5 for o in updated.project.operations)


def test_channels_bore_and_cosmetic_thread_survive_in_the_same_valid_project():
    p=Project(bore=Bore(diameter=10));a,b,c,d=p.stages
    p.operations=[Groove(a.id,offset=5),Keyway(b.id,offset=5,length=30,width=14,depth=5.5),
                  CosmeticThread(c.id,edge='left',length=15,pitch=1.5)]
    before=deepcopy(p.to_dict());batch=plan_treatments(p,'chamfer',.5)
    assert p.to_dict()==before and batch.project.bore==p.bore
    assert batch.project.operations[:3]==p.operations and batch.edge_count==8
    assert [op.kind for op in batch.project.operations[:3]]==['groove','keyway','cosmetic_thread']
    assert batch.project.to_dict()['version']==2 and not validate(batch.project)


@pytest.mark.parametrize('kind',['chamfer','fillet'])
def test_conflicting_channel_or_too_large_size_changes_nothing(kind):
    p=Project();p.operations=[Groove(p.stages[0].id,offset=0)]
    before=p.to_dict()
    with pytest.raises(ValueError,match='çakış'):plan_treatments(p,kind,1.)
    assert p.to_dict()==before
    p=Project(stages=[Stage(30,40),Stage(32,40)]);before=p.to_dict()
    with pytest.raises(ValueError,match='omuz'):plan_treatments(p,kind,.75)
    assert p.to_dict()==before


@pytest.mark.parametrize('size',[0,-1,float('nan'),float('inf'),'1',True])
def test_invalid_size_does_not_enter_the_native_plan(size):
    p=Project();before=p.to_dict()
    with pytest.raises(ValueError):plan_treatments(p,'chamfer',size)
    assert p.to_dict()==before


def test_existing_invalid_edge_can_be_repaired_only_when_replacement_is_explicit():
    p=Project();p.operations=[Chamfer(p.stages[0].id,distance=20)]
    before=p.to_dict()
    with pytest.raises(ValueError):plan_treatments(p,'fillet',.5)
    assert p.to_dict()==before
    assert not validate(plan_treatments(p,'fillet',.5,replace_existing=True).project)


def test_limit_200_is_preserved_with_existing_channels_and_single_stage_still_has_two_ends():
    p=Project(stages=[Stage(30+(i%2)*20,40) for i in range(100)])
    p.operations=[Groove(p.stages[0].id,offset=5)]
    before=p.to_dict()
    with pytest.raises(ValueError,match='200 operasyon'):plan_treatments(p,'chamfer',.5)
    assert p.to_dict()==before
    single=plan_treatments(Project(stages=[Stage(30,40)]),'fillet',1.)
    assert single.edge_count==2 and not validate(single.project)
