"""Exercise cancellation lifecycle without claiming a real CAD call was cancelled."""

import threading
import time
import os

import pytest

from modules.dxf_dwg.preview.cancellation import cancellable_read
from modules.cad_converter.models import Cancelled
from modules.cad_converter.api import ApiError, RestoreError


class CancelApi:
    def __init__(self):
        self.released = threading.Event()
        self.calls = []
    def CoInitialize(self): self.calls.append(('init', threading.get_native_id()))
    def CoUninitialize(self): self.calls.append(('uninit', threading.get_native_id()))
    def CoEnableCallCancellation(self): self.calls.append(('enable', threading.get_native_id()))
    def CoDisableCallCancellation(self): self.calls.append(('disable', threading.get_native_id()))
    def CoGetCancelObject(self, target):
        self.calls.append(('get', target))
        return self
    def Cancel(self, seconds):
        assert seconds == 0
        self.released.set()


def test_stop_requests_rpc_cancel_on_the_correct_thread_and_balances_com():
    api = CancelApi(); stop = threading.Event()
    target = threading.get_native_id()
    timer = threading.Timer(.03, stop.set); timer.start()
    try:
        with pytest.raises(Cancelled), cancellable_read(stop, api=api):
            assert api.released.wait(2)
            raise RuntimeError('Synthetic cancelled RPC; no CAD involved')
    finally:
        timer.cancel()
    assert ('get', target) in api.calls
    assert ('disable', target) in api.calls
    assert sum(k == 'init' for k, _ in api.calls) == sum(k == 'uninit' for k, _ in api.calls) == 2


def test_deadline_rejects_late_read_result():
    api = CancelApi()
    with pytest.raises(ApiError, match='süre sınırı'), cancellable_read(threading.Event(), timeout=.01, api=api):
        assert api.released.wait(2)


def test_restoration_failure_is_never_disguised_as_cancellation():
    api = CancelApi(); stop = threading.Event()
    with pytest.raises(RestoreError), cancellable_read(stop, api=api):
        stop.set()
        raise RestoreError('The real source state is not confirmed')
    assert any(k == 'disable' for k, _ in api.calls)


def test_successful_read_disarms_the_monitor_without_cancelling_future_calls():
    api = CancelApi()
    with cancellable_read(threading.Event(), api=api):
        pass
    time.sleep(.07)
    assert not api.released.is_set() and not any(k == 'get' for k, _ in api.calls)


def test_stop_before_start_makes_no_com_call():
    api = CancelApi(); stop = threading.Event(); stop.set()
    with pytest.raises(Cancelled), cancellable_read(stop, api=api):
        raise AssertionError('Not reached')
    assert not api.calls


def test_cancellation_cleanup_failure_is_fatal_and_does_not_hide_source_restore_failure():
    api = CancelApi()
    def failed(): raise RuntimeError('cancel registration cleanup failed')
    api.CoDisableCallCancellation = failed
    with pytest.raises(RestoreError, match='real source restore failed') as error:
        with cancellable_read(threading.Event(), api=api):
            raise RestoreError('real source restore failed')
    assert any('COM' in note for note in error.value.__notes__)
    with pytest.raises(RestoreError, match='COM temizliği'):
        with cancellable_read(threading.Event(), api=api):
            pass


@pytest.mark.skipif(os.name != 'nt', reason='Windows COM runtime required; no SolidWorks used.')
def test_native_windows_enables_and_disables_call_cancellation_without_cad():
    with cancellable_read(threading.Event(), timeout=2):
        pass
