"""Observe Windows process exits even when in-process crash hooks cannot run.

This helper never imports Qt or connects to CAD. It only waits on an inherited
read-only process handle and appends the exit status to the existing local log.
"""

import ctypes
from ctypes import wintypes
import ntpath
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from xml.etree import ElementTree

from . import diagnostics


WATCH_FLAG = '--process-exit-watch'
_ROLES = {'gui', 'pdf-worker'}


def _kernel32():
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'OpenProcess': ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        'GetProcessId': ([wintypes.HANDLE], wintypes.DWORD),
        'GetProcessTimes': ([wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)]*4)], wintypes.BOOL),
        'WaitForSingleObject': ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
        'GetExitCodeProcess': ([wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
        'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = arguments, result
    return api


def _command(handle, pid, role, log):
    entry = [] if getattr(sys, 'frozen', False) else [str(Path(__file__).resolve().parents[1]/'main.py')]
    return [sys.executable, *entry, WATCH_FLAG, str(handle), str(pid), role, str(log)]


def _failure(error):
    # Exceptions may contain user paths; keep only the class and Windows code.
    code = getattr(error, 'winerror', None)
    return f'error={type(error).__name__} winerror={code if isinstance(code, int) else "unknown"}'


def start_watch(pid, log, role):
    """Best effort only: a failed observer must not prevent normal application use.

    Open the process *before* spawning the helper. Inheriting this exact handle
    avoids a PID-reuse race and still permits inspection after the target exits.
    The observer has no terminate, memory read/write or CAD permissions.
    """
    if sys.platform != 'win32' or log is None:
        return None
    handle = None
    api = None
    try:
        if role not in _ROLES or pid <= 0:
            raise ValueError('Invalid process observer target')
        api = _kernel32()
        handle = api.OpenProcess(0x00100000 | 0x1000, True, pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        startup = subprocess.STARTUPINFO()
        startup.lpAttributeList = {'handle_list': [handle]}
        process = subprocess.Popen(_command(handle, pid, role, Path(log).resolve()),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True, startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW,
            env={**os.environ, 'PYINSTALLER_RESET_ENVIRONMENT': '1'})
        diagnostics.record(f'process_watch_started target={role} pid={pid} observer={process.pid}', log)
        return process
    except Exception as error:
        diagnostics.record(f'process_watch_unavailable target={role} '+_failure(error), log)
        return None
    finally:
        if handle and api is not None:
            api.CloseHandle(handle)


def _fault_details(xml, pid, created=None):
    """Accept only the target's event 1000; never persist raw event XML/paths."""
    if len(xml) > 256*1024:
        return None
    try:
        root = ElementTree.fromstring(xml)
        if root.findtext('{*}System/{*}EventID') != '1000':
            return None
        provider = root.find('{*}System/{*}Provider')
        if provider is None or provider.get('Name') != 'Application Error':
            return None
        values = {node.get('Name'): node.text or '' for node in root.findall('{*}EventData/{*}Data')}
        if int(values.get('ProcessId', ''), 0) != pid:
            return None
        if created is not None and int(values.get('ProcessCreationTime', ''), 0) != created:
            return None  # An older fault from a reused PID is not this process.
        module = ntpath.basename(values.get('ModuleName', ''))
        if not re.fullmatch(r'[\w. -]{1,100}\.(?:dll|exe|pyd)', module, re.IGNORECASE):
            module = 'unknown'
        exception = values.get('ExceptionCode', '')
        if not re.fullmatch(r'(?:0x)?[0-9a-fA-F]{1,8}', exception):
            return None
        return f'windows_application_error module={module} exception=0x{int(exception, 16):08X}'
    except (ValueError, ElementTree.ParseError):
        return None


def _application_fault(pid, created=None):
    import win32evtlog
    query = win32evtlog.EvtQuery('Application',
        win32evtlog.EvtQueryChannelPath | win32evtlog.EvtQueryReverseDirection,
        '*[System[EventID=1000 and TimeCreated[timediff(@SystemTime) <= 120000]]]')
    try:
        for _ in range(8):  # At most 128 recent errors, not the entire system log.
            events = win32evtlog.EvtNext(query, 16, 0, 0)
            if not events:
                break
            try:
                for event in events:
                    found = _fault_details(win32evtlog.EvtRender(event, win32evtlog.EvtRenderEventXml), pid, created)
                    if found:
                        return found
            finally:
                for event in events:
                    event.Close()
    finally:
        query.Close()
    return None


def run_watch(handle, pid, role, log):
    """Internal CLI: wait outside the GUI/COM processes, without a GUI thread."""
    if sys.platform != 'win32' or role not in _ROLES or handle <= 0 or pid <= 0:
        return 2
    api = _kernel32()
    try:
        if api.GetProcessId(handle) != pid:
            raise RuntimeError('Process observer handle does not match target')
        timestamps = [wintypes.FILETIME() for _ in range(4)]
        if not api.GetProcessTimes(handle, *(ctypes.byref(value) for value in timestamps)):
            raise ctypes.WinError(ctypes.get_last_error())
        created = (timestamps[0].dwHighDateTime << 32) | timestamps[0].dwLowDateTime
        diagnostics.record(f'process_watch_ready target={role} pid={pid}', log)
        if api.WaitForSingleObject(handle, 0xFFFFFFFF) != 0:  # INFINITE; sleeps in the OS, no polling.
            raise ctypes.WinError(ctypes.get_last_error())
        code = wintypes.DWORD()
        if not api.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        diagnostics.record(f'process_exit target={role} pid={pid} code={code.value} (0x{code.value:08X})', log)
        if code.value:
            # Windows Error Reporting can publish its event just after process
            # exit. This bounded wait occurs only in the observer, never the UI.
            deadline = time.monotonic()+6
            while True:
                try:
                    fault = _application_fault(pid, created)
                except Exception as error:
                    diagnostics.record('windows_application_error_unavailable '+_failure(error), log)
                    break
                if fault:
                    diagnostics.record(fault, log)
                    break
                if time.monotonic() >= deadline:
                    diagnostics.record('windows_application_error=not_found', log)
                    break
                time.sleep(.5)
        return 0
    except Exception as error:
        diagnostics.record(f'process_watch_failed target={role} '+_failure(error), log)
        return 1
    finally:
        api.CloseHandle(handle)
