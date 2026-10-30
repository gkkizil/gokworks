from copy import deepcopy
from pathlib import Path
from queue import Queue
from threading import Event
import pytest
from modules.dxf_dwg.sheetmetal import scan_inventory,scan_sources
from modules.dxf_dwg.inventory import display_rows,selected_items,plan_destinations
from modules.dxf_dwg.exporter import export_selection
from modules.dxf_dwg.preview.flat import read_flat
from modules.nesting.filename_parser import parse_filename
from .sheet_fakes import environment,part,assembly,component,Body


@pytest.fixture
def env(monkeypatch):return environment(monkeypatch)


def scan(env,source=None,mode='active'):
    with env[1]() as session:return scan_inventory(session,source,mode=mode)


def test_single_body_is_real_sheet_and_legacy_name_is_preserved(env,tmp_path):
    app,_,_=env;m=part(app,tmp_path/'Panel.SLDPRT');app.ActiveDoc=m
    rows,notes=scan(env)
    assert len(rows)==1 and rows[0]['exportable'] and not notes
    assert rows[0]['quantity']==1 and rows[0]['thickness_mm']==1
    targets=plan_destinations(rows,tmp_path,tmp_path/'out',('dxf',))
    assert targets[rows[0]['sheet_id']][0].name=='Panel - 1 mm - 1 adet.dxf'
    assert rows[0]['properties']['MATERIAL']['evaluated']=='S235JR'
    assert rows[0]['properties']['MATERIAL']['raw']=='$PRP:MATERIAL'
    assert app.ActiveDoc is m and not app.saves


def test_ten_sheet_bodies_and_a_mechanical_solid_are_independent(env,tmp_path):
    app,_,_=env;m=part(app,tmp_path/'Multi.SLDPRT',count=10);app.ActiveDoc=m
    m.by_config['Default'].append(Body('Mechanical',m,sheet=False))
    rows,_=scan(env)
    assert len(rows)==10 and len({r['body_ref'] for r in rows})==10
    assert sorted(r['thickness_mm'] for r in rows)==list(range(1,11))
    assert all(r['exportable'] and r['body_count']==11 for r in rows)
    assert all(r['flat_pattern'].endswith(r['body_name']) for r in rows)


def test_mixed_assembly_lists_only_sheet_and_never_scans_mechanical_features(env,tmp_path):
    app,_,calls=env
    sheet=part(app,tmp_path/'Panel.SLDPRT');mechanical=part(app,tmp_path/'Bolt.SLDPRT',sheet=False)
    mechanical.FirstFeature=lambda:pytest.fail('Mechanical part received an expensive feature scan')
    root=assembly(app,tmp_path/'Main.SLDASM',[component(sheet),component(mechanical,name='Bolt-1')]);app.ActiveDoc=root
    rows,notes=scan(env)
    assert len(rows)==1 and rows[0]['source']==sheet.path and not notes
    assert calls[(mechanical.path,'Default')]==1


def test_nested_repeated_subassemblies_count_instances_not_unique_files(env,tmp_path):
    app,_,calls=env;p=part(app,tmp_path/'Panel.SLDPRT')
    sub=assembly(app,tmp_path/'Sub.SLDASM',[component(p)])
    branches=[component(sub,name='Sub-'+str(i),children=[component(p,name='Panel-1')]) for i in range(5)]
    root=assembly(app,tmp_path/'Main.SLDASM',branches);app.ActiveDoc=root
    rows,_=scan(env)
    assert len(rows)==1 and rows[0]['quantity']==5 and len(set(rows[0]['instances']))==5
    assert calls[(p.path,'Default')]==1
    selected={rows[0]['sheet_id']:set(rows[0]['instances'])}
    assert len(display_rows(rows,selected,False))==5
    assert display_rows(rows,selected,True)[0]['quantity']==5
    selected[rows[0]['sheet_id']].pop()
    assert display_rows(rows,selected,True)[0]['selected'] is None
    assert selected_items(rows,selected)[0]['quantity']==4


