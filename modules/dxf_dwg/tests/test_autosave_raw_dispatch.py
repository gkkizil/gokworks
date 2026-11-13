"""Raw document pointers at autosave boundaries; controlled COM, not live CAD."""
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from modules.dxf_dwg import exporter as ex
from .test_autosave import case as case
from .test_selection_autosave import case as _selected_case, run as selected_run

selection_case = _selected_case


class PyIDispatch:
    """Only the raw IDispatch protocol; no GetPathName Python attribute."""
    __slots__ = ('target',)
    def __init__(self, target): self.target = target
    def GetIDsOfNames(self, locale, name): return name
    def Invoke(self, name, locale, flags, want_result, *args):
        member = getattr(self.target, name)
        return member(*args) if flags == 1 else member


def wrappers(monkeypatch):
    seen=[]
    def wrap(value):
        seen.append(value)
        return value.target if isinstance(value, PyIDispatch) else value
    monkeypatch.setattr(ex.win32com.client, 'dynamic', NS(DumbDispatch=wrap), raising=False)
    return seen


@pytest.mark.parametrize('boundary', ['extra','documents','both','application'])
def test_silent_save_handles_raw_documents_before_path_and_dirty_flag_access(case,monkeypatch,boundary):
    app,part,parent,calls=case;part.dirty=True
    raw=PyIDispatch(part);raw_parent=PyIDispatch(parent)
    documents=app.GetDocuments
    if boundary in ('documents','both'):
        app.GetDocuments=lambda:(raw,raw_parent)
    seen=wrappers(monkeypatch)
    extra=(raw,) if boundary in ('extra','both') else ()
    active=app.ActiveDoc
    saved,warnings=ex.save_modified_documents(PyIDispatch(app) if boundary=='application' else app,extra=extra)
    assert saved==[part.path,parent.path] and not warnings
    assert len(calls)==2 and not part.dirty and not parent.dirty
    assert app.ActiveDoc is active and not app.closed and seen
    if boundary=='extra':assert raw in seen and documents()


@pytest.mark.parametrize('readonly',[False,True])
def test_raw_document_save_errors_remain_fatal_and_do_not_close_documents(case,monkeypatch,readonly):
    app,part,_,calls=case;part.dirty=True;part.readonly=readonly
    if not readonly:part.Save3=lambda *args:False
    wrappers(monkeypatch)
    with pytest.raises(ex.SaveDocumentsError,match='salt okunur|kayıt başarısız'):
        ex.save_modified_documents(app,extra=(PyIDispatch(part),))
    assert part.dirty and not calls and not app.closed


def test_raw_document_metadata_is_read_after_save_instead_of_silently_becoming_empty(case,monkeypatch):
    _,part,_,_=case;wrappers(monkeypatch)
    result=ex.preview_identity(PyIDispatch(part),None)
    info=Path(part.path).stat()
    assert result['source_stamp']==(info.st_size,info.st_mtime_ns)


def test_selected_export_passes_a_raw_source_through_save_restore_and_final_close_checks(selection_case,monkeypatch):
    c=selection_case;seen=wrappers(monkeypatch);raw=PyIDispatch(c.model)
    parent=c.session
    class Session(parent):
        def document(self,path=None):
            result=super().document(path)
            return raw if result is c.model else result
        def _close_document(self,path,**kwargs):
            # Native GetDocuments can also return raw entries during cleanup.
            get_documents=self.app.GetDocuments
            self.app.GetDocuments=lambda:tuple(PyIDispatch(doc) for doc in get_documents())
            try:return super()._close_document(path,**kwargs)
            finally:self.app.GetDocuments=get_documents
    c.session=Session;c.model.dirty=True
    c.model.opened=False;c.model.Visible=False
    # Active root stays a normal wrapped document; only the explicit source is raw.
    result=selected_run(c,rows=c.rows[1:])
    assert result['state']=='completed' and result['succeeded']==2, result
    assert raw in seen and c.calls and not c.model.dirty and not c.root.dirty
    assert c.app.ActiveDoc is c.root and not c.model.opened and c.root.opened
    rows=[r for k,r in c.events if k=='sheet_result']
    assert [r['body_ref'] for r in rows]==[r['body_ref'] for r in c.rows[1:]]
    assert all(r.get('source_stamp') for r in rows)
