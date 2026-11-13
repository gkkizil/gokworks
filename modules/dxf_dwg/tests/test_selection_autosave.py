"""Selected production exports use real save/restore logic with controlled COM."""
from pathlib import Path
from queue import Queue
from threading import Event
from types import SimpleNamespace as NS

import pytest

from modules.cad_converter.tests.fakes import C
from modules.dxf_dwg import exporter as ex
from modules.dxf_dwg.autosave import Session as SavingSession
from modules.dxf_dwg.sheetmetal import scan_inventory
from .sheet_fakes import environment, part, assembly, component


@pytest.fixture
def case(monkeypatch, tmp_path):
    app, fake, _ = environment(monkeypatch)
    model = part(app, tmp_path/'ORHAN.SLDPRT', count=3)
    root = assembly(app, tmp_path/'Root.SLDASM', [component(model)])
    app.ActiveDoc = root
    with fake() as session:
        rows, _ = scan_inventory(session)
    class Session(SavingSession, fake):
        pass
    calls = []
    def install(doc):
        doc.dirty = False
        doc.readonly = False
        doc.GetSaveFlag = lambda: doc.dirty
        doc.IsOpenedReadOnly = lambda: doc.readonly
        def save(options, errors, warnings):
            assert options == 5
            calls.append((doc.path, doc.active))
            doc.dirty = False
            Path(doc.path).write_text(f'native save {doc.active} {len(calls)}')
            if doc is model: root.dirty = True
            return True
        doc.Save3 = save
    for doc in app.models.values(): install(doc)
    app.GetDocuments = lambda: tuple(d for d in app.models.values() if d.opened or d.keep_loaded)
    export = model.ExportToDWG2
    def native(*args):
        assert not any(d.dirty for d in app.GetDocuments()), 'MODAL_SAVE_DIALOG'
        result = export(*args)
        model.dirty = True
        return result
    model.ExportToDWG2 = native
    show = model.ShowConfiguration2
    def change(name):
        before = model.active
        result = show(name)
        if before != model.active: model.dirty = True
        return result
    model.ShowConfiguration2 = change
    close = app.CloseDoc
    def close_clean(title):
        assert not any(d.dirty for d in app.GetDocuments()), 'MODAL_SAVE_DIALOG'
        close(title)
    app.CloseDoc = close_clean
    return NS(app=app, model=model, root=root, rows=rows, session=Session, calls=calls, install=install,
              source=tmp_path, output=tmp_path/'out')


def run(case, *, rows=None, formats=('dxf',), stop=None):
    events = Queue()
    ex.export_selection(case.rows if rows is None else rows, case.source, case.output, formats, events,
                        stop, session_factory=case.session, save_modified=True)
    case.events = list(events.queue)
    return case.events[-1][1]


@pytest.mark.parametrize('formats', [('dxf',), ('dwg',), ('dxf','dwg')])
def test_selected_multibody_export_without_preview_saves_and_keeps_numbered_body_identity(case, formats):
    c=case; c.model.dirty=c.root.dirty=True
    rows=c.rows[1:]
    result=run(c, rows=rows, formats=formats)
    assert result['state']=='completed' and result['succeeded']==2, (result,c.events)
    assert c.calls and not c.model.dirty and not c.root.dirty
    assert all(config=='Default' for _,config in c.calls)
    outputs=[row for kind,row in c.events if kind=='sheet_result']
    assert [r['body_ref'] for r in outputs]==[r['body_ref'] for r in rows]
    assert all(Path(o['path']).name.startswith(f"ORHAN-{r['body_index']:02d} - ") for r in outputs for o in r['outputs'])
    info=Path(c.model.path).stat()
    assert outputs[-1]['source_stamp']==(info.st_size,info.st_mtime_ns)
    assert c.model.selection==['user selection'] and c.app.ActiveDoc is c.root
    assert any('otomatik kaydedildi' in warning for warning in result['warnings'])


def alternate(case):
    c=case
    new=part(c.app,c.model.path,{'A':[('Body',1,10)],'B':[('Body',1,10)]})
    c.model.by_config=new.by_config;c.model.features_by_config=new.features_by_config
    for bodies in c.model.by_config.values():
        for body in bodies:body.model=c.model
    c.model.names=('A','B');c.model.active='A';c.app.models[c.model.path]=c.model
    with c.session() as session:
        with session.configuration(c.model,'B'):
            c.rows,_=session.describe(c.model,c.model.path,'B')
    for row in c.rows: row['quantity']=1
    c.model.dirty=False