def test_actual_configurations_are_separate_and_restored(env,tmp_path):
    app,_,_=env;p=part(app,tmp_path/'Panel.SLDPRT',{'A':[('Body',1.5,10)],'B':[('Body',3,30)]})
    root=assembly(app,tmp_path/'Main.SLDASM',[component(p,name='P1',configuration='A'),component(p,name='P2',configuration='B')]);app.ActiveDoc=root
    rows,_=scan(env)
    assert {(r['configuration'],r['thickness_mm'],r['quantity']) for r in rows}=={('A',1.5,1),('B',3,1)}
    assert p.active=='A' and root.active=='Default' and app.ActiveDoc is root
    paths=plan_destinations(rows,tmp_path,tmp_path/'out',('dxf',))
    assert len({str(p) for targets in paths.values() for p in targets})==2


def test_hidden_referenced_configuration_is_read_without_activating_or_showing_part(env,tmp_path):
    app,_,_=env;p=part(app,tmp_path/'Panel.SLDPRT',{'A':[('Body',1,10)],'B':[('Body',2,20)]});p.Visible=False
    root=assembly(app,tmp_path/'Main.SLDASM',[component(p,configuration='B')]);app.ActiveDoc=root
    activate=app.ActivateDoc3
    def only_visible(name,*args):
        assert name!=p.path,'Reading must not activate a hidden component'
        return activate(name,*args)
    app.ActivateDoc3=only_visible
    rows,notes=scan(env)
    assert len(rows)==1 and rows[0]['exportable'] and rows[0]['configuration']=='B' and not notes
    assert p.active=='A' and p.Visible is False and p.selection==['user selection'] and app.ActiveDoc is root


def test_hidden_referenced_configuration_exports_then_restores_visibility_and_selection(env,tmp_path):
    app,Session,_=env;p=part(app,tmp_path/'Panel.SLDPRT',{'A':[('Body',1,10)],'B':[('Body',2,20)]});p.Visible=False
    root=assembly(app,tmp_path/'Main.SLDASM',[component(p,configuration='B')]);app.ActiveDoc=root
    activate=app.ActivateDoc3
    def requires_visible(name,*args):
        if name==p.path:assert p.Visible is True
        return activate(name,*args)
    app.ActivateDoc3=requires_visible;rows,_=scan(env);events=Queue()
    export_selection(rows,tmp_path,tmp_path/'out',('dxf',),events,session_factory=Session)
    assert events.queue[-1][1]['succeeded']==1 and p.export_calls==[('B','B-Body',1)]
    assert p.active=='A' and p.Visible is False and p.selection==['user selection'] and app.ActiveDoc is root


def test_restore_failure_reports_current_body_and_completed_output_then_stops(env,tmp_path):
    app,Session,_=env;p=part(app,tmp_path/'Panel.SLDPRT',{'A':[('Body',1,10)],'B':[('Body',2,20)]})
    other=part(app,tmp_path/'Next.SLDPRT');root=assembly(app,tmp_path/'Main.SLDASM',
        [component(p,configuration='B'),component(other,name='Next')]);app.ActiveDoc=root
    rows,_=scan(env);show=p.ShowConfiguration2
    p.ShowConfiguration2=lambda name:False if name=='A' else show(name)
    events=Queue();export_selection(rows,tmp_path,tmp_path/'out',('dxf',),events,session_factory=Session)
    summary=events.queue[-1][1]
    assert summary['state']=='error' and summary['native_restore_failed'] and summary['partial']==1
    result=next(row for kind,row in events.queue if kind=='sheet_result')
    assert result['status']=='partial' and result['body_name']=='B-Body' and 'konfigürasyon' in result['detail']
    assert result['outputs'][0]['status']=='success' and Path(result['outputs'][0]['path']).is_file()
    assert not other.export_calls and not app.saves


