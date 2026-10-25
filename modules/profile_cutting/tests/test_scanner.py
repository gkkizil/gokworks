from copy import deepcopy
from dataclasses import replace
from queue import Queue
from threading import Event

import pytest

from modules.profile_cutting.scanner import scan, Options
from modules.profile_cutting.models import Project, Demand, transfer
from modules.profile_cutting.optimizer import optimize, validate_plan
from modules.cad_converter.api import RestoreError
from .fakes import Model, Folder, Body, component, factory


def read(model, others=(), options=Options(), events=None):
    session, make = factory([model,*others],model)
    result=scan(options=options,events=events,session_factory=make)
    assert session.closed
    return result, session


def test_single_weldment_keeps_resolved_and_raw_properties_without_saving(tmp_path):
    model=Model(tmp_path/'frame.SLDPRT',[Folder()])
    result,_=read(model)
    row=result.rows[0]
    assert row.ready and row.length=='1000' and row.count==1
    assert row.properties['LENGTH'].raw=='$PRP:LENGTH'
    assert row.properties['LENGTH'].evaluated=='1000'
    assert row.body_refs and result.summary['profiles']==1


def test_integer_fully_rebuilt_status_does_not_block_a_valid_weldment(tmp_path):
    model=Model(tmp_path/'Şase.SLDPRT',[Folder()])
    model.Extension.NeedsRebuild2=0  # Actual IModelDocExtension return: Int32 enum, not bool.
    result,_=read(model)
    assert result.rows[0].ready and not result.rows[0].issues


def test_integer_fully_rebuilt_assembly_does_not_invalidate_its_weldment_instances(tmp_path):
    part=Model(tmp_path/'Şase.SLDPRT',[Folder()]);part.Extension.NeedsRebuild2=0
    root=Model(tmp_path/'Montaj.SLDASM',children=[component('Şase-1',part.path)])
    root.Extension.NeedsRebuild2=0
    result,_=read(root,[part])
    assert result.rows[0].ready and result.unscanned==0


def test_multi_body_and_different_sections_and_lengths_are_not_combined(tmp_path):
    folders=[Folder('A',[Body('a'),Body('b')]),
             Folder('B',[Body('c',500)],{'LENGTH':'500'}),
             Folder('C',[Body('d')],{'DESCRIPTION':'50×30×2'})]
    result,_=read(Model(tmp_path/'multi.SLDPRT',folders))
    assert [r.count for r in result.rows]==[2,1,1]
    project=Project(); assert transfer(project,result)['added']==3
    assert len({r.group for r in project.demands})==2
    plan=optimize(project);validate_plan(project,plan)
    assert sum(len(b.cuts) for b in plan.bars)==4


def test_five_assembly_instances_are_counted_but_part_is_scanned_once(tmp_path):
    part=Model(tmp_path/'part.SLDPRT',[Folder(bodies=[Body('A'),Body('B')])])
    assembly=Model(tmp_path/'root.SLDASM',children=[component(f'part-{i}',part.path) for i in range(5)])
    result,session=read(assembly,[part])
    assert result.rows[0].count==10 and len(result.rows[0].occurrences)==5
    assert result.scanned_parts==5 and result.weldments==1
    assert session.reads.count(part.path)==1
    assert result.summary['length']=='10000'
    project=Project();transfer(project,result)
    assert sum(len(b.cuts) for b in optimize(project).bars)==10


def test_recursive_subassembly_multiplicity_and_suppressed_lightweight(tmp_path):
    part=Model(tmp_path/'p.SLDPRT',[Folder()])
    sub=Model(tmp_path/'s.SLDASM',children=[component('p-1',part.path),component('p-2',part.path,state=1),component('off',part.path,state=0)])
    root=Model(tmp_path/'r.SLDASM',children=[component('s-1',sub.path),component('s-2',sub.path)])
    result,_=read(root,[sub,part])
    assert result.rows[0].count==4 and result.unscanned==0
    assert sum('Suppressed' in v['detail'] for v in result.diagnostics)==2
    assert sum('Lightweight' in v['detail'] for v in result.diagnostics)==2


def test_referenced_configurations_stay_separate_and_original_is_restored(tmp_path):
    part=Model(tmp_path/'p.SLDPRT',configs={'A':[Folder()], 'B':[Folder(properties={'LENGTH':'500'},bodies=[Body('short',500)])]})
    root=Model(tmp_path/'r.SLDASM',children=[component('p-A',part.path,'A'),component('p-B',part.path,'B')])
    result,_=read(root,[part])
    assert {(r.configuration,r.length) for r in result.rows}=={('A','1000'),('B','500')}
    assert part.ConfigurationManager.ActiveConfiguration.Name=='A'


@pytest.mark.parametrize('properties', [{'LENGTH':''},{'LENGTH':'bad'},{'QUANTITY':'5'},{'Angle1':'45'},{'MATERIAL':''},{'DESCRIPTION':'Profile'}])
def test_missing_and_conflicting_properties_and_miter_are_blocked(tmp_path,properties):
    result,_=read(Model(tmp_path/'p.SLDPRT',[Folder(properties=properties)]))
    assert not result.rows[0].ready
    project=Project();stats=transfer(project,result)
    assert stats['blocked']==1 and project.demands==[]


