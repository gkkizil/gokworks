"""STA C# host using the exact running SOLIDWORKS installation's own interop."""

import json
from collections import deque
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from .models import Project
from .geometry import operation_plan


HOST_SOURCE = Path(__file__).with_name('interop') / 'ShaftHost.cs'
LOADER = r"""$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
try {
    $interop = $env:GOKWORKS_SHAFT_INTEROP
    $constants = [IO.Path]::Combine([IO.Path]::GetDirectoryName($interop), 'SolidWorks.Interop.swconst.dll')
    [Reflection.Assembly]::LoadFrom($interop) | Out-Null
    [Reflection.Assembly]::LoadFrom($constants) | Out-Null
    Add-Type -TypeDefinition ([IO.File]::ReadAllText($env:GOKWORKS_SHAFT_HOST)) -ReferencedAssemblies @($interop, $constants, 'System.Web.Extensions.dll') -ErrorAction Stop
    [Console]::WriteLine('{"event":"shaft_ready","protocol":1}')
    [Gokworks.ShaftInterop.Host]::Run()
} catch {
    [Console]::WriteLine((@{success=$false; errors=@($_.Exception.Message)} | ConvertTo-Json -Depth 4 -Compress))
    exit 1
}
"""


def checked_payload(payload):
    if not isinstance(payload,dict) or payload.get('operation')!='create_shaft':
        raise ValueError('Desteklenmeyen mil komutu.')
    project=Project.from_dict(payload['project'])
    if payload.get('plan')!=operation_plan(project):
        raise ValueError('Mil işlem planı parametrelerle eşleşmiyor.')
    output=str(payload.get('output_path',''))
    if output:
        target=Path(output)
        if target.suffix.lower()!='.sldprt' or not target.is_absolute() or not target.parent.is_dir():
            raise ValueError('SLDPRT için mevcut klasörde tam dosya yolu gerekli.')
        if target.exists():raise FileExistsError('Mevcut SLDPRT üzerine yazılmaz: '+output)
    return project


def _exchange(process, payload, *, stop=None, on_status=None, startup_timeout=60,
              diagnostic_interval=15, operation_timeout=180):
    """Bound startup before sending CAD work; keep the lock during slow COM calls.

    A running CAD command cannot safely be killed or abandoned on timeout. Its
    deadline raises a visible wait warning while this worker retains ownership.
    """
    responses=queue.Queue();diagnostics=deque(maxlen=40)
    def read_output():
        try:
            for line in process.stdout:
                try:responses.put(json.loads(line))
                except ValueError:diagnostics.append('Geçersiz host çıktısı: '+line[-500:])
        except Exception as error:diagnostics.append(str(error))
        finally:responses.put(None)
    def read_errors():
        for line in process.stderr:diagnostics.append(line[-500:].rstrip())
    reader=threading.Thread(target=read_output,daemon=True,name='shaft-host-output')
    errors=threading.Thread(target=read_errors,daemon=True,name='shaft-host-errors')
    reader.start();errors.start()
    began=time.monotonic();sent=None;last_notice=began;phase='C# derleniyor';result=None;timed_out=False
    try:
        while True:
            now=time.monotonic()
            if sent is None and now-began>=startup_timeout:
                # No request has been sent, so the host cannot own a CAD part.
                process.terminate();process.wait()
                raise RuntimeError(f'C# host başlangıcı {startup_timeout:g} saniyede tamamlanmadı. CAD komutu gönderilmedi.')
            if sent is not None:
                overdue=now-sent>=operation_timeout
                if overdue and not timed_out:
                    timed_out=True
                    if on_status:on_status(f'SOLIDWORKS bekleme süresi aşıldı ({now-sent:.0f} sn). Son aşama: {phase}. Devam eden COM işleminin güvenli sonucu bekleniyor.')
                elif now-last_notice>=diagnostic_interval:
                    if on_status:on_status(f'SOLIDWORKS · {phase} · {now-sent:.0f} sn; güvenli sonuç bekleniyor.')
                    last_notice=now
            try:reply=responses.get(timeout=.1)
            except queue.Empty:continue
            if reply is None:break
            if not isinstance(reply,dict):diagnostics.append('Host yanıtı JSON nesnesi değil.');continue
            if reply.get('event')=='shaft_ready':
                if sent is not None or reply.get('protocol')!=1:
                    if sent is None:process.terminate();process.wait()
                    raise RuntimeError('C# host protokolü uyuşmuyor.')
                if stop is not None and stop.is_set():
                    process.stdin.close();process.wait()
                    raise RuntimeError('Mil işlemi başlamadan durduruldu.')
                process.stdin.write(json.dumps(payload,ensure_ascii=False,allow_nan=False)+'\n');process.stdin.flush()
                sent=time.monotonic();process.stdin.close()
            elif reply.get('event')=='shaft_phase' and sent is not None:
                phase=str(reply.get('phase',''))
                if on_status:on_status(phase)
            elif 'success' in reply:
                result=reply
        process.wait();errors.join(timeout=2)
        if result is None:
            raise RuntimeError('SOLIDWORKS C# yanıtı alınamadı. Son aşama: '+phase+'\n'+'\n'.join(diagnostics))
        return result
    finally:
        reader.join(timeout=2);errors.join(timeout=2)