def test_suppressed_is_ignored_and_lightweight_part_and_subassembly_open_safely(env,tmp_path):
    app,_,_=env;p=part(app,tmp_path/'Panel.SLDPRT',opened=False)
    sub=assembly(app,tmp_path/'Sub.SLDASM',[component(p)]);sub.opened=False
    root=assembly(app,tmp_path/'Main.SLDASM',[component(p,name='Suppressed',state=0),
        component(None,name='Light',path=p.path,state=1),component(None,name='Sub-Light',path=sub.path,state=1)])
    app.ActiveDoc=root;rows,notes=scan(env)
    assert len(rows)==1 and rows[0]['quantity']==2 and not notes
    assert p.path in app.open_calls and sub.path in app.open_calls
    assert not p.opened and not sub.opened and app.ActiveDoc is root and not app.saves


def test_speedpak_configuration_property_is_checked_before_reading_a_partial_tree(env,tmp_path):
    from types import SimpleNamespace as NS
    from modules.cad_converter.api import ApiError
    app,_,_=env;root=assembly(app,tmp_path/'Main.SLDASM');app.ActiveDoc=root
    class SpeedPak(type(root)):
        @property
        def ConfigurationManager(self):
            return NS(ActiveConfiguration=NS(Name=self.active,IsSpeedPak=True,
                      GetRootComponent3=lambda *args:pytest.fail('Partial SpeedPak tree must not be accepted')))
    root.__class__=SpeedPak
    with pytest.raises(ApiError,match='SpeedPak'):scan(env)


def test_unreadable_part_is_reported_without_blocking_other_parts(env,tmp_path):
    app,_,_=env;p=part(app,tmp_path/'Panel.SLDPRT')
    root=assembly(app,tmp_path/'Main.SLDASM',[component(p),component(None,name='Missing',path=str(tmp_path/'Missing.SLDPRT'))]);app.ActiveDoc=root
    rows,notes=scan(env)
    assert len(rows)==1 and rows[0]['exportable'] and rows[0]['quantity']==1
    assert notes and 'Missing' in notes[0]


def test_unreadable_subassembly_never_certifies_incomplete_quantities(env,tmp_path):
    app,_,_=env;p=part(app,tmp_path/'Panel.SLDPRT')
    root=assembly(app,tmp_path/'Main.SLDASM',[component(p),component(None,name='Missing',path=str(tmp_path/'Missing.SLDASM'))]);app.ActiveDoc=root
    rows,notes=scan(env)
    assert len(rows)==1 and not rows[0]['exportable'] and 'adet doğrulanamadı' in rows[0]['detail'] and notes


def test_broken_flat_stays_in_sheet_list_without_hiding_other_bodies(env,tmp_path):
    app,_,_=env;p=part(app,tmp_path/'Multi.SLDPRT',count=2);app.ActiveDoc=p
    p.features_by_config['Default'][-1].GetDefinition=lambda:None
    rows,notes=scan(env)
    assert len(rows)==2 and sum(r['exportable'] for r in rows)==1
    assert any('Flat-Pattern' in r['detail'] for r in rows if not r['exportable']) and notes


def test_missing_cut_list_keeps_sheet_with_real_body_thickness(env,tmp_path):
    app,_,_=env;p=part(app,tmp_path/'Panel.SLDPRT');app.ActiveDoc=p
    features=p.features_by_config['Default'];features[0].next=features[2]
    rows,_=scan(env)
    assert len(rows)==1 and rows[0]['exportable'] and rows[0]['thickness_mm']==1
    assert 'Cut List bulunamadı' in rows[0]['detail']


