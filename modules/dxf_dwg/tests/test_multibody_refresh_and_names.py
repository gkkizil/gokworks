"""Rebuilt bodies, scoped FlatPattern definitions and stable numbered outputs."""
from pathlib import Path
from queue import Queue
from types import SimpleNamespace as NS

import pytest

from modules.cad_converter import api
from modules.dxf_dwg.sheetmetal import scan_inventory
from modules.dxf_dwg.inventory import plan_destinations, display_rows
from modules.dxf_dwg.exporter import export_selection
from modules.dxf_dwg.preview.flat import read_flat
from .sheet_fakes import environment, part, Body, assembly, component


@pytest.fixture
def case(monkeypatch,tmp_path):
    app,session,_=environment(monkeypatch)
    model=part(app,tmp_path/'ORHAN.SLDPRT',count=3);app.ActiveDoc=model
    return app,session,model


def scan(case):
    with case[1]() as session:return scan_inventory(session)


def test_rebuild_replaces_all_bodies_and_old_com_objects_are_never_used(case):
    app,session,model=case;old=list(model.by_config['Default'])
    class RetiredBody(Body):
        def __getattribute__(self,name):
            if name in ('Name','ref','GetFeatures'):
                raise RuntimeError('E_FAIL: body was replaced by the native rebuild')
            return super().__getattribute__(name)
    model.Extension.NeedsRebuild2=True
    def rebuild():
        fresh=part(app,model.path,count=3)
        model.by_config=fresh.by_config;model.features_by_config=fresh.features_by_config
        for body in model.by_config['Default']:body.model=model
        app.models[model.path]=model
        for body in old:body.__class__=RetiredBody
        model.Extension.NeedsRebuild2=False
        return True
    model.EditRebuild3=rebuild
    rows,_=scan(case)
    assert len(rows)==3 and all(r['exportable'] for r in rows)
    assert sorted(r['body_index'] for r in rows)==[1,2,3]
    assert all(r['body_name']!='Adsız sac gövdesi' for r in rows)
    events=Queue()
    export_selection(rows,Path(model.path).parent,Path(model.path).parent/'out',('dxf',),events,session_factory=session)
    assert events.queue[-1][1]['succeeded']==3 and not app.saves


def install_access(case,monkeypatch,*,fail_release=False,access_ok=True):
    _,_,model=case;definitions=[]
    monkeypatch.setattr(api,'null_dispatch',lambda:None)
    class Definition:
        def __init__(self,body):self.body=body;self.active=False;self.accesses=0;self.releases=0
        @property
        def FixedFace2(self):
            return NS(GetBody=lambda:self.body) if self.active else None
        def AccessSelections(self,owner,component):
            assert owner is model and component is None
            self.accesses+=1
            if not access_ok:return False
            model.selection=[];self.active=True;return True
        def ReleaseSelectionAccess(self):
            self.releases+=1;self.active=False
            if fail_release:raise RuntimeError('release failed')
    for f in model.features_by_config['Default']:
        if f.kind=='FlatPattern':
            d=Definition(f.body);definitions.append(d);f.GetDefinition=lambda d=d:d
    return definitions


def test_multibody_fixed_faces_requiring_definition_access_scan_and_export(case,monkeypatch,tmp_path):
    app,session,model=case;defs=install_access(case,monkeypatch)
    before=Path(model.path).read_bytes()
    rows,_=scan(case)
    assert len(rows)==3 and all(r['exportable'] for r in rows)
    events=Queue();export_selection(rows,tmp_path,tmp_path/'out',('dxf',),events,session_factory=session)
    assert events.queue[-1][1]['succeeded']==3 and len(model.export_calls)==3
    assert all(d.accesses==d.releases and not d.active for d in defs)
    assert model.selection==['user selection'] and not model.SelectionManager.saved
    assert not app.saves and Path(model.path).read_bytes()==before
    outputs=[r for k,r in events.queue if k=='sheet_result']
    assert {Path(r['outputs'][0]['path']).name for r in outputs}=={
        f'ORHAN-{i:02d} - {i} mm - 1 adet.dxf' for i in (1,2,3)}
    assert {read_flat(r['outputs'][0]['path']).bounds[2] for r in outputs}=={10,20,30}


def test_definition_release_failure_is_a_restore_failure_not_an_approved_body(case,monkeypatch):
    app,_,model=case;defs=install_access(case,monkeypatch,fail_release=True)
    with pytest.raises(api.RestoreError,match='tanım erişimi'):scan(case)
    assert defs[0].releases==1 and model.selection==['user selection'] and not app.saves


