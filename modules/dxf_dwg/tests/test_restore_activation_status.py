"""Native activation warning is not a failed restore; real errors stay fatal."""

import pytest

from modules.cad_converter import api
from modules.dxf_dwg.preview import solidworks as sw
from .test_preview_source import source as source
from .test_preview_autosave import saving as saving, read


def activation_status(case,code,*,wrong_active=False,wrong_return=False,stage=None):
    previous=case.app.ActiveDoc
    activate=case.app.ActivateDoc3
    calls=[]
    def operation(name,preferences,option,errors):
        result=activate(name,preferences,option,errors)
        if name==previous.path:
            calls.append(name)
            if stage is None or len(calls)==stage:
                errors.value=code
                if wrong_active:case.app.ActiveDoc=case.model
                if wrong_return:result=case.model
        return result
    case.app.ActivateDoc3=operation
    return previous


def test_preview_with_verified_parent_rebuild_warning_returns_final_mesh_and_flat(saving):
    case=saving;previous=activation_status(case,2)  # swDocNeedsRebuildWarning, published enum.
    result=read(case)
    assert result.flat and result.mesh.triangles==1
    assert case.app.ActiveDoc is previous and case.model.active=='Bent'
    assert result.revision[1]==sw.file_stamp(case.model.path)


@pytest.mark.parametrize('code',[1,3,4,-1])
@pytest.mark.parametrize('stage',[1,2],ids=['native-export','session-exit'])
def test_real_and_combined_activation_errors_still_block_preview(saving,code,stage):
    activation_status(saving,code,stage=stage)
    with pytest.raises(api.RestoreError):read(saving)


@pytest.mark.parametrize('fault',['active','return'])
@pytest.mark.parametrize('stage',[1,2],ids=['native-export','session-exit'])
def test_rebuild_warning_does_not_excuse_a_wrong_restored_document(saving,fault,stage):
    activation_status(saving,2,wrong_active=fault=='active',wrong_return=fault=='return',stage=stage)
    with pytest.raises(api.RestoreError):read(saving)
