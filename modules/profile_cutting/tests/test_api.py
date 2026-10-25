from types import ModuleType, SimpleNamespace as NS
import sys

import pytest

from modules.profile_cutting.solidworks import Session
from modules.profile_cutting.models import Project, transfer
from modules.profile_cutting.scanner import scan
from modules.cad_converter.api import RestoreError
from .fakes import Model, Folder, component, factory, CONSTANTS


def test_real_session_balances_com_apartment_and_restores_active_document(monkeypatch,tmp_path):
    calls=[]
    com=ModuleType('pythoncom')
    com.CoInitialize=lambda:calls.append('init')
    com.CoUninitialize=lambda:calls.append('uninit')
    monkeypatch.setitem(sys.modules,'pythoncom',com)
    model=Model(tmp_path/'part.SLDPRT',[Folder()])
    app=NS(ActiveDoc=model,ActivateDoc3=lambda *a:calls.append('restore') or model,
           CloseDoc=lambda *a:calls.append('close'))
    monkeypatch.setattr('solidworks.connection.connect_to_solidworks',lambda **kw:app)
    monkeypatch.setattr('modules.cad_converter.api.load_constants',lambda app:CONSTANTS | {'swDontRebuildActiveDoc':2})
    monkeypatch.setattr('modules.cad_converter.api.out_int',lambda:NS(value=0))
    with Session() as session:
        assert session.document() is model
    assert calls==['init','restore','uninit']


def test_connection_failure_always_releases_apartment(monkeypatch):
    calls=[];com=ModuleType('pythoncom')
    com.CoInitialize=lambda:calls.append('init');com.CoUninitialize=lambda:calls.append('uninit')
    monkeypatch.setitem(sys.modules,'pythoncom',com)
    def fail(**kw):raise RuntimeError('SolidWorks açık değil')
    monkeypatch.setattr('solidworks.connection.connect_to_solidworks',fail)
    with pytest.raises(RuntimeError,match='açık değil'):
        with Session():pass
    assert calls==['init','uninit']


def test_assembly_level_cut_is_reported_and_blocks_automatic_import(tmp_path):
    part=Model(tmp_path/'part.SLDPRT',[Folder()])
    cut=Folder('Assembly cut');cut.GetTypeName2=lambda:'Cut'
    root=Model(tmp_path/'r.SLDASM',[cut],children=[component('p',part.path)])
    session,make=factory([root,part],root)
    result=scan(session_factory=make)
    assert 'Montaj unsuru' in result.rows[0].issues[0] and not result.rows[0].ready
    project=Project();assert transfer(project,result)['blocked']==1


def test_configuration_restore_failure_aborts_scan_instead_of_publishing_success(tmp_path):
    part=Model(tmp_path/'p.SLDPRT',configs={'A':[Folder()],'B':[Folder()]})
    root=Model(tmp_path/'r.SLDASM',children=[component('p',part.path,'B')])
    original=part.ShowConfiguration2
    part.ShowConfiguration2=lambda name:False if name=='A' else original(name)
    session,make=factory([root,part],root)
    with pytest.raises(RestoreError):scan(session_factory=make)
    assert session.closed


def test_raw_get6_invoke_has_explicit_byref_outputs_and_accepts_tuple_result():
    calls=[]
    class Dispatch:
        def GetIDsOfNames(self,lcid,name): return {'GetNames':1,'Get6':2}[name]
        def Invoke(self,member,lcid,flags,result,*args):
            calls.append((member,flags))
            if member==1:return ('LENGTH',)
            assert args[0]=='LENGTH' and args[1] is False
            assert [a.varianttype for a in args[2:]]==[0x4008,0x4008,0x400B,0x400B]
            return 2,'SW-LENGTH@source','1234.5 mm',True,True
    session=Session();session.constants=CONSTANTS
    props=session.properties(NS(CustomPropertyManager=NS(_oleobj_=Dispatch())))
    assert props['LENGTH'].evaluated=='1234.5 mm' and props['LENGTH'].resolved
    assert props['LENGTH'].raw=='SW-LENGTH@source' and calls==[(1,1),(2,1)]


@pytest.mark.parametrize('status,expected',[(0,False),(1,True),(2,True),(False,False),(True,True),(None,None),(99,None)])
def test_needs_rebuild_uses_published_integer_enum_and_preserves_unknown_status(status,expected):
    session=Session();session.constants=CONSTANTS
    assert session.rebuild_pending(NS(Extension=NS(NeedsRebuild2=status))) is expected


def test_failed_read_drops_exception_owned_pointers_before_sta_exit(tmp_path):
    import weakref
    pointers=[]
    class Pointer:pass
    model=Model(tmp_path/'p.SLDPRT',[Folder()])
    session,make=factory([model],model)
    def failure(model):
        pointer=Pointer();pointers.append(weakref.ref(pointer))
        raise RuntimeError('Read failed')
    session.active_configuration=failure
    from .fakes import FakeSession
    class Guarded(FakeSession):
        def __exit__(self,*args):
            assert pointers and pointers[0]() is None
            super().__exit__(*args)
    session.__class__=Guarded
    with pytest.raises(RuntimeError,match='Read failed'):scan(session_factory=make)


def test_raw_feature_graph_deduplicates_new_dispatch_wrappers_and_follows_both_links():
    members={name:i for i,name in enumerate(('Name','GetTypeName2','GetFirstSubFeature',
        'GetNextFeature','GetNextSubFeature','Extension','GetPersistReference3'))}
    names={i:name for name,i in members.items()};calls=[]
    nodes={'root':('Gövdeler','FtrFolder','a','a',None),
           'a':('Kesim-1','CutListFolder',None,'b','b'),
           'b':('Kesim-2','CutListFolder',None,'a','a')}
    def wrap(key):return NS(_oleobj_=Dispatch(key)) if key is not None else None
    class Dispatch:
        def __init__(self,key):self.key=key
        def GetIDsOfNames(self,lcid,name):return members[name]
        def Invoke(self,member,lcid,flags,result,*args):
            name=names[member];calls.append((self.key,name,flags))
            assert flags==(2 if name in ('Name','Extension') else 1)
            if name=='Extension':return wrap('extension')
            if name=='FirstFeature':return wrap('root')
            if name=='GetPersistReference3':return args[0]._oleobj_.key.encode()
            node=nodes[self.key]
            if name=='Name':return node[0]
            if name=='GetTypeName2':return node[1]
            return wrap(node[{'GetFirstSubFeature':2,'GetNextFeature':3,'GetNextSubFeature':4}[name]])
    members['FirstFeature']=len(members);names[members['FirstFeature']]='FirstFeature'
    folders=list(Session().cut_folders(wrap('model')))
    assert [(f._oleobj_.key,kind) for f,kind in folders]==[('a','CutListFolder'),('b','CutListFolder')]
    assert ('a','GetNextFeature',1) in calls and ('a','GetNextSubFeature',1) in calls
    assert len(calls)<100