def test_500_occurrences_cache_classification_and_never_emit_bolts(env,tmp_path):
    app,_,calls=env;p=part(app,tmp_path/'Panel.SLDPRT');bolt=part(app,tmp_path/'Bolt.SLDPRT',sheet=False)
    root=assembly(app,tmp_path/'Main.SLDASM',[component(p if i<30 else bolt,name=f'C-{i}') for i in range(500)])
    app.ActiveDoc=root;rows,_=scan(env)
    assert len(rows)==1 and rows[0]['quantity']==30 and sum(calls.values())==2


def test_folder_and_selected_assembly_modes_classify_real_bodies(env,tmp_path):
    app,_,_=env;p=part(app,tmp_path/'P.SLDPRT');part(app,tmp_path/'Bolt.SLDPRT',sheet=False);app.ActiveDoc=p
    rows,_=scan(env,str(tmp_path),mode='folder');assert len(rows)==1
    root=assembly(app,tmp_path/'Main.SLDASM',[component(p)]);app.ActiveDoc=p
    rows,_=scan(env,root.path,mode='file');assert len(rows)==1 and app.ActiveDoc is p


def test_identity_is_idempotent_and_distinct_files_never_merge(env,tmp_path):
    app,_,_=env;a=part(app,tmp_path/'A'/'Same.SLDPRT');b=part(app,tmp_path/'B'/'Same.SLDPRT')
    root=assembly(app,tmp_path/'Main.SLDASM',[component(a,name='A'),component(b,name='B')]);app.ActiveDoc=root
    first,_=scan(env);second,_=scan(env)
    assert {r['sheet_id'] for r in first}=={r['sheet_id'] for r in second} and len(first)==2
    paths=plan_destinations(first,tmp_path/'other',tmp_path/'out',('dxf',))
    assert len({str(p) for targets in paths.values() for p in targets})==2
    with pytest.raises(ValueError,match='tekrar'):plan_destinations(first+first,tmp_path,tmp_path/'out',('dxf',))


def test_names_stay_stable_for_subsets_long_names_and_multiple_configs(env,tmp_path):
    import json
    app,_,_=env;p=part(app,tmp_path/('P'*150+'.SLDPRT'),{'A':[('Body',2,10),('Other',3,20)],'B':[('Body',2,30)]})
    root=assembly(app,tmp_path/'Main.SLDASM',[component(p,name='A',configuration='A'),component(p,name='B',configuration='B')]);app.ActiveDoc=root
    rows,_=scan(env);json.dumps(rows)  # No COM objects escape in the inventory DTO.
    all_paths=plan_destinations(rows,tmp_path,tmp_path/'out',('dxf',))
    for row in rows:
        assert plan_destinations([row],tmp_path,tmp_path/'out',('dxf',))[row['sheet_id']]==all_paths[row['sheet_id']]


def test_known_sheet_is_not_lost_when_feature_tree_cannot_be_read(env,tmp_path):
    app,_,_=env;p=part(app,tmp_path/'Panel.SLDPRT');app.ActiveDoc=p
    def broken():raise RuntimeError('feature tree RPC error')
    p.FirstFeature=broken;rows,notes=scan(env)
    assert len(rows)==1 and not rows[0]['exportable'] and notes


def test_folder_scope_keeps_active_assembly_quantities_and_discards_unused_parts(env,tmp_path):
    app,_,_=env;p=part(app,tmp_path/'Panel.SLDPRT');part(app,tmp_path/'Unused.SLDPRT')
    root=assembly(app,tmp_path/'Main.SLDASM',[component(p,name=f'P-{i}') for i in range(6)]);app.ActiveDoc=root
    rows,_=scan(env,str(tmp_path),mode='folder')
    assert len(rows)==1 and rows[0]['quantity']==6 and rows[0]['source']==p.path


def test_stopped_scan_never_emits_a_successful_partial_list(env,tmp_path):
    app,Session,_=env;app.ActiveDoc=part(app,tmp_path/'P.SLDPRT');stop=Event();stop.set();events=Queue()
    scan_sources(None,True,events,stop,mode='active',session_factory=Session)
    assert events.queue[-1][1]['state']=='cancelled' and not any(k=='sheet_inventory' for k,_ in events.queue)


