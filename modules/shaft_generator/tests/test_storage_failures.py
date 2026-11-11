"""Failed writes and competing publishers must not expose corrupt projects."""
import errno
import os

import pytest

from modules.shaft_generator.models import Project
from modules.shaft_generator import storage


@pytest.mark.parametrize('overwrite',[False,True])
def test_failed_project_flush_keeps_new_target_absent_or_existing_target_intact(tmp_path,monkeypatch,overwrite):
    target=tmp_path/'Türkçe.gokshaft.json'
    if overwrite:target.write_bytes(b'previous user project')
    def full_disk(fd):raise OSError(errno.ENOSPC,'simulated full disk')
    monkeypatch.setattr(storage.os,'fsync',full_disk)
    with pytest.raises(OSError):storage.save(Project(),target,overwrite=overwrite)
    assert target.read_bytes()==b'previous user project' if overwrite else not target.exists()
    assert not list(tmp_path.glob('.shaft-*'))


def test_competing_new_project_wins_without_replacement_and_temporary_is_removed(tmp_path,monkeypatch):
    target=tmp_path/'shared.gokshaft.json'; original=os.link
    def racing(source,destination):
        target.write_bytes(b'competing user project')
        return original(source,destination)
    monkeypatch.setattr(storage.os,'link',racing)
    with pytest.raises(FileExistsError):storage.save(Project(),target)
    assert target.read_bytes()==b'competing user project'
    assert not list(tmp_path.glob('.shaft-*'))


def test_complete_exclusive_project_is_published_and_source_round_trips(tmp_path):
    target=tmp_path/'new.gokshaft.json'; project=Project()
    storage.save(project,target)
    assert storage.load(target)==project
    assert not list(tmp_path.glob('.shaft-*'))
