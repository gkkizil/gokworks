"""Real subprocess pipe/protocol tests; these do not simulate CAD geometry."""

import subprocess
import sys
import threading
import pytest
from modules.shaft_generator.bridge import _exchange


def child(source):
    return subprocess.Popen([sys.executable,'-u','-c',source],stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding='utf-8')


def test_ready_handshake_progress_and_result_are_separate_messages():
    source='''
import json,sys
print(json.dumps(dict(event='shaft_ready',protocol=1)),flush=True)
request=json.loads(input())
assert request['operation']=='create_shaft'
print(json.dumps(dict(event='shaft_phase',phase='Rebuild')),flush=True)
print(json.dumps(dict(success=True,document='TEST')),flush=True)
'''
    notices=[]
    with child(source) as process:
        result=_exchange(process,{'operation':'create_shaft'},on_status=notices.append)
    assert result==dict(success=True,document='TEST') and notices==['Rebuild']


def test_startup_timeout_kills_only_commandless_helper():
    with child('import time;time.sleep(10)') as process:
        with pytest.raises(RuntimeError,match='CAD komutu gönderilmedi'):
            _exchange(process,{'operation':'create_shaft'},startup_timeout=.02)
        assert process.poll() is not None


def test_slow_operation_reports_deadline_and_waits_for_safe_completion():
    source='''
import json,time
print(json.dumps(dict(event='shaft_ready',protocol=1)),flush=True)
input();time.sleep(.25)
print(json.dumps(dict(success=True)),flush=True)
'''
    notices=[]
    with child(source) as process:
        result=_exchange(process,{},operation_timeout=.02,diagnostic_interval=.05,on_status=notices.append)
    assert result['success'] and process.returncode==0
    assert any('süresi aşıldı' in message for message in notices)


def test_cancel_before_ready_sends_no_cad_request():
    source='''
import json,sys
print(json.dumps(dict(event='shaft_ready',protocol=1)),flush=True)
assert sys.stdin.read()==''
'''
    stop=threading.Event();stop.set()
    with child(source) as process:
        with pytest.raises(RuntimeError,match='başlamadan durduruldu'):_exchange(process,{},stop=stop)
    assert process.returncode==0


def test_host_crash_preserves_bounded_stderr_diagnostics():
    with child("import sys;print('compiler failed',file=sys.stderr);sys.exit(1)") as process:
        with pytest.raises(RuntimeError,match='compiler failed'):_exchange(process,{})
