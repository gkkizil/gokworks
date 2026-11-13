"""A failed native close is fatal even after a file has been produced."""
from pathlib import Path
import pytest
from modules.dxf_dwg import exporter as ex
from .test_autosave import case as case

@pytest.mark.parametrize('mode',['exception','ignored'])
def test_owned_document_close_failure_cannot_be_reported_as_success(case,tmp_path,mode):
    app,part,root,_=case;app.existing=False
    opened=app.OpenDoc6
    def load(*args):
        model=opened(*args);app.existing=True;return model
    app.OpenDoc6=load
    if mode=='exception':
        def close(title):raise RuntimeError('close refused')
        app.CloseDoc=close
    else:app.CloseDoc=lambda title:None
    with pytest.raises(ex.SourceRestoreError,match='kapat'):
        ex.export_one_part(app,part.path,[tmp_path/'saved.dxf'])
    assert (tmp_path/'saved.dxf').exists()


def test_closed_reference_can_remain_loaded_with_its_window_hidden(case,tmp_path):
    app,part,_,_=case;app.existing=False
    opened=app.OpenDoc6
    def load(*args):
        model=opened(*args);app.existing=True;return model
    app.OpenDoc6=load
    app.CloseDoc=lambda title:setattr(part,'Visible',False)
    status,detail=ex.export_one_part(app,part.path,[tmp_path/'saved.dxf'])
    assert status=='success',detail
    assert app.GetOpenDocumentByName(part.path) is part and part.Visible is False


@pytest.mark.parametrize('mode',['exception','ignored'])
def test_legacy_queue_reports_published_output_as_partial_and_stops_after_close_failure(case,tmp_path,monkeypatch,mode):
    from queue import Queue
    from support.solidworks import FakeComponent
    app,part,root,_=case;app.existing=False
    next_path=tmp_path/'zzz.SLDPRT';next_path.write_bytes(b'native source')
    root.root.children=(*root.root.children,FakeComponent(next_path))
    opened=app.OpenDoc6
    def load(*args):
        model=opened(*args);app.existing=True;return model
    app.OpenDoc6=load
    def close(title):
        if mode=='exception':raise RuntimeError('close refused')
    app.CloseDoc=close
    monkeypatch.setattr(ex,'connect_to_solidworks',lambda:app)
    events=Queue();ex.export_parts(tmp_path,tmp_path/'out',False,False,events)
    messages=list(events.queue);summary=messages[-1][1]
    assert summary['state']=='error' and summary['native_restore_failed']
    assert summary['processed']==1 and summary['partial']==1 and summary['succeeded']==0
    results=[r for k,r in messages if k=='result']
    assert len(results)==1 and results[0]['status']=='partial'
    assert all(Path(o['path']).exists() for o in results[0]['outputs'])
    assert len([v for k,v in messages if k=='current'])==1


def test_successful_close_does_not_call_the_retired_document_again(case,tmp_path):
    app,part,root,_=case;app.existing=False;closed=[]
    path=part.GetPathName
    def source_path():
        if closed:raise RuntimeError('document proxy is retired')
        return path()
    activate=app.ActivateDoc3
    def restore(name,*args):
        if name==root.path:
            app.ActiveDoc=root;return root
        return activate(name,*args)
    app.ActivateDoc3=restore
    part.GetPathName=source_path
    app.CloseDoc=lambda title:closed.append(title)
    status,detail=ex.export_one_part(app,part.path,[tmp_path/'saved.dxf'])
    assert status=='success',detail
    assert closed and (tmp_path/'saved.dxf').exists()
