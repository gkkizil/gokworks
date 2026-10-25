"""Weldment features form a graph, not a unique recursive tree."""

from threading import Event

import pytest

from modules.profile_cutting.scanner import scan, Options
from modules.profile_cutting.models import Project, transfer
from modules.profile_cutting.optimizer import optimize
from .fakes import Model, Folder, factory, component


class TreeFeature:
    def __init__(self, name, kind='FtrFolder'):
        self.Name=name;self.kind=kind
        self.child=self.top=self.sub=None

    def GetTypeName2(self):return self.kind
    def GetFirstSubFeature(self):return self.child
    def GetNextFeature(self):return self.top
    def GetNextSubFeature(self):return self.sub


def graph_model(tmp_path, first):
    model=Model(tmp_path/'Örnek_şase_.SLDPRT',configs={'Default<As Machined>':[]})
    model.FirstFeature=lambda:first
    return model


def link(folder, *, top=None, sub=None, child=None):
    folder.GetNextFeature=lambda:top
    folder.GetNextSubFeature=lambda:sub
    folder.GetFirstSubFeature=lambda:child


@pytest.mark.parametrize('repeated_chain',['top','sub','both'])
def test_repeated_cutlist_exposures_do_not_drop_the_weldment_or_multiply_bodies(tmp_path,repeated_chain):
    root=TreeFeature('Katı Gövdeler')
    first,second=Folder('Kesim-Listesi-1'),Folder('Kesim-Listesi-2')
    root.child=first;root.top=first
    link(first,top=second,sub=second)
    link(second,top=first if repeated_chain in ('top','both') else None,
         sub=first if repeated_chain in ('sub','both') else None)
    model=graph_model(tmp_path,root);session,make=factory([model],model)
    result=scan(session_factory=make)
    assert session.closed and result.unscanned==0
    assert result.scanned_parts==result.weldments==1
    assert {row.folder for row in result.rows}=={'Kesim-Listesi-1','Kesim-Listesi-2'}
    assert all(row.ready for row in result.rows)
    assert result.summary['profiles']==2 and result.summary['length']=='2000'
    project=Project();assert transfer(project,result)['added']==2
    assert sum(len(bar.cuts) for bar in optimize(project).bars)==2


def test_subfeature_and_top_level_successors_are_both_followed(tmp_path):
    root=TreeFeature('Gövdeler');first,second=Folder('A'),Folder('B')
    root.child=first;root.top=first
    link(first,top=second)
    result=scan(session_factory=factory([model:=graph_model(tmp_path,root)],model)[1])
    assert result.unscanned==0 and [r.folder for r in result.rows]==['A','B']


@pytest.mark.parametrize('reference',['collision','unavailable'])
def test_feature_reference_collision_is_not_enough_to_discard_distinct_named_folders(tmp_path,reference):
    root=TreeFeature('Gövdeler');first,second=Folder('A'),Folder('B')
    root.child=first;link(first,sub=second)
    model=graph_model(tmp_path,root)
    def persist(obj):
        if reference=='unavailable':raise RuntimeError('This feature has no persistent reference')
        return b'generic-folder-reference'
    model.Extension.GetPersistReference3=persist
    result=scan(session_factory=factory([model],model)[1])
    assert result.unscanned==0 and {r.folder for r in result.rows}=={'A','B'}


def test_feature_name_shared_by_different_kinds_does_not_hide_a_cutlist(tmp_path):
    root=TreeFeature('A','HistoryFolder');root.child=Folder('A')
    result=scan(session_factory=factory([model:=graph_model(tmp_path,root)],model)[1])
    assert result.unscanned==0 and len(result.rows)==1 and result.rows[0].ready


def test_deep_feature_structure_does_not_depend_on_python_recursion_limit(tmp_path):
    root=node=TreeFeature('Folder-0')
    for i in range(1,1200):
        node.child=TreeFeature(f'Folder-{i}');node=node.child
    node.child=Folder()
    result=scan(session_factory=factory([model:=graph_model(tmp_path,root)],model)[1])
    assert result.unscanned==0 and len(result.rows)==1 and result.rows[0].ready


def test_cutlist_update_is_applied_before_reading_its_new_subfeatures(tmp_path):
    parent=Folder('Katı Gövdeler');parent.GetTypeName2=lambda:'SolidBodyFolder'
    child=Folder('Yeni Kesim Listesi');model=graph_model(tmp_path,parent)
    parent.child=None
    def update():parent.child=child;return True
    parent.UpdateCutList=update;parent.GetFirstSubFeature=lambda:parent.child
    result=scan(options=Options(update_cut_list=True),session_factory=factory([model],model)[1])
    assert result.unscanned==0 and len(result.rows)==1 and result.rows[0].folder==child.Name


def test_cancel_during_feature_graph_walk_releases_the_session(tmp_path):
    stop=Event();root=TreeFeature('Gövdeler')
    def child():stop.set();return Folder()
    root.GetFirstSubFeature=child
    model=graph_model(tmp_path,root);session,make=factory([model],model)
    assert scan(stop=stop,session_factory=make) is None and session.closed


def test_repeated_features_in_a_reused_weldment_preserve_assembly_multiplicity(tmp_path):
    root=TreeFeature('Gövdeler');first=Folder('A');second=Folder('B')
    root.child=first;root.top=first
    link(first,top=second,sub=second);link(second,sub=first)
    part=graph_model(tmp_path,root)
    assembly=Model(tmp_path/'Montaj.SLDASM',children=[
        component(f'Şase-{i}',part.path,'Default<As Machined>') for i in range(5)])
    session,make=factory([assembly,part],assembly)
    result=scan(session_factory=make)
    assert result.unscanned==0 and result.scanned_parts==5 and result.weldments==1
    assert len(result.rows)==2 and all(row.count==5 for row in result.rows)
    assert result.summary['profiles']==10 and result.summary['length']=='10000'
    assert session.reads.count(part.path)==1


def test_pathological_unbounded_graph_is_stopped_with_a_readable_error(tmp_path,monkeypatch):
    monkeypatch.setattr('modules.profile_cutting.solidworks.MAX_FEATURE_STATES',3)
    root=node=TreeFeature('Folder-0')
    for i in range(1,6):node.child=TreeFeature(f'Folder-{i}');node=node.child
    model=graph_model(tmp_path,root)
    result=scan(session_factory=factory([model],model)[1])
    assert result.unscanned==1 and not result.rows
    assert 'güvenli tarama sınırı' in result.diagnostics[0]['detail']