def test_geometry_fallback_is_explicit_and_never_uses_aabb(tmp_path):
    model=Model(tmp_path/'p.SLDPRT',[Folder(properties={'LENGTH':''})])
    result,_=read(model)
    assert not result.rows[0].ready and result.rows[0].length==''
    result,_=read(model,options=Options(geometry_length=True))
    assert result.rows[0].ready and result.rows[0].length=='1000.000'
    assert 'geometrisi' in result.rows[0].length_source


def test_curves_and_sheet_or_non_weldment_bodies_are_not_accepted(tmp_path):
    folders=[Folder('curve',[Body('curved',curved=True)]),Folder('sheet',[Body('sheet',sheet=True)]),Folder('solid',kind=1)]
    result,_=read(Model(tmp_path/'p.SLDPRT',folders))
    assert not any(r.ready for r in result.rows)
    assert [r.excluded for r in result.rows]==[False,True,True]


def test_stale_cutlist_requires_choice_and_never_changes_update_settings(tmp_path):
    folder=Folder();folder.automatic=False
    model=Model(tmp_path/'p.SLDPRT',[folder])
    result,_=read(model)
    assert not result.rows[0].ready and folder.updated==0
    result,_=read(model,options=Options(update_cut_list=True))
    assert result.rows[0].ready and folder.updated==1 and folder.automatic is False
    model.Extension.NeedsRebuild2=True
    result,_=read(model,options=Options(update_cut_list=True))
    assert not result.rows[0].ready


def test_duplicate_body_in_two_folders_is_not_imported_twice(tmp_path):
    body=Body('same')
    result,_=read(Model(tmp_path/'p.SLDPRT',[Folder('A',[body]),Folder('B',[body])]))
    assert result.rows[0].ready and not result.rows[1].ready
    project=Project();transfer(project,result)
    assert sum(r.count for r in project.demands)==1


def test_repeat_scan_preserves_manual_entries_and_changed_sources_are_not_overwritten(tmp_path):
    model=Model(tmp_path/'p.SLDPRT',[Folder()])
    result,_=read(model)
    manual=Demand('manual','50×30×2','S355JR','1200',3)
    project=Project([manual]);assert transfer(project,result)['added']==1
    again,_=read(model);assert transfer(project,again)['duplicate']==1
    again.rows[0].material='S355JR'
    assert transfer(project,again)['changed']==1
    assert len(project.demands)==2 and project.demands[0] is manual
    assert project.demands[1].material=='S235JR'


def test_miter_manual_review_requires_note_and_keeps_angles_and_allowance(tmp_path):
    result,_=read(Model(tmp_path/'p.SLDPRT',[Folder(properties={'Angle1':'45'})]))
    row=result.rows[0];row.reviewed=True
    assert not row.ready
    row.review_note='Uzun uç 1000 mm; testere açısı üretim resminden kontrol edildi.'
    row.allowance='25'
    assert row.ready
    project=Project();transfer(project,result)
    demand=project.demands[0]
    assert demand.angle1=='45' and demand.allowance=='25'
    cut=optimize(project).bars[0].cuts[0]
    assert cut.consumption=='1028' and cut.angle1=='45' and cut.note==row.review_note


def test_missing_configuration_and_no_cutlist_are_reported(tmp_path):
    part=Model(tmp_path/'p.SLDPRT')
    root=Model(tmp_path/'r.SLDASM',children=[component('bad',part.path,'Missing'),component('ok',part.path)])
    result,_=read(root,[part])
    assert result.unscanned==1 and result.rows==[]
    assert any('konfigürasyon' in d['detail'] for d in result.diagnostics)
    assert any('Cut List bulunamadı' in d['detail'] for d in result.diagnostics)


def test_cancellation_keeps_previous_result_and_emits_no_incomplete_scan(tmp_path):
    model=Model(tmp_path/'p.SLDPRT',[Folder()]);events=Queue();stop=Event();stop.set()
    session,make=factory([model],model)
    assert scan(events=events,stop=stop,session_factory=make) is None
    assert not any(k=='weldment_scan' for k,v in list(events.queue)) and session.closed


def test_renamed_cutlist_folder_does_not_add_the_same_bodies_again(tmp_path):
    folder=Folder();model=Model(tmp_path/'p.SLDPRT',[folder])
    first,_=read(model);project=Project();transfer(project,first)
    folder.Name='Renamed Cut List'
    again,_=read(model)
    assert first.rows[0].id==again.rows[0].id
    assert transfer(project,again)['changed']==1 and len(project.demands)==1


def test_regrouped_cutlist_bodies_are_not_counted_again_until_old_import_is_removed(tmp_path):
    a,b=Body('a'),Body('b')
    model=Model(tmp_path/'p.SLDPRT',[Folder('Together',[a,b])])
    first,_=read(model);project=Project();transfer(project,first)
    model.configs['Default']=[Folder('A',[a]),Folder('B',[b])]
    again,_=read(model)
    stats=transfer(project,again)
    assert stats['changed']==2 and stats['added']==0 and sum(d.count for d in project.demands)==2
    project.demands.clear()
    assert transfer(project,again)['added']==2 and sum(d.count for d in project.demands)==2
