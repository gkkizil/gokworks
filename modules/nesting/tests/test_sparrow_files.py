"""Windows sharing failures are retried only for private native worker files."""
from pathlib import Path
import subprocess
import sys
import time

import pytest
from modules.nesting import sparrow, sparrow_files


def sharing_error(code=32):
    error = PermissionError(13, 'sharing violation')
    error.winerror = code
    return error


def test_transient_windows_lock_is_bounded_and_other_failures_are_not_retried(monkeypatch):
    monkeypatch.setattr(sparrow_files, 'platform', 'linux')
    pauses = []; monkeypatch.setattr(sparrow_files.time, 'sleep', pauses.append)
    attempts = []
    def locked():
        attempts.append(True)
        if len(attempts) < 3:
            raise sharing_error()
        return 'complete'
    assert sparrow_files.filesystem_call(locked) == 'complete'
    assert len(attempts) == 3 and pauses == [.01, .02]
    pauses.clear()
    def permanent():
        raise sharing_error(5)
    with pytest.raises(PermissionError):
        sparrow_files.filesystem_call(permanent)
    assert sum(pauses) == pytest.approx(.25) and len(pauses) == 5
    for error in (ValueError('invalid result'), PermissionError(13, 'ordinary permission denied'), OSError(28, 'no space')):
        pauses.clear()
        with pytest.raises(type(error)) as raised:
            sparrow_files.filesystem_call(lambda: (_ for _ in ()).throw(error))
        assert raised.value is error
        assert not pauses


def test_cleanup_retries_a_locked_result_without_discarding_success(monkeypatch, tmp_path):
    location = tmp_path/'owned-worker'; location.mkdir(); (location/'result.json').write_text('complete')
    calls = []
    class Temporary:
        name = str(location)
        def cleanup(self):
            calls.append(True)
            if len(calls) < 3:
                raise sharing_error()
            (location/'result.json').unlink(); location.rmdir()
    monkeypatch.setattr(sparrow_files, 'TemporaryDirectory', lambda **kwargs: Temporary())
    monkeypatch.setattr(sparrow_files.time, 'sleep', lambda _: None)
    with sparrow_files.workspace() as folder:
        assert (folder/'result.json').read_text() == 'complete'
    assert len(calls) == 3 and not location.exists()


@pytest.mark.parametrize('with_winerror', [True, False])
def test_parent_reaps_one_worker_then_reads_locked_snapshot_without_resolving_again(monkeypatch, with_winerror):
    monkeypatch.setattr(sparrow_files, 'platform', 'win32')
    popen = subprocess.Popen; children = []; reads = []
    def child(command, **kwargs):
        code = "import sys;from pathlib import Path;Path(sys.argv[1]).with_name('result.json').write_text('{\"ok\":true,\"placements\":[]}',encoding='utf-8')"
        process = popen([sys.executable, '-c', code, command[-1]], **kwargs)
        children.append(process); return process
    read = Path.read_text
    def locked(path, *args, **kwargs):
        if path.name == 'result.json':
            reads.append(True)
            if len(reads) < 3:
                raise sharing_error() if with_winerror else PermissionError(13, 'Permission denied')
        return read(path, *args, **kwargs)
    monkeypatch.setattr(sparrow.subprocess, 'Popen', child)
    monkeypatch.setattr(Path, 'read_text', locked)
    monkeypatch.setattr(sparrow_files.time, 'sleep', lambda _: None)
    assert sparrow._run({}, time.monotonic()+5, None) == []
    assert len(children) == 1 and children[0].poll() == 0 and len(reads) == 3


def test_persistent_windows_crt_permission_error_still_has_a_bounded_failure(monkeypatch):
    monkeypatch.setattr(sparrow_files, 'platform', 'win32')
    pauses = []
    monkeypatch.setattr(sparrow_files.time, 'sleep', pauses.append)
    error = PermissionError(13, 'Permission denied')
    with pytest.raises(PermissionError) as raised:
        sparrow_files.filesystem_call(lambda: (_ for _ in ()).throw(error))
    assert raised.value is error and sum(pauses) == pytest.approx(.25) and len(pauses) == 5
