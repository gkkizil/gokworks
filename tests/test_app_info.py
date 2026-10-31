import json

import pytest

from shared import app_info


@pytest.mark.parametrize('kind',['loose','packed','detached','worktree'])
def test_revision_reads_the_actual_git_layout_without_a_git_executable(tmp_path,kind):
    root=tmp_path/'project';root.mkdir();git=root/'.git';git.mkdir();revision='a'*40
    if kind=='detached':(git/'HEAD').write_text(revision)
    else:
        ref='refs/heads/üretim'
        (git/'HEAD').write_text('ref: '+ref,encoding='utf-8')
        if kind=='packed':(git/'packed-refs').write_text(revision+' '+ref+'\n',encoding='utf-8')
        elif kind=='worktree':
            actual=tmp_path/'git-dir';git.rename(actual);(root/'.git').write_text('gitdir: '+str(actual))
            common=tmp_path/'common';common.mkdir();(actual/'commondir').write_text('../common')
            (common/'packed-refs').write_text(revision+' '+ref,encoding='utf-8')
        else:
            path=git/ref;path.parent.mkdir(parents=True);path.write_text(revision)
    assert app_info.source_revision(root)==revision


def test_source_version_does_not_use_metadata_from_an_old_exe_release(monkeypatch):
    monkeypatch.setattr(app_info,'source_revision',lambda:'b'*40)
    assert app_info.version_text()=='Kaynak revizyonu bbbbbbbb'


def test_packaged_version_comes_from_its_embedded_build_revision(tmp_path,monkeypatch):
    monkeypatch.setattr(app_info,'ROOT',tmp_path);monkeypatch.setattr(app_info.sys,'frozen',True,raising=False)
    (tmp_path/'build').mkdir();(tmp_path/'build/application-info.json').write_text(json.dumps(dict(schema=1,revision='c'*40)))
    assert app_info.version_text()=='Derleme revizyonu cccccccc'
    (tmp_path/'build/application-info.json').unlink()
    assert app_info.version_text()=='Paket sürüm bilgisi bulunamadı'
