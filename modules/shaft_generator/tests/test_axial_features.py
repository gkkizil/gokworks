from copy import deepcopy
import pytest
from modules.shaft_generator.models import Project,Stage,Bore,CosmeticThread,Groove,Keyway,Chamfer,Fillet
from modules.shaft_generator.validation import validate
from modules.shaft_generator.geometry import operation_plan
from modules.shaft_generator.bridge import checked_payload
from modules.shaft_generator.controller import request
from modules.shaft_generator import storage


@pytest.mark.parametrize('condition,entry,depth,expected',[
    ('through_all','left',20,(0,190)),('through_all','right',20,(0,190)),
    ('blind','left',30,(0,30)),('blind','right',30,(160,190)),
])
def test_axial_hole_span_and_plan_are_in_metres(condition,entry,depth,expected):
    p=Project(bore=Bore(10,depth,condition,entry))
    assert not validate(p) and p.bore.interval(p.total_length)==expected
    plan=operation_plan(p)
    assert plan[len(p.stages)]==dict(kind='bore',name='IC_DELIK_01',sketch='IC_DELIK_01_ESKIZI',
        diameter_m=.01,start_m=expected[0]*.001,length_m=(expected[1]-expected[0])*.001)
    assert checked_payload(request(p))==p


@pytest.mark.parametrize('field,value',[
    ('diameter',0),('diameter',float('nan')),('diameter',float('inf')),('diameter',True),
    ('diameter','10'),('depth',0),('depth',float('nan')),('entry','top'),('end_condition','all'),
])
def test_bad_bore_inputs_cannot_reach_bridge(field,value):
    p=Project(bore=Bore());setattr(p.bore,field,value)
    assert validate(p)
    with pytest.raises(ValueError):request(p)


def test_bore_checks_only_stages_reached_and_does_not_turn_a_blind_hole_into_through():
    p=Project(stages=[Stage(60,40),Stage(20,40)],bore=Bore(40,20,'blind','left'))
    assert not validate(p)
    p.bore.entry='right';assert 'et kalınlığı' in '\n'.join(validate(p))
    p.bore=Bore(10,80,'blind','left');assert 'kör delik' in '\n'.join(validate(p))
    p.bore=Bore(20,20,'through_all');assert validate(p)


def test_blind_bore_must_not_break_out_at_a_smaller_shoulder_exactly_at_its_bottom():
    p=Project(stages=[Stage(60,40),Stage(20,40)],bore=Bore(40,40,'blind','left'))
    assert 'et kalınlığı' in '\n'.join(validate(p))
    p.bore.depth=39;assert not validate(p)


def test_concave_shoulder_treatment_adds_material_and_does_not_reduce_bore_wall():
    p=Project(stages=[Stage(30,40),Stage(45,40)],bore=Bore(27))
    p.operations=[Chamfer(p.stages[0].id,edge='right',distance=2)]
    assert not validate(p)
    p.operations[0].edge='left'
    assert 'iç delik ile operasyon' in '\n'.join(validate(p))


@pytest.mark.parametrize('operation',[
    lambda sid:Groove(sid,offset=10,width=2,depth=2),
    lambda sid:Keyway(sid,offset=5,length=20,width=8,depth=4),
    lambda sid:Chamfer(sid,edge='left',distance=2),
    lambda sid:Fillet(sid,edge='left',radius=2),
])
def test_channels_and_end_treatments_must_leave_wall_to_the_bore(operation):
    p=Project(stages=[Stage(30,80)],bore=Bore(27))
    p.operations=[operation(p.stages[0].id)]
    assert 'iç delik ile operasyon' in '\n'.join(validate(p))
    p.bore.diameter=16;assert not validate(p)


def test_blind_bore_does_not_falsely_clash_with_a_distant_channel():
    p=Project(stages=[Stage(30,80)],bore=Bore(27,10,'blind','right'))
    p.operations=[Groove(p.stages[0].id,offset=10,width=2,depth=2)]
    assert not validate(p)
    p.bore.entry='left';p.bore.depth=20
    assert 'iç delik ile operasyon' in '\n'.join(validate(p))


@pytest.mark.parametrize('edge,expected',[('left',(2,22)),('right',(59,79))])
def test_cosmetic_thread_starts_on_full_diameter_land_after_treatment(edge,expected):
    p=Project(stages=[Stage(30,80)],bore=Bore(10))
    sid=p.stages[0].id;t=CosmeticThread(sid,edge=edge,length=20,pitch=3.5)
    p.operations=[Chamfer(sid,edge='left',distance=2),Fillet(sid,edge='right'),t]
    assert p.thread_interval(t)==expected and not validate(p)
    assert operation_plan(p)[-1]['name']=='KOZMETIK_DIS_01'
    t.length=79;assert validate(p)


def test_cosmetic_thread_conflicts_and_no_edge_on_equal_diameter_stages():
    p=Project(stages=[Stage(30,80),Stage(30,80)])
    sid=p.stages[0].id;p.operations=[CosmeticThread(sid,edge='right')]
    assert 'dairesel kenar yok' in '\n'.join(validate(p))
    p.operations=[CosmeticThread(sid,length=20),Groove(sid,offset=10)]
    assert 'çakışıyor' in '\n'.join(validate(p))


def test_cosmetic_thread_intended_minor_diameter_must_leave_wall_to_reached_bore():
    p=Project(stages=[Stage(30,80)],bore=Bore(28))
    p.operations=[CosmeticThread(p.stages[0].id,pitch=1.5)]
    assert 'iç delik ile operasyon' in '\n'.join(validate(p))
    p.bore=Bore(28,20,'blind','right');assert not validate(p)


@pytest.mark.parametrize('field,value',[('pitch',0),('pitch',100),('pitch',float('nan')),('length',81),('edge','top')])
def test_invalid_cosmetic_dimensions_are_rejected(field,value):
    p=Project(stages=[Stage(30,80)]);t=CosmeticThread(p.stages[0].id);setattr(t,field,value);p.operations=[t]
    assert validate(p)


def test_v1_unchanged_and_v2_features_roundtrip_in_storage_and_bridge(tmp_path):
    p=Project();old=p.to_dict();assert old['version']==1 and 'bore' not in old
    assert Project.from_dict(old)==p
    p.bore=Bore(10,30,'blind','right');p.operations=[CosmeticThread(p.stages[0].id)]
    data=p.to_dict();assert data['version']==2 and data['bore']['entry']=='right'
    path=tmp_path/'hollow.gokshaft.json';storage.save(p,path)
    assert storage.load(path)==p and checked_payload(request(p))==p
    for mutation in (lambda d:d.update(version=1),lambda d:d['bore'].update(extra=42),lambda d:d['bore'].pop('depth')):
        bad=deepcopy(data);mutation(bad)
        with pytest.raises(ValueError):Project.from_dict(bad)
    p.bore=None;p.operations=[];assert p.to_dict()==old
