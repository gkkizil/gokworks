"""Scope the SolidWorks out-of-process performance flag to a CAD job."""
from contextlib import contextmanager
import logging
import threading


_job = threading.local()
_logger = logging.getLogger(__name__)


def _hold_apartment():
    from ctypes import OleDLL, WinDLL
    import pythoncom

    # pywin32 can return success without taking a reference on its initializer
    # thread. Use the native API so this reference outlives the CAD session.
    release = WinDLL('ole32').CoUninitialize
    release.restype = None
    OleDLL('ole32').CoInitializeEx(None, pythoncom.COINIT_APARTMENTTHREADED)
    return release


class _SpeedScope:
    def __init__(self):
        self.app = None
        self.release = None

    def enable(self, dispatch):
        if self.app is not None:
            return
        from win32com.client.dynamic import Dispatch

        # Keep a COM reference until after the operation's own CoUninitialize.
        # CoInitializeEx either takes a reference or raises; only balance success.
        release = _hold_apartment()
        try:
            app = Dispatch(dispatch)
            self.previous = bool(app.CommandInProgress)
            if not self.previous:
                app.CommandInProgress = True
        except Exception:
            release()
            raise
        self.app, self.release = app, release

    def close(self):
        if self.app is None:
            return
        try:
            if not self.previous:
                self.app.CommandInProgress = False
        except Exception:
            _logger.warning('Could not restore SolidWorks CommandInProgress', exc_info=True)
        finally:
            self.app = None
            self.release()


@contextmanager
def cad_job():
    """Prepare a scope without opening or probing SolidWorks for non-CAD jobs."""
    if getattr(_job, 'scope', None) is not None:
        yield
        return
    _job.scope = scope = _SpeedScope()
    try:
        yield
    finally:
        del _job.scope
        scope.close()


def enable_for(dispatch):
    scope = getattr(_job, 'scope', None)
    if scope is not None:
        try:
            scope.enable(dispatch)
        except Exception:
            _logger.debug('SolidWorks API speed flag unavailable', exc_info=True)
