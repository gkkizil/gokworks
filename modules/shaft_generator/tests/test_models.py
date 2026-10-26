from copy import deepcopy
import json
import math

import pytest
from modules.shaft_generator.models import Project, Stage, Groove, Keyway, Chamfer, Fillet
from modules.shaft_generator.validation import validate, require_valid
from modules.shaft_generator import storage


def test_stage_edit_copy_reorder_delete_retains_targets_and_total():
    p=Project(); assert p.total_length==190
    target=p.stages[1].id;op=Groove(target);p.operations.append(op)
    p.move_stage(target,-1);assert p.stages[0].id==target and p.start(target)==0
    p.stage(target).length=70;p.stage(target).diameter=48;assert p.total_length==195
    clone=p.add_stage(target,copy=True);assert clone!=target and p.stage(clone).diameter==48
    assert p.total_length==265 and p.operations[0].stage_id==target
    p.remove_stage(target);assert p.total_length==195 and not p.operations
    assert not validate(p)


def test_single_stage_and_last_stage_cannot_be_deleted():
    p=Project(stages=[Stage(20,50)]);assert p.total_length==50 and not validate(p)
    with pytest.raises(ValueError,match='En az'):p.remove_stage(p.stages[0].id)


@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf'),float('-inf'),'30',True,None,1e7])
@pytest.mark.parametrize('field',['length','diameter'])
def test_bad_dimensions_never_allow_a_plan(field,value):
    p=Project();setattr(p.stages[2],field,value)
    assert any('3. kademe' in e for e in validate(p))
    with pytest.raises(ValueError):require_valid(p)


def test_operation_geometry_and_supported_limits():
    p=Project();s=p.stages[0]
    for op,word in [(Groove(s.id,offset=39,width=2),'sınır'),(Groove(s.id,depth=16),'et'),
                    (Keyway(s.id,width=29,depth=1),'taban'),(Keyway(s.id,angle=90),'0°'),
                    (Chamfer(s.id,angle=30),'45°'),(Fillet(s.id,radius=30),'büyük')]:
        p.operations=[op];assert word in '\n'.join(validate(p))
    p.operations=[Groove(s.id,offset=8,width=2),Keyway(s.id,offset=15,length=20,width=8,depth=3),Chamfer(s.id)]
    assert not validate(p)


def test_overlap_boundary_contact_and_stale_stage_checks():
    p=Project();sid=p.stages[0].id
    p.operations=[Groove(sid,offset=8,width=2),Groove(sid,offset=9,width=2)]
    assert 'çakış' in '\n'.join(validate(p))
    p.operations[1].offset=10;assert not validate(p)
    p.operations.append(Groove('missing'));assert 'bulunamadı' in '\n'.join(validate(p))


@pytest.mark.parametrize('length',[4,8,8.000001])
def test_rounded_keyway_rejects_degenerate_or_short_overall_length(length):
    p=Project();p.operations=[Keyway(p.stages[0].id,length=length,width=8)]
    assert 'toplam boyu genişliğinden' in '\n'.join(validate(p))


def test_rounded_keyway_keeps_v1_fields_and_overall_bounds():
    p=Project();p.operations=[Keyway(p.stages[0].id,offset=20,length=20,width=8)]
    assert not validate(p)
    assert Project.from_dict(p.to_dict())==p
    p.operations[0].offset+=.1
    assert 'sınır' in '\n'.join(validate(p))


def test_equal_diameter_shoulder_has_no_edge_and_ends_cannot_overlap():
    p=Project(stages=[Stage(30,10),Stage(30,10)])
    p.operations=[Fillet(p.stages[0].id)];assert validate(p)
    p=Project(stages=[Stage(30,10)])
    p.operations=[Chamfer(p.stages[0].id,distance=6),Fillet(p.stages[0].id,radius=6)]
    assert 'çakış' in '\n'.join(validate(p))


def test_shoulder_treatment_checks_neighbor_operations():
    p=Project();a,b=p.stages[:2]
    p.operations=[Fillet(b.id,edge='left',radius=1),Groove(a.id,offset=38,width=2)]
    assert 'çakış' in '\n'.join(validate(p))


def test_round_trip_preserves_all_operation_types_and_exclusive_save(tmp_path):
    p=Project();s=p.stages[1].id
    p.operations=[Groove(s,offset=8),Keyway(s,offset=20),Chamfer(p.stages[0].id),Fillet(p.stages[-1].id)]
    path=tmp_path/'Mil Türkçe.gokshaft.json';storage.save(p,path)
    assert storage.load(path)==p
    content=path.read_bytes();p.name='MIL_002'
    with pytest.raises(FileExistsError):storage.save(p,path)
    assert path.read_bytes()==content
    storage.save(p,path,overwrite=True);assert storage.load(path).name=='MIL_002'


@pytest.mark.parametrize('mutation',[
    lambda d:d.update(version=2),lambda d:d.update(units='m'),lambda d:d.update(name=42),
    lambda d:d['stages'][0].pop('length'),lambda d:d['stages'][0].update(diameter=float('inf')),
    lambda d:d.update(future='unknown'),lambda d:d['operations'][0].update(kind='thread'),
    lambda d:d['operations'][0].pop('depth'),lambda d:d['stages'][0].update(id=d['stages'][1]['id']),
])
def test_invalid_or_future_project_is_rejected_without_modifying_existing(mutation,tmp_path):
    p=Project();p.operations=[Groove(p.stages[0].id)]
    original=deepcopy(p);data=p.to_dict();mutation(data)
    path=tmp_path/'bad.json';path.write_text(json.dumps(data))
    with pytest.raises(ValueError):storage.load(path)
    assert p==original


def test_duplicate_json_fields_and_nonfinite_literal_are_rejected(tmp_path):
    path=tmp_path/'bad.json'
    for value in ('{"version":1,"version":2}','{"length":NaN}'):
        path.write_text(value)
        with pytest.raises(ValueError):storage.load(path)


def test_confirmed_overwrite_refuses_target_changed_after_confirmation(tmp_path):
    path=tmp_path/'shared.json';storage.save(Project(),path)
    digest=storage.fingerprint(path);path.write_text('another process data')
    with pytest.raises(FileExistsError,match='değişti'):
        storage.save(Project(),path,overwrite=True,expected_digest=digest)
    assert path.read_text()=='another process data'
    assert not list(tmp_path.glob('.shaft-*'))
