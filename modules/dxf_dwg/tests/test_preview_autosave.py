"""Preview crosses the real native export/save lifecycle with controlled COM."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from support.solidworks import com_stubs
from modules.cad_converter import api
from modules.dxf_dwg.preview import solidworks as sw
from modules.dxf_dwg.preview.models import MeshCache
from .test_preview_source import source as source
from .test_preview_geometry import flat_file


@pytest.fixture
def saving(source, monkeypatch, tmp_path):
    app, model, previous, body, request, session_type = source
    root = app.add(tmp_path/'Root.SLDASM', opened=True)
    for doc in app.models.values():
        doc.dirty = False
        doc.GetSaveFlag = lambda d=doc: d.dirty
        doc.IsOpenedReadOnly = lambda: False
    calls=[]
    def save(doc):
        def operation(options, errors, warnings):
            assert options == 5  # Silent | SaveReferenced, never a UI command.
            calls.append((doc.path, doc.active))
            doc.dirty = False
            Path(doc.path).write_text('native saved '+doc.active+str(len(calls)))
            if doc is model: root.dirty = True
            return True
        return operation
    for doc in app.models.values():doc.Save3 = save(doc)
    app.GetDocuments = lambda: tuple(d for d in app.models.values() if d.opened or d.keep_loaded)
    com,client=com_stubs('dxf',dynamic=True)
    monkeypatch.setattr(sw.exporter,'pythoncom',com)
    monkeypatch.setattr(sw.exporter,'win32com',NS(client=client))
    exports=[]
    def export(path,*args):
        # A native server needing saved references would block here with the
        # Save Modified Documents dialog. Saving only after capture is too late.
        assert not any(d.dirty for d in app.GetDocuments()), 'MODAL_SAVE_DIALOG'
        exports.append(path);flat_file(Path(path));model.dirty=True
        return True
    model.ExportToDWG2=export
    close=app.CloseDoc
    def close_without_dialog(title):
        assert not any(d.dirty for d in app.GetDocuments()), 'MODAL_SAVE_DIALOG'
        close(title)
    app.CloseDoc=close_without_dialog
    opened=[];open_doc=app.OpenDoc6
    def open_record(path,kind,options,*args):
        opened.append(options);return open_doc(path,kind,options,*args)
    app.OpenDoc6=open_record
    return NS(app=app,model=model,root=root,request=replace(request,output=''),
              session=session_type,calls=calls,exports=exports,opened=opened)


def read(case, **kwargs):
    return sw.capture(case.request,MeshCache(),session_factory=case.session,save_modified=True,**kwargs)


def test_preview_saves_modified_parts_and_parent_before_native_flat_export(saving):
    c=saving;c.model.dirty=c.root.dirty=True
    result=read(c)
    assert result.flat and result.mesh.triangles==1 and c.exports
    assert {p for p,_ in c.calls}=={c.model.path,c.root.path}
    assert not c.model.dirty and not c.root.dirty
    assert result.revision[1]==sw.file_stamp(c.model.path)
    assert any('otomatik kaydedildi' in w for w in result.warnings)


def test_rebuild_dirtied_source_is_saved_before_export_not_only_at_preview_entry(saving):
    c=saving;c.model.Extension.NeedsRebuild2=True
    def rebuild():
        c.model.dirty=True;c.model.Extension.NeedsRebuild2=False;return True
    c.model.EditRebuild3=rebuild
    assert read(c).flat and c.exports and c.calls


def test_original_configuration_is_restored_and_saved_after_reading_derived_flat(saving):
    c=saving;c.model.active='Flat';show=c.model.ShowConfiguration2
    def change(name):
        result=show(name);c.model.dirty=True;return result
    c.model.ShowConfiguration2=change
    c.request=replace(c.request,configuration='Bent')
    result=read(c)
    assert result.configuration=='Bent' and c.model.active=='Flat'
    assert [config for path,config in c.calls if path==c.model.path][-1]=='Flat'
    assert not c.model.dirty and not c.root.dirty
    assert result.revision[1]==sw.file_stamp(c.model.path)
    assert result.revision[-1] is None  # No cache stamped before the final save.


def test_preview_opens_its_own_source_writable_and_saves_before_closing(saving):
    c=saving;c.model.opened=False
    assert read(c).flat and c.exports
    assert c.app.open_calls
    # Constants are the real enum fixture; inspect the actual OpenDoc6 flags.
    from modules.cad_converter.tests.fakes import C
    assert not c.opened[0] & C['swOpenDocOptions_ReadOnly']
    assert c.model.GetTitle() in c.app.closed and not c.model.dirty


@pytest.mark.parametrize('failure',['readonly','save_error','unnamed'])
def test_unsavable_source_never_reaches_native_export_or_modal_close(saving,failure):
    c=saving;c.model.dirty=True
    if failure=='readonly':c.model.IsOpenedReadOnly=lambda:True
    if failure=='unnamed':c.model.GetPathName=lambda:''
    if failure=='save_error':
        def fail(options,errors,warnings):errors.value=4;return False
        c.model.Save3=fail
    with pytest.raises(api.ApiError,match='kayıt|kaydedin'):
        read(c)
    assert not c.exports and not c.app.closed and c.model.opened


def test_failed_original_configuration_restore_never_persists_that_temporary_state(saving):
    c=saving;c.model.active='Flat';show=c.model.ShowConfiguration2
    c.request=replace(c.request,configuration='Bent')
    def change(name):
        if name=='Flat':return False
        c.model.dirty=True;return show(name)
    c.model.ShowConfiguration2=change
    with pytest.raises(api.RestoreError):read(c)
    assert not any(config=='Flat' for path,config in c.calls if path==c.model.path)
    assert c.model.opened and not c.app.closed


def test_save_error_after_native_export_does_not_close_dirty_owned_document(saving):
    c=saving;c.model.opened=False
    def fail(options,errors,warnings):errors.value=4;return False
    c.model.Save3=fail
    with pytest.raises(api.RestoreError,match='açık bırakıldı'):read(c)
    assert c.exports and c.model.dirty and c.model.opened and not c.app.closed


def test_failed_save_keeps_a_temporarily_shown_component_visible_for_recovery(saving):
    c=saving;c.model.Visible=False
    def fail(options,errors,warnings):errors.value=4;return False
    c.model.Save3=fail
    with pytest.raises(api.ApiError):read(c)
    assert c.exports and c.model.dirty and c.model.Visible and not c.app.closed


def test_post_restore_save_that_changes_live_geometry_gets_one_fresh_read(saving):
    c=saving;c.model.active='Flat';c.request=replace(c.request,configuration='Bent')
    show=c.model.ShowConfiguration2
    def change(name):
        ok=show(name);c.model.dirty=True;return ok
    c.model.ShowConfiguration2=change
    stamp=[10];c.model.GetUpdateStamp=lambda:stamp[0]
    original=c.model.Save3;bumped=[]
    def save(options,errors,warnings):
        ok=original(options,errors,warnings)
        if c.model.active=='Flat' and not bumped:stamp[0]+=1;bumped.append(True)
        return ok
    c.model.Save3=save
    result=read(c)
    assert len(c.exports)==2 and result.mesh.triangles==1
    assert result.revision[1]==sw.file_stamp(c.model.path)


def test_repeated_save_rebuilds_do_not_publish_an_unstable_snapshot(saving):
    c=saving;c.model.active='Flat';c.request=replace(c.request,configuration='Bent')
    show=c.model.ShowConfiguration2
    def change(name):
        ok=show(name);c.model.dirty=True;return ok
    c.model.ShowConfiguration2=change
    stamp=[10];c.model.GetUpdateStamp=lambda:stamp[0];save=c.model.Save3
    def changed(options,errors,warnings):
        ok=save(options,errors,warnings)
        if c.model.active=='Flat':stamp[0]+=1
        return ok
    c.model.Save3=changed
    with pytest.raises(api.ApiError,match='tekrar güncelliyor'):read(c)
    assert len(c.exports)==2


def test_raw_dispatch_session_uses_late_bound_silent_save_and_real_export(saving,monkeypatch):
    c=saving;c.model.dirty=True
    class RawDispatch:
        def GetIDsOfNames(self,locale,name):return name
        def Invoke(self,name,locale,flags,want_result,*args):
            member=getattr(c.app,name)
            return member(*args) if flags==1 else member
    raw=RawDispatch();wrapped=[]
    def dispatch(obj):
        if obj is raw:wrapped.append(True);return c.app
        return obj
    monkeypatch.setattr(sw.exporter.win32com.client.dynamic,'DumbDispatch',dispatch)
    parent=c.session
    class RawSession(parent):
        def __enter__(self):
            super().__enter__();self.app=raw;return self
    c.session=RawSession
    result=read(c)
    assert wrapped and c.calls and c.exports and result.flat