def test_original_configuration_is_saved_after_exported_configuration_is_restored(case):
    c=case;alternate(c)
    result=run(c)
    assert result['succeeded']==1 and c.model.export_calls==[('B','B-Body',1)], (result,c.events)
    saves=[conf for path,conf in c.calls if path==c.model.path]
    assert 'B' in saves and saves[-1]=='A'
    assert c.model.active=='A' and 'native save A' in Path(c.model.path).read_text()
    assert not c.model.dirty and not c.root.dirty and c.app.ActiveDoc is c.root
    row=next(r for k,r in c.events if k=='sheet_result')
    info=Path(c.model.path).stat()
    assert row['source_stamp']==(info.st_size,info.st_mtime_ns)


def test_export_owned_source_is_opened_writable_saved_and_only_then_closed(case):
    c=case;c.model.opened=False;c.model.Visible=False
    options=[];opened=c.app.OpenDoc6
    def open_doc(path,kind,flags,*args):
        options.append(flags);return opened(path,kind,flags,*args)
    c.app.OpenDoc6=open_doc
    assert run(c)['succeeded']==3
    assert options and not options[0]&C['swOpenDocOptions_ReadOnly']
    assert c.calls and not c.model.opened and c.root.opened and c.app.ActiveDoc is c.root


@pytest.mark.parametrize('mode',['readonly','unnamed'])
def test_unsavable_open_document_stops_before_any_export_or_save(case,mode):
    c=case;c.model.dirty=c.root.dirty=True
    if mode=='readonly':c.model.readonly=True
    else:c.model.path=''
    result=run(c)
    assert result['state']=='error' and 'Otomatik kayıt' in result['error']
    assert not c.calls and not c.model.export_calls and not c.app.closed
    assert not c.output.exists()


@pytest.mark.parametrize('owned',[False,True])
@pytest.mark.parametrize('formats',[('dxf',),('dxf','dwg')])
def test_post_export_save_failure_keeps_output_and_stops_remaining_bodies(case,owned,formats):
    c=case;c.model.Save3=lambda *args:False
    if owned:c.model.opened=False;c.model.Visible=False
    result=run(c,formats=formats)
    assert result['state']=='error' and result['partial']==1
    assert len(c.model.export_calls)==1 and c.model.dirty and not c.app.closed
    row=next(r for k,r in c.events if k=='sheet_result')
    assert row['status']=='partial' and 'kayıt' in row['detail'].lower()
    assert Path(row['outputs'][0]['path']).exists()
    assert c.model.opened


def test_save_failure_after_return_to_original_configuration_is_reported_as_partial(case):
    c=case;alternate(c);save=c.model.Save3
    c.model.Save3=lambda *args:False if c.model.active=='A' else save(*args)
    result=run(c)
    assert result['state']=='error' and result['partial']==1
    assert c.model.active=='A' and c.model.dirty and not c.app.closed
    row=next(r for k,r in c.events if k=='sheet_result')
    assert row['status']=='partial' and Path(row['outputs'][0]['path']).exists()


def test_failed_rebuild_is_not_persisted_as_an_autosave_during_cleanup(case):
    c=case;before=Path(c.model.path).read_bytes()
    c.model.Extension.NeedsRebuild2=True
    def fail_rebuild():
        c.model.dirty=True
        return False
    c.model.EditRebuild3=fail_rebuild
    c.model.ForceRebuild3=lambda *args:False
    result=run(c,rows=c.rows[:1])
    assert result['failed']==1 and not c.model.export_calls and not c.calls
    assert c.model.dirty and Path(c.model.path).read_bytes()==before


def test_failed_restore_never_saves_or_closes_the_unrestored_source(case):
    c=case;alternate(c);show=c.model.ShowConfiguration2
    c.model.ShowConfiguration2=lambda name:False if name=='A' else show(name)
    result=run(c)
    assert result['state']=='error' and result.get('native_restore_failed'), (result,c.events)
    assert not any(conf=='A' for path,conf in c.calls if path==c.model.path)
    assert c.model.active=='B' and not c.app.closed


def test_cancel_after_native_export_still_saves_restored_configuration_without_next_body(case):
    c=case;alternate(c);stop=Event();c.model.after_export=stop.set
    result=run(c,stop=stop)
    assert result['state']=='cancelled' and len(c.model.export_calls)==1, (result,c.events)
    assert c.model.active=='A' and not c.model.dirty and not c.root.dirty
    assert [conf for path,conf in c.calls if path==c.model.path][-1]=='A'
    assert not list(c.output.rglob('.gokworks-*'))


def test_workbench_export_route_enables_native_save_policy(monkeypatch,tmp_path):
    recorded=[]
    monkeypatch.setattr(ex,'export_selection',lambda *args,**kwargs:recorded.append(kwargs))
    ex.export_parts(tmp_path,tmp_path/'out',False,False,Queue(),items=[{'sheet_id':'selected'}])
    assert recorded[0]['save_modified'] is True
