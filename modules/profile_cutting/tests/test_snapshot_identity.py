"""Malformed saved scan identities fail before reaching profile table/imports."""
from copy import deepcopy
import json

import pytest

from modules.profile_cutting.models import Project,ScanResult,ScanRow
from modules.profile_cutting.storage import load,save


def scan():
    a=ScanRow('cut-a','A.SLDPRT','Default','CutList-A',profile='40x40',material='S235JR',
              length='1000',count=1,geometry_verified=True)
    b=deepcopy(a);b.id='cut-b';b.source='B.SLDPRT';b.length='2000'
    return ScanResult('Root.SLDASM','Default',[a,b])


@pytest.mark.parametrize('identity',['','   ','cut-a'])
def test_load_rejects_empty_or_duplicate_scan_row_identities(tmp_path,identity):
    path=tmp_path/'project.gokprofile';save(Project(),scan(),path)
    data=json.loads(path.read_text());data['scan']['rows'][1]['id']=identity
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='kimlik'):
        load(path)


@pytest.mark.parametrize('identity',['','cut-a'])
def test_invalid_scan_cannot_replace_an_existing_project(tmp_path,identity):
    path=tmp_path/'project.gokprofile';save(Project(),scan(),path)
    previous=path.read_bytes();bad=scan();bad.rows[1].id=identity
    with pytest.raises(ValueError,match='kimlik'):
        save(Project(),bad,path)
    assert path.read_bytes()==previous
    assert not list(tmp_path.glob('.gokworks-*'))


def test_distinct_scans_with_same_cut_list_caption_keep_both_rows(tmp_path):
    original=scan();original.rows[1].folder=original.rows[0].folder
    path=tmp_path/'project.gokprofile';save(Project(),original,path)
    _,loaded=load(path)
    assert [(r.id,r.source,r.length) for r in loaded.rows]==[
        ('cut-a','A.SLDPRT','1000'),('cut-b','B.SLDPRT','2000')]
