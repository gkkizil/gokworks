"""Counterexamples found while reviewing the multibody integration."""
from pathlib import Path
from queue import Queue
from threading import Event

import pytest

from modules.cad_converter.models import checkpoint
from modules.dxf_dwg.exporter import export_selection
from modules.dxf_dwg.inventory import plan_destinations
from modules.dxf_dwg.sheetmetal import scan_inventory
from .sheet_fakes import environment, part, assembly, component


@pytest.fixture
def env(monkeypatch):return environment(monkeypatch)


def scan(env):
    with env[1]() as session:return scan_inventory(session)[0]


@pytest.mark.parametrize('custom_code',[False,True])
def test_exported_names_do_not_change_when_only_one_colliding_part_is_selected(env,tmp_path,custom_code):
    app,_,_=env
    prefix='P'*145 if not custom_code else ''
    a=part(app,tmp_path/(prefix+'A.SLDPRT'));b=part(app,tmp_path/(prefix+'B.SLDPRT'))
    root=assembly(app,tmp_path/'Main.SLDASM',[component(a,name='A'),component(b,name='B')]);app.ActiveDoc=root
    if custom_code:
        for model in (a,b):model.features_by_config['Default'][1].CustomPropertyManager.values['PART NUMBER']='SHARED'
    rows=scan(env);naming=('code',) if custom_code else ()
    together=plan_destinations(rows,tmp_path,tmp_path/'out',('dxf',),naming=naming)
    separately=[plan_destinations([row],tmp_path,tmp_path/'out',('dxf',),naming=naming)[row['sheet_id']] for row in rows]
    assert [together[row['sheet_id']] for row in rows]==separately
    assert separately[0]!=separately[1]


def test_custom_code_cannot_overwrite_a_different_part_in_a_later_export(env,tmp_path):
    app,Session,_=env
    a=part(app,tmp_path/'A.SLDPRT');b=part(app,tmp_path/'B.SLDPRT',{'Default':[('Body',1,40)]})
    for model in (a,b):model.features_by_config['Default'][1].CustomPropertyManager.values['PART NUMBER']='SHARED'
    root=assembly(app,tmp_path/'Main.SLDASM',[component(a,name='A'),component(b,name='B')]);app.ActiveDoc=root
    rows=scan(env);paths=[];before=None
    for row in rows:
        events=Queue()
        export_selection([row],tmp_path,tmp_path/'out',('dxf',),events,overwrite=True,naming=('code',),session_factory=Session)
        result=next(r for kind,r in events.queue if kind=='sheet_result')
        assert result['status']=='success'
        paths.append(Path(result['outputs'][0]['path']))
        if before is None:before=paths[0].read_bytes()
    assert paths[0]!=paths[1] and paths[0].read_bytes()==before


def test_body_material_is_more_specific_than_document_material(env,tmp_path,monkeypatch):
    app,Session,_=env;p=part(app,tmp_path/'Panel.SLDPRT');app.ActiveDoc=p
    p.features_by_config['Default'][1].CustomPropertyManager.values.pop('MATERIAL')
    p.by_config['Default'][0].GetMaterialPropertyName2=lambda *args:'S355JR'
    monkeypatch.setattr(Session,'document_properties',lambda *args:{'MATERIAL':'S235JR'})
    rows=scan(env)
    assert rows[0]['exportable'] and rows[0]['material']=='S355JR'


@pytest.mark.parametrize('change',['thickness','material'])
@pytest.mark.parametrize('live_stamp',[10,None])
def test_next_body_is_revalidated_even_if_a_prior_body_was_already_checked(env,tmp_path,change,live_stamp):
    app,Session,_=env;p=part(app,tmp_path/'Multi.SLDPRT',count=2);app.ActiveDoc=p
    p.GetUpdateStamp=lambda:live_stamp
    rows=scan(env)
    def changed():
        if change=='thickness':p.by_config['Default'][1].features[0].thickness=9
        else:p.features_by_config['Default'][4].CustomPropertyManager.values['MATERIAL']='S355JR'
    p.after_export=changed;events=Queue()
    export_selection(rows,tmp_path,tmp_path/'out',('dxf',),events,session_factory=Session)
    results=[r for kind,r in events.queue if kind=='sheet_result']
    assert results[0]['status']=='success' and results[1]['status']=='error'
    assert 'değişmiş' in results[1]['detail'] and len(p.export_calls)==1


