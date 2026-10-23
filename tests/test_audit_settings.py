"""Settings publication must preserve complete files and unrelated user data."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from threading import Barrier

import pytest

from shared.settings import save_settings


def test_unique_temporary_preserves_unrelated_file_and_cleans_up_on_failure(tmp_path, monkeypatch):
    path = tmp_path/'settings.json'; path.write_text('{"old":true}')
    unrelated = path.with_suffix('.tmp'); unrelated.write_text('user data')
    def fail(*args): raise OSError('disk unavailable')
    monkeypatch.setattr('shared.settings.os.replace', fail)
    with pytest.raises(OSError): save_settings({'new': 'İmalat'}, path)
    assert json.loads(path.read_text()) == {'old': True}
    assert unrelated.read_text() == 'user data'
    assert not list(tmp_path.glob('.gokworks-settings-*'))


def test_concurrent_writers_publish_only_complete_independent_files(tmp_path, monkeypatch):
    path = tmp_path/'settings.json'; gate = Barrier(2); replace = os.replace
    paths = []
    def publish(source, target):
        paths.append(source)
        gate.wait(timeout=5)
        replace(source, target)
    monkeypatch.setattr('shared.settings.os.replace', publish)
    values = [{'value': 'A'*10000}, {'value': 'B'*10000}]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda data: save_settings(data, path), values))
    assert json.loads(path.read_text()) in values
    assert len(set(paths)) == 2 and not any(p.exists() for p in paths)


def test_nonfinite_settings_never_replace_a_valid_file(tmp_path):
    path = tmp_path/'settings.json'; save_settings({'old': 1}, path)
    with pytest.raises(ValueError): save_settings({'value': float('nan')}, path)
    assert json.loads(path.read_text()) == {'old': 1}