@pytest.mark.parametrize('formats',[('dxf',),('dwg',),('dxf','dwg')])
def test_selected_bodies_export_isolated_geometry_and_restore_all_state(env,tmp_path,formats):
    app,Session,_=env;p=part(app,tmp_path/'Multi.SLDPRT',count=3);app.ActiveDoc=p
    before=Path(p.path).read_bytes();selection=deepcopy(p.selection);rows,_=scan(env);events=Queue()
    export_selection([rows[0],rows[2]],tmp_path,tmp_path/'out',formats,events,bend_lines=True,session_factory=Session)
    assert events.queue[-1][1]['succeeded']==2 and events.queue[-1][1]['failed']==0
    results=[r for k,r in events.queue if k=='sheet_result'];assert len(results)==2
    assert len(p.export_calls)==2*len(formats) and all('Body-1' not in name for _,name,_ in p.export_calls)
    for row in results:
        for output in row['outputs']:
            if output['format']=='DXF':
                flat=read_flat(output['path']);assert flat.bounds==(0,0,10 if row['body_name'].endswith('0') else 30,20)
                assert sum(s.bend for s in flat.strokes)==1
            parsed=parse_filename(Path(output['path']).name)
            assert parsed.quantity==1 and parsed.thickness==row['thickness_mm']
    assert p.selection==selection and p.active=='Default' and app.ActiveDoc is p
    assert Path(p.path).read_bytes()==before and not app.saves


def test_one_export_error_allows_other_parts_and_existing_files_are_preserved(env,tmp_path):
    app,Session,_=env;a=part(app,tmp_path/'A.SLDPRT');b=part(app,tmp_path/'B.SLDPRT');a.fail_export=True
    root=assembly(app,tmp_path/'Main.SLDASM',[component(a,name='A'),component(b,name='B')]);app.ActiveDoc=root
    rows,_=scan(env);events=Queue();export_selection(rows,tmp_path,tmp_path/'out',('dxf',),events,session_factory=Session)
    assert events.queue[-1][1]['failed']==1 and events.queue[-1][1]['succeeded']==1
    target=next((tmp_path/'out').glob('B*.dxf'));original=target.read_bytes();events=Queue();b.fail_export=True
    export_selection([r for r in rows if r['source']==b.path],tmp_path,tmp_path/'out',('dxf',),events,session_factory=Session)
    assert events.queue[-1][1]['skipped']==1 and target.read_bytes()==original


def test_wrong_flat_ownership_and_stale_thickness_block_export(env,tmp_path):
    app,Session,_=env;p=part(app,tmp_path/'Multi.SLDPRT',count=2);app.ActiveDoc=p
    rows,_=scan(env);wrong=dict(rows[0],flat_ref=rows[1]['flat_ref']);events=Queue()
    export_selection([wrong],tmp_path,tmp_path/'out',('dxf',),events,session_factory=Session)
    assert events.queue[-1][1]['failed']==1 and not p.export_calls
    p.by_config['Default'][0].features[0].thickness=9;events=Queue()
    export_selection([rows[0]],tmp_path,tmp_path/'out',('dxf',),events,session_factory=Session)
    assert events.queue[-1][1]['failed']==1 and not p.export_calls


def test_cancel_after_native_export_prevents_publication_and_restores_selection(env,tmp_path):
    app,Session,_=env;p=part(app,tmp_path/'Multi.SLDPRT',count=2);app.ActiveDoc=p
    rows,_=scan(env);stop=Event();p.after_export=stop.set;events=Queue()
    export_selection(rows,tmp_path,tmp_path/'out',('dxf',),events,stop,session_factory=Session)
    assert events.queue[-1][1]['state']=='cancelled' and not list((tmp_path/'out').glob('*.dxf'))
    assert p.selection==['user selection'] and app.ActiveDoc is p
