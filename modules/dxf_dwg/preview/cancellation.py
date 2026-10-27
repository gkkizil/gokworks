"""Cooperative stop plus Windows COM call cancellation for read-only preview.

No thread/process termination and no SolidWorks ExitApp. Native servers may
refuse cancellation; state restoration is still required before the CAD lock
can be released. A restoration failure must never be disguised as cancellation.
"""

from contextlib import contextmanager
import os
import threading
import time

from modules.cad_converter.models import checkpoint, Cancelled
from modules.cad_converter.api import ApiError, RestoreError


@contextmanager
def cancellable_read(stop, *, timeout=60, api=None):
    checkpoint(stop)
    if api is None and os.name != 'nt':
        yield
        checkpoint(stop)
        return
    if api is None:
        import pythoncom as api
    api.CoInitialize()
    enabled = False
    finished = threading.Event()
    reason = []
    monitor = None
    try:
        api.CoEnableCallCancellation()
        enabled = True
        thread_id = threading.get_native_id()
        deadline = time.monotonic()+timeout
        def watch():
            api.CoInitialize()
            cancel = None
            try:
                while not finished.wait(.05):
                    requested = stop is not None and stop.is_set()
                    expired = time.monotonic() >= deadline
                    if not requested and not expired:
                        continue
                    if not reason:
                        reason.append('stop' if requested else 'timeout')
                    try:
                        cancel = api.CoGetCancelObject(thread_id)
                        cancel.Cancel(0)
                        return  # Only the pending call; never cancel cleanup RPCs repeatedly.
                    except Exception:
                        cancel = None  # No pending cancellable call yet.
            finally:
                cancel = None
                api.CoUninitialize()
        monitor = threading.Thread(target=watch, name='gokworks-preview-rpc-cancel', daemon=True)
        monitor.start()
        try:
            yield
        except RestoreError:
            raise
        except Exception:
            if reason or (stop is not None and stop.is_set()):
                if reason and reason[0] == 'timeout':
                    raise ApiError('SolidWorks önizleme çağrısı süre sınırını aştı. Açık kayıt/uyarı penceresini kontrol edip Yenile’ye basın.') from None
                raise Cancelled('Önizleme durduruldu.') from None
            raise
        if reason and reason[0] == 'timeout':
            raise ApiError('SolidWorks önizlemesi süre sınırını aştı; geciken sonuç gösterilmedi.')
        checkpoint(stop)
    finally:
        finished.set()
        if monitor is not None:
            monitor.join(.5)
        try:
            if enabled:
                api.CoDisableCallCancellation()
        finally:
            api.CoUninitialize()