def test_stop_during_body_validation_never_leaves_current_body_running(env,tmp_path,monkeypatch):
    app,Session,_=env;p=part(app,tmp_path/'Panel.SLDPRT');app.ActiveDoc=p
    rows=scan(env);stop=Event();events=Queue()
    def cancelled(*args,**kwargs):stop.set();checkpoint(stop)
    monkeypatch.setattr(Session,'describe',cancelled)
    export_selection(rows,tmp_path,tmp_path/'out',('dxf',),events,stop,session_factory=Session)
    assert events.queue[-1][1]['state']=='cancelled'
    results=[r for kind,r in events.queue if kind=='sheet_result']
    assert len(results)==1 and results[0]['status']=='skipped' and not p.export_calls
    assert p.selection==['user selection']


def test_export_validation_reads_only_the_selected_bodys_properties(env,tmp_path):
    app,Session,_=env;p=part(app,tmp_path/'Multi.SLDPRT',count=2);app.ActiveDoc=p
    rows=scan(env);reads=[]
    manager=p.features_by_config['Default'][1].CustomPropertyManager
    original=manager.GetNames
    manager.GetNames=lambda:reads.append('unselected') or original()
    events=Queue()
    export_selection([rows[1]],tmp_path,tmp_path/'out',('dxf',),events,session_factory=Session)
    assert events.queue[-1][1]['succeeded']==1 and not reads
    assert len(p.export_calls)==1 and p.export_calls[0][1]==rows[1]['body_name']


def test_cancelled_validation_with_restore_failure_is_an_error_not_a_clean_stop(env,tmp_path,monkeypatch):
    app,Session,_=env
    p=part(app,tmp_path/'Panel.SLDPRT',{'A':[('Body',1,10)],'B':[('Body',2,20)]})
    root=assembly(app,tmp_path/'Main.SLDASM',[component(p,configuration='B')]);app.ActiveDoc=root
    rows=scan(env);stop=Event();events=Queue();show=p.ShowConfiguration2
    p.ShowConfiguration2=lambda name:False if name=='A' else show(name)
    def cancelled(*args,**kwargs):stop.set();checkpoint(stop)
    monkeypatch.setattr(Session,'describe',cancelled)
    export_selection(rows,tmp_path,tmp_path/'out',('dxf',),events,stop,session_factory=Session)
    summary=events.queue[-1][1]
    assert summary['state']=='error' and summary['native_restore_failed'] and summary['failed']==1
    results=[r for kind,r in events.queue if kind=='sheet_result']
    assert len(results)==1 and results[0]['status']=='error' and not p.export_calls


@pytest.mark.parametrize('failure',['visibility','visibility_ignored','active_document','active_wrong_document'])
def test_document_state_restore_failure_preserves_output_and_stops_the_batch(env,tmp_path,failure):
    app,Session,_=env
    p=part(app,tmp_path/'Panel.SLDPRT');other=part(app,tmp_path/'Next.SLDPRT')
    root=assembly(app,tmp_path/'Main.SLDASM',[component(p,name='Panel'),component(other,name='Next')]);app.ActiveDoc=root
    rows=scan(env)
    if failure.startswith('visibility'):
        p._visible=False
        class HiddenPart(type(p)):
            @property
            def Visible(self):return self._visible
            @Visible.setter
            def Visible(self,value):
                if value is False:
                    if failure=='visibility':raise RuntimeError('visibility restore refused')
                    return
                self._visible=value
        p.__class__=HiddenPart
    else:
        activate=app.ActivateDoc3;attempts=[]
        def fails_once(name,*args):
            if name==root.path and not attempts:
                attempts.append(name)
                if failure=='active_wrong_document':return p
                args[-1].value=1;return None
            return activate(name,*args)
        app.ActivateDoc3=fails_once
    events=Queue()
    export_selection(rows,tmp_path,tmp_path/'out',('dxf',),events,session_factory=Session)
    summary=events.queue[-1][1]
    assert summary['state']=='error' and summary['native_restore_failed'] and summary['partial']==1
    results=[r for kind,r in events.queue if kind=='sheet_result']
    assert len(results)==1 and results[0]['status']=='partial'
    assert Path(results[0]['outputs'][0]['path']).is_file()
    assert not other.export_calls and not app.saves and p.selection==['user selection']
    assert app.ActiveDoc is root