def test_definition_rollback_can_replace_body_objects_without_losing_any_sheet(case,monkeypatch,tmp_path):
    app,session,model=case;defs=install_access(case,monkeypatch)
    class RetiredBody(Body):
        def __getattribute__(self,name):
            if name in ('Name','ref','GetFeatures'):
                raise RuntimeError('Body pointer belongs to the old rollback state')
            return super().__getattribute__(name)
    def regenerate():
        old=model.by_config['Default'];new=[];mapping={}
        for body in old:
            live=Body(body.Name,model,body.sheet,body.width,body.thickness)
            live.features=body.features;new.append(live);mapping[id(body)]=live
        for feature in model.features_by_config['Default']:feature.body=mapping[id(feature.body)]
        for definition in defs:definition.body=mapping[id(definition.body)]
        model.by_config['Default']=new
        for body in old:body.__class__=RetiredBody
    for definition in defs:
        release=definition.ReleaseSelectionAccess
        def replaced(release=release):release();regenerate()
        definition.ReleaseSelectionAccess=replaced
    rows,_=scan(case)
    assert len(rows)==3 and all(r['exportable'] for r in rows)
    events=Queue();export_selection(rows,tmp_path,tmp_path/'out',('dxf',),events,session_factory=session)
    assert events.queue[-1][1]['succeeded']==3 and not app.saves
    assert model.selection==['user selection']


def test_failed_definition_access_does_not_guess_a_flat_pattern(case,monkeypatch):
    _,_,model=case;defs=install_access(case,monkeypatch,access_ok=False)
    rows,_=scan(case)
    assert len(rows)==3 and not any(r['exportable'] for r in rows)
    assert all(d.releases==0 for d in defs) and model.selection==['user selection']


def test_numbered_names_are_stable_for_subset_reordered_bodies_and_both_formats(case,tmp_path):
    _,session,model=case;first,_=scan(case)
    plans=plan_destinations(first,tmp_path,tmp_path/'out',('dxf','dwg'))
    for row in first:
        i=row['body_index']
        assert [p.name for p in plans[row['sheet_id']]]==[
            f'ORHAN-{i:02d} - {i} mm - 1 adet.{fmt}' for fmt in ('dxf','dwg')]
        assert plan_destinations([row],tmp_path,tmp_path/'out',('dxf','dwg'))[row['sheet_id']]==plans[row['sheet_id']]
    model.by_config['Default'].reverse();second,_=scan(case)
    assert {r['body_ref']:r['body_index'] for r in first}=={r['body_ref']:r['body_index'] for r in second}
    selected=next(r for r in first if r['body_index']==2)
    with session() as s:
        refreshed,_=s.describe(model,model.path,'Default',body_ref=selected['body_ref'])
    assert len(refreshed)==1 and refreshed[0]['body_index']==2 and refreshed[0]['sheet_count']==3
    shown=display_rows(first,{r['sheet_id']:set(r['instances']) for r in first})
    assert {r['source_label'].split(' [')[0] for r in shown}=={'ORHAN-01','ORHAN-02','ORHAN-03'}


def test_non_sheet_bodies_do_not_consume_sheet_numbers(case,tmp_path):
    _,_,model=case
    model.by_config['Default'].insert(0,Body('Mechanical',model,sheet=False))
    rows,_=scan(case)
    assert len(rows)==3 and {r['body_index'] for r in rows}=={1,2,3}
    names=[p.name for group in plan_destinations(rows,tmp_path,tmp_path/'out',('dxf',)).values() for p in group]
    assert all(name.startswith(('ORHAN-01 ','ORHAN-02 ','ORHAN-03 ')) for name in names)


def test_numbered_body_cannot_collide_with_a_distinct_native_part_in_a_later_subset(case,tmp_path):
    app,_,model=case;other=part(app,tmp_path/'ORHAN-01.SLDPRT')
    app.ActiveDoc=assembly(app,tmp_path/'Root.SLDASM',[component(model,name='Multi-1'),component(other,name='Single-1')])
    rows,_=scan(case);plans=plan_destinations(rows,tmp_path,tmp_path/'out',('dxf',))
    paths=[str(p) for targets in plans.values() for p in targets]
    assert len(paths)==len(set(paths))==4
    for row in rows:
        assert plan_destinations([row],tmp_path,tmp_path/'out',('dxf',))[row['sheet_id']]==plans[row['sheet_id']]
    assert sum(bool(row.get('numbered_name_collision')) for row in rows)==2
