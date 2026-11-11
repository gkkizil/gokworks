"""Reject Windows device stems during pure Pack and Go planning."""
import pytest

from modules.naming.exporter import Document, Rules, Snapshot, plan_names


@pytest.mark.parametrize('stem',['CONIN$','CONOUT$','CON .part','AUX .foo','COM¹','LPT²'])
def test_pack_and_go_override_cannot_create_a_windows_device(tmp_path,stem):
    source=str(tmp_path/'Source.SLDPRT')
    snapshot=Snapshot(source,(Document(source,(),(10,1)),))
    target=tmp_path/'new-package'
    with pytest.raises(ValueError,match='Windows'):
        plan_names(snapshot,target,Rules(),{source:stem})
    assert not target.exists()


@pytest.mark.parametrize('stem',['CONSOLE','AUXILIARY','CONIN$_part','COM¹-ready'])
def test_pack_and_go_retains_regular_similar_names(tmp_path,stem):
    source=str(tmp_path/'Source.SLDPRT')
    snapshot=Snapshot(source,(Document(source,(),(10,1)),))
    result=plan_names(snapshot,tmp_path/'new-package',overrides={source:stem})
    assert result[0].destination.endswith(stem+'.SLDPRT')