def execute(payload, *, stop=None, on_status=None):
    checked_payload(payload)
    if sys.platform!='win32':
        raise RuntimeError('Yerel SOLIDWORKS parçası oluşturmak Windows ve açık SOLIDWORKS gerektirir.')
    if stop is not None and stop.is_set():
        raise RuntimeError('Mil işlemi başlamadan durduruldu.')
    import pythoncom
    from solidworks.connection import connect_to_solidworks
    from modules.naming.native import _installed_interop
    pythoncom.CoInitialize()
    app=None
    try:
        app=connect_to_solidworks()
        value=app.GetProcessID
        process_id=value() if callable(value) else value
        if type(process_id) is not int or process_id<=0:
            raise RuntimeError('SOLIDWORKS işlem kimliği okunamadı.')
        library=_installed_interop(process_id)
    finally:
        app=None
        pythoncom.CoUninitialize()
    if not HOST_SOURCE.is_file():raise RuntimeError('ShaftHost.cs uygulama paketinde bulunamadı.')
    if not library.with_name('SolidWorks.Interop.swconst.dll').is_file():
        raise RuntimeError('Kurulu SOLIDWORKS API sabitleri bulunamadı: SolidWorks.Interop.swconst.dll')
    powershell=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    command=[str(powershell),'-NoLogo','-NoProfile','-NonInteractive','-STA','-Command',LOADER]
    with subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                           encoding='utf-8',errors='strict',creationflags=subprocess.CREATE_NO_WINDOW,
                           env={**os.environ,'GOKWORKS_SHAFT_INTEROP':str(library),'GOKWORKS_SHAFT_HOST':str(HOST_SOURCE)}) as process:
        result=_exchange(process,dict(payload,process_id=process_id),stop=stop,on_status=on_status)
    if not isinstance(result,dict) or process.returncode or result.get('success') is not True:
        messages=result.get('errors',['Geçersiz C# yanıtı.']) if isinstance(result,dict) else ['Geçersiz C# yanıtı.']
        raise RuntimeError('SOLIDWORKS: '+'; '.join(str(item) for item in messages))
    expected=[row['name'] for row in payload['plan']]
    if (result.get('process_id')!=process_id or result.get('rebuild_success') is not True
            or result.get('features')!=expected or result.get('feature_count')!=len(expected)
            or result.get('fully_defined') is not True or result.get('single_body') is not True):
        raise RuntimeError('C# yanıtında işlem kimliği, özellik ağacı veya parametrik doğrulama eksik.')
    return result
