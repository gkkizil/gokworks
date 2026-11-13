"""Native call budgets and safe fallbacks; controlled COM, not live SW timing."""
from collections import Counter

import pytest

from modules.dxf_dwg import exporter as ex
from modules.dxf_dwg.sheetmetal import scan_inventory
from .test_selection_autosave import alternate, case as case, run
from .sheet_fakes import part


def many_bodies(c,count):
    model=c.model;fresh=part(c.app,model.path,count=count)
    model.by_config=fresh.by_config;model.features_by_config=fresh.features_by_config
    c.app.models[model.path]=model
    for bodies in model.by_config.values():
        for body in bodies:body.model=model
    with c.session() as session:c.rows,_=scan_inventory(session)


@pytest.mark.parametrize('formats',[('dxf',),('dxf','dwg')])
def test_stable_multibody_export_does_not_repeat_whole_tree_validation_per_format(case,monkeypatch,formats):
    c=case;many_bodies(c,12);calls=Counter();features=c.session.features
    def walk(session,*args,**kwargs):
        calls['tree']+=1;yield from features(session,*args,**kwargs)
    monkeypatch.setattr(c.session,'features',walk)
    save=ex.save_modified_documents
    def sweep(*args,**kwargs):calls['save_sweeps']+=1;return save(*args,**kwargs)
    monkeypatch.setattr(ex,'save_modified_documents',sweep)
    assert run(c,formats=formats)['succeeded']==12
    assert calls['tree']==12  # One complete initial validation per selected body.
    assert calls['save_sweeps']==1+12*(len(formats)+1)
    assert len(c.model.export_calls)==12*len(formats)
    assert not c.model.dirty and not c.root.dirty and c.app.ActiveDoc is c.root


def test_unmodified_unrelated_documents_need_no_path_reads_during_save_sweeps(case,tmp_path):
    c=case
    for i in range(40):
        doc=c.app.add(tmp_path/f'Unrelated-{i}.SLDPRT',opened=True);c.install(doc)
        def forbidden():raise AssertionError('unnecessary clean-document path query')
        doc.GetPathName=forbidden
    assert run(c)['succeeded']==3


@pytest.mark.parametrize('formats',[('dxf',),('dxf','dwg')])
def test_configuration_restore_is_saved_once_after_all_formats(case,formats):
    c=case;alternate(c)
    assert run(c,formats=formats)['succeeded']==1
    saves=[config for path,config in c.calls if path==c.model.path]
    assert saves==['B']*len(formats)+['A']
    assert c.model.active=='A' and not c.model.dirty and not c.root.dirty


def test_each_native_dxf_is_parsed_once_for_audit_and_curve_validation(case,monkeypatch):
    reads=[];read=ex.ezdxf.readfile
    def measured(path,*args,**kwargs):reads.append(path);return read(path,*args,**kwargs)
    monkeypatch.setattr(ex.ezdxf,'readfile',measured)
    assert run(case)['succeeded']==3
    assert len(reads)==3


def test_inventory_reads_shared_document_revision_once_for_all_bodies(case,monkeypatch):
    c=case;many_bodies(c,15);seen=[];identity=ex.preview_identity
    def measured(model,body):seen.append(body);return identity(model,body)
    monkeypatch.setattr(ex,'preview_identity',measured)
    with c.session() as session:rows,_=scan_inventory(session)
    assert len(rows)==15 and seen==[None]
    assert len({row['body_ref'] for row in rows})==15
    assert all(row['source_stamp']==rows[0]['source_stamp'] for row in rows)


@pytest.mark.parametrize('fallback',['unknown-stamp','changed-stamp','stamp-type-change','flat-rename','cut-rename','rebuild'])
def test_changed_or_uncertain_native_state_uses_complete_validation(case,monkeypatch,fallback):
    c=case;calls=[];describe=c.session.describe;stamp=[10]
    c.model.GetUpdateStamp=lambda:None if fallback=='unknown-stamp' else stamp[0]
    def checked(session,*args,**kwargs):calls.append(True);return describe(session,*args,**kwargs)
    monkeypatch.setattr(c.session,'describe',checked)
    def changed():
        if fallback=='changed-stamp':stamp[0]+=1
        elif fallback=='stamp-type-change':stamp[0]=float(stamp[0])
        elif fallback=='flat-rename':c.model.features_by_config['Default'][2].Name='RenamedFlat'
        elif fallback=='cut-rename':c.model.features_by_config['Default'][1].Name='RenamedCut'
        elif fallback=='rebuild':c.model.Extension.NeedsRebuild2=True
    def rebuild():c.model.Extension.NeedsRebuild2=False;return True
    c.model.EditRebuild3=rebuild;c.model.after_export=changed
    result=run(c,rows=c.rows[:1])
    assert result['succeeded']==1 and len(calls)==2


@pytest.mark.parametrize('failure',['flat-owner','duplicate-body'])
def test_direct_validation_cannot_accept_a_changed_body_or_flat_owner(case,failure):
    c=case
    def changed():
        bodies=c.model.by_config['Default']
        if failure=='flat-owner':c.model.features_by_config['Default'][2].body=bodies[1]
        else:bodies[1].ref=bodies[0].ref
    c.model.after_export=changed
    result=run(c,rows=c.rows[:1])
    assert result['succeeded']==0 and result['failed']==1
    assert not list(c.output.rglob('*.dxf'))


def test_exporter_still_saves_its_own_opened_document_before_closing_it(case):
    c=case;c.model.opened=False;c.model.Visible=False;outputs=[]
    with c.session() as session:
        session.save_modified=True
        status,detail=ex.export_one_part(session.app,c.model.path,[c.output/'one.dxf'],
            sheet=c.rows[0],selection_session=session,save_modified=True,session_managed_save=True,
            output_results=outputs)
    assert status=='success',detail
    assert c.calls and not c.model.dirty and not c.root.dirty and not c.model.opened
    assert outputs[0]['status']=='success' and c.root.opened


def test_direct_validation_reacquires_bodies_after_flat_definition_access(case,monkeypatch):
    from .sheet_fakes import Body
    c=case;retired=[];full=[];describe=c.session.describe
    reference=c.session.flat_body_reference
    class Retired(Body):
        def __getattribute__(self,name):
            if name in ('ref','GetFeatures','GetMaterialPropertyName2','IsSheetMetal'):
                raise RuntimeError('IBody2 retired after ReleaseSelectionAccess')
            return super().__getattribute__(name)
    def checked(session,*args,**kwargs):full.append(True);return describe(session,*args,**kwargs)
    def scope(session,model,feature):
        result=reference(session,model,feature)
        if c.model.export_calls and not retired:
            old=list(model.by_config['Default']);fresh=[]
            for body in old:
                item=Body(body.Name,model,body.sheet,body.width,body.thickness)
                item.ref=body.ref;item.features=body.features;fresh.append(item)
            for feature in model.features_by_config['Default']:
                feature.body=fresh[old.index(feature.body)]
            model.by_config['Default']=fresh
            for body in old:body.__class__=Retired
            retired.append(True)
        return result
    monkeypatch.setattr(c.session,'describe',checked)
    monkeypatch.setattr(c.session,'flat_body_reference',scope)
    assert run(c,rows=c.rows[:1])['succeeded']==1
    assert retired and len(full)==1
