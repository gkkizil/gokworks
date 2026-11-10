"""Windows keeps a just-replaced/killed writer's result file locked briefly; reading must not fail the layout."""
import json
from pathlib import Path
import pytest
from modules.nesting import sparrow


class FakeChild:
    def __init__(self, command, **kwargs):
        request = Path(command[-1]); self.returncode = 0
        request.with_name('result.json').write_text(json.dumps(dict(ok=True, placements=[dict(id='a', x=0, y=0, angle=0)])), encoding='utf-8')
    def poll(self): return 0
    def wait(self, timeout=None): return 0
    def kill(self): pass


def locked(times, monkeypatch):
    real = Path.read_text; calls = []
    def read_text(self, *args, **kwargs):
        if self.name == 'result.json' and len(calls) < times:
            calls.append(1)
            error = PermissionError(13, 'Permission denied', str(self))
            error.winerror = 32
            raise error
        return real(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read_text)
    monkeypatch.setattr(sparrow.subprocess, 'Popen', FakeChild)
    return calls


def test_a_briefly_locked_result_is_read_after_a_short_retry(monkeypatch):
    calls = locked(3, monkeypatch)
    rows = sparrow._run(dict(items=[]), deadline=float('inf'), stop=None)
    assert rows == [dict(id='a', x=0, y=0, angle=0)] and len(calls) == 3


def test_a_result_that_stays_locked_is_a_clear_error_not_a_crash(monkeypatch):
    locked(10**6, monkeypatch); monkeypatch.setattr(sparrow.time, 'sleep', lambda s: None)
    with pytest.raises(ValueError, match='kilitli'):
        sparrow._run(dict(items=[]), deadline=float('inf'), stop=None)


def test_an_interrupted_run_with_a_locked_snapshot_has_no_snapshot(monkeypatch):
    import threading
    locked(10**6, monkeypatch); monkeypatch.setattr(sparrow.time, 'sleep', lambda s: None)
    class Running(FakeChild):
        def poll(self): return None if not self.killed else -9
        def __init__(self, command, **kwargs): super().__init__(command); self.killed = False
        def kill(self): self.killed = True
        def wait(self, timeout=None): return -9
    monkeypatch.setattr(sparrow.subprocess, 'Popen', Running)
    stop = threading.Event(); stop.set()
    assert sparrow._run(dict(items=[]), deadline=float('inf'), stop=stop) is None
