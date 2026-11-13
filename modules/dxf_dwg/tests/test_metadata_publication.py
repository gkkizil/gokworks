"""Manufacturing tags must survive Save3/native export until publication."""
import pytest
from .test_selection_autosave import case as case, run

@pytest.mark.parametrize('kind',['thickness','material'])
@pytest.mark.parametrize('timing',['save','native-export'])
@pytest.mark.parametrize('formats',[('dxf',),('dwg',),('dxf','dwg')])
def test_metadata_changes_during_native_operations_cannot_publish_a_stale_filename(case,kind,timing,formats):
    c=case
    def mutate():
        if kind=='thickness':c.model.by_config['Default'][0].features[0].thickness=7
        else:c.model.features_by_config['Default'][1].CustomPropertyManager.values['MATERIAL']='S355JR'
    if timing=='save':
        c.model.Extension.NeedsRebuild2=True
        def rebuilt():
            c.model.Extension.NeedsRebuild2=False;c.model.dirty=True;return True
        c.model.EditRebuild3=rebuilt
        save=c.model.Save3
        def update(*args):mutate();return save(*args)
        c.model.Save3=update
    else:c.model.after_export=mutate
    result=run(c,rows=c.rows[:1],formats=formats)
    rows=[r for k,r in c.events if k=='sheet_result']
    assert result['succeeded']==0 and result['failed']==1, rows
    assert rows[0]['status']=='error' and 'değişmiş' in rows[0]['detail'], rows
    assert not list(c.output.rglob('*.dxf')) and not list(c.output.rglob('*.dwg'))
    assert c.model.active=='Default' and c.model.selection==['user selection']


@pytest.mark.parametrize('path',['full','direct'])
def test_metadata_validation_restore_error_stops_before_any_output_is_published(case,path):
    from modules.cad_converter.api import RestoreError
    c=case;describe=c.session.describe;calls=[]
    def check(session,*args,**kwargs):
        calls.append(True)
        if len(calls)==2:raise RestoreError('final validation restore refused')
        return describe(session,*args,**kwargs)
    if path=='full':
        c.model.GetUpdateStamp=lambda:None
        c.session.describe=check
    else:
        def failed(*args):raise RestoreError('final validation restore refused')
        c.session.manufacturing_metadata=failed
    result=run(c,formats=('dxf','dwg'))
    assert result['state']=='error' and result['native_restore_failed']
    assert len(c.model.export_calls)==1 and not list(c.output.rglob('*.dxf'))
    assert not list(c.output.rglob('*.dwg'))


def test_second_format_metadata_change_keeps_only_the_already_verified_first_output(case):
    c=case
    def change():
        if len(c.model.export_calls)==2:c.model.by_config['Default'][0].features[0].thickness=7
    c.model.after_export=change
    result=run(c,rows=c.rows[:1],formats=('dxf','dwg'))
    assert result['partial']==1 and result['succeeded']==0
    assert len(list(c.output.rglob('*.dxf')))==1 and not list(c.output.rglob('*.dwg'))
