"""Internal, typed SolidWorks interop fallback for broken Automation getters.

The user's installed interop DLL stays on their machine. A short-lived STA
PowerShell/.NET client owns only a Pack and Go object, never CAD documents.
"""

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading


HOST_SOURCE = Path(__file__).with_name('interop') / 'PackAndGoHost.cs'
FLAGS = frozenset(('IncludeDrawings', 'IncludeSuppressed', 'IncludeToolboxComponents',
                   'IncludeSimulationResults', 'FlattenToSingleFolder'))
TEXTS = frozenset(('AddPrefix', 'AddSuffix'))
# Paths are environment values, never interpolated into PowerShell source.
LOADER = r"""$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
try {
    $interop = $env:GOKWORKS_PACKANDGO_INTEROP
    [Reflection.Assembly]::LoadFrom($interop) | Out-Null
    Add-Type -TypeDefinition ([IO.File]::ReadAllText($env:GOKWORKS_PACKANDGO_HOST)) -ReferencedAssemblies @($interop, 'System.Web.Extensions.dll') -ErrorAction Stop
    [Gokworks.PackAndGoInterop.Host]::Run()
} catch {
    [Console]::WriteLine((@{ok=$false; error=$_.Exception.Message} | ConvertTo-Json -Compress))
    exit 1
}
"""


def _installed_interop(process_id):
    """Resolve the DLL beside this exact running SW executable, not another year."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                                 wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, process_id)  # QUERY_LIMITED_INFORMATION
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wintypes.DWORD(32768)
        filename = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, filename, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        executable = Path(filename.value)
    finally:
        kernel.CloseHandle(handle)
    if executable.name.casefold() != 'sldworks.exe':
        raise RuntimeError('SolidWorks işlem kimliği doğrulanamadı.')
    for directory in (executable.parent / 'api' / 'redist', executable.parent):
        library = directory / 'SolidWorks.Interop.sldworks.dll'
        if library.is_file():
            return library
    raise RuntimeError('SolidWorks kurulumunda api/redist/SolidWorks.Interop.sldworks.dll bulunamadı. '
                       'SolidWorks API bileşeninin kurulumu gerekli.')


class Client:
    def __init__(self, process_id, source, library):
        if not HOST_SOURCE.is_file():
            raise RuntimeError('Gömülü Pack and Go interop kaynağı pakette bulunamadı.')
        system_root = Path(os.environ.get('SystemRoot', r'C:\Windows'))
        powershell = system_root / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        if not powershell.is_file():
            raise RuntimeError('Windows PowerShell 5.1 bulunamadı.')
        self.closed = False
        self.responses = queue.Queue()
        self.process = subprocess.Popen(
            [str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-STA', '-Command', LOADER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            encoding='utf-8', errors='strict', bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW,
            env={**os.environ, 'GOKWORKS_PACKANDGO_INTEROP': str(library),
                 'GOKWORKS_PACKANDGO_HOST': str(HOST_SOURCE)},
        )
        self.reader = threading.Thread(target=self._read, daemon=True, name='gokworks-packandgo-interop')
        self.reader.start()
        try:
            self._send(dict(process_id=process_id, source=source))
            ready = self._response(timeout=60)
            if ready.get('backend') != 'SolidWorks .NET interop' or ready.get('process_id') != process_id:
                raise RuntimeError('Pack and Go interop oturumu doğrulanamadı.')
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                self.responses.put(json.loads(line))
        except Exception as error:
            self.responses.put(error)
        finally:
            self.responses.put(None)

    def _send(self, request):
        self.process.stdin.write(json.dumps(request, ensure_ascii=False, allow_nan=False) + '\n')
        self.process.stdin.flush()

    def _response(self, timeout=None):
        try:
            reply = self.responses.get(timeout=timeout)
        except queue.Empty as error:
            raise RuntimeError('Pack and Go interop istemcisi başlatılamadı; bekleme süresi doldu.') from error
        if reply is None:
            raise RuntimeError('Pack and Go interop bağlantısı beklenmedik şekilde kapandı.')
        if isinstance(reply, Exception):
            raise RuntimeError('Pack and Go interop yanıtı okunamadı.') from reply
        if not isinstance(reply, dict) or reply.get('ok') is not True:
            message = reply.get('error', 'Geçersiz interop yanıtı.') if isinstance(reply, dict) else 'Geçersiz interop yanıtı.'
            raise RuntimeError('SolidWorks .NET interop: ' + str(message))
        return reply

    def request(self, operation, **values):
        if self.closed:
            raise RuntimeError('Pack and Go interop oturumu kapalı.')
        try:
            self._send(dict(operation=operation, **values))
        except OSError as error:
            raise RuntimeError('Pack and Go interop bağlantısı koptu.') from error
        # Like a direct COM call, saving is not forcibly interrupted. Cancellation
        # is checked by the engine before/after the call, never by killing SW.
        return self._response().get('result')

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.process.poll() is None:
                try:
                    self._send(dict(operation='close'))
                except (OSError, ValueError):
                    pass
            try:
                self.process.stdin.close()
            except OSError:
                pass
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()  # only our client; never sldworks.exe
                self.process.wait(timeout=5)
        finally:
            self.reader.join(timeout=2)
            self.process.stdout.close()


class Pack:
    """Expose the engine's small Pack and Go surface through the typed host."""
    def __init__(self, client):
        object.__setattr__(self, '_client', client)

    def __getattr__(self, name):
        if name in FLAGS:
            return self._client.request('get_flag', name=name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in FLAGS:
            if type(value) is not bool:
                raise TypeError('Pack and Go bayrağı boolean olmalı.')
            self._client.request('set_flag', name=name, value=value)
        elif name in TEXTS:
            if not isinstance(value, str):
                raise TypeError('Pack and Go ön/son eki metin olmalı.')
            self._client.request('set_text', name=name, value=value)
        else:
            raise AttributeError(name)

    def GetDocumentNames(self):
        return True, self._client.request('get_names')

    def GetDocumentNamesCount(self):
        return self._client.request('count')

    def GetDocumentSaveToNames(self):
        names, states = self._client.request('get_targets')
        return True, names, states

    def SetSaveToName(self, override, path):
        return self._client.request('set_folder', override=override, path=path)

    def SetDocumentSaveToNames(self, paths):
        return self._client.request('set_targets', paths=list(getattr(paths, 'value', paths)))

    def save(self):
        return self._client.request('save')

    def close(self):
        self._client.close()


def open_pack(app, source):
    if sys.platform != 'win32':
        raise RuntimeError('Yerel SolidWorks interop bağlantısı Windows gerektirir.')
    value = app.GetProcessID
    process_id = value() if callable(value) else value
    if type(process_id) is not int or process_id <= 0:
        raise RuntimeError('SolidWorks işlem kimliği okunamadı.')
    library = _installed_interop(process_id)
    return Pack(Client(process_id, source, library))
