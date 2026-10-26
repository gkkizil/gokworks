"""Exercise the shipping loader against real Windows PowerShell, without CAD."""

import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest
from modules.shaft_generator.bridge import LOADER, _exchange


@pytest.mark.skipif(sys.platform!='win32',reason='Windows PowerShell 5.1 requires Windows.')
def test_windows_powershell_loader_reads_request_after_ready_and_exits(tmp_path):
    root=tmp_path/'Mil taşıma testi';root.mkdir()
    framework=Path(os.environ['SystemRoot'])/'Microsoft.NET/Framework64/v4.0.30319'
    compiler=framework/'csc.exe'
    assert compiler.is_file()
    for name in ('sldworks','swconst'):
        source=root/(name+'.cs')
        source.write_text('namespace Transport_'+name+' { public class Marker {} }',encoding='utf-8')
        library=root/('SolidWorks.Interop.'+name+'.dll')
        subprocess.run([str(compiler),'/nologo','/target:library','/out:'+str(library),str(source)],
                       capture_output=True,text=True,check=True,timeout=20)
    host=root/'ShaftHost.cs'
    host.write_text('''using System;
using System.Threading;
using System.Web.Script.Serialization;
namespace Gokworks.ShaftInterop {
 public static class Host {
  public static void Run() {
   string request=Console.ReadLine();
   Console.WriteLine(new JavaScriptSerializer().Serialize(new {
    success=true, received=request, apartment=Thread.CurrentThread.GetApartmentState().ToString()
   }));
  }
 }
}''',encoding='utf-8')
    powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    payload=dict(operation='create_shaft',sentinel='Ölçü Ø30 · 40 mm')
    with subprocess.Popen([str(powershell),'-NoLogo','-NoProfile','-NonInteractive','-STA','-Command',LOADER],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW,
            env={**os.environ,'GOKWORKS_SHAFT_INTEROP':str(root/'SolidWorks.Interop.sldworks.dll'),
                 'GOKWORKS_SHAFT_HOST':str(host)}) as process:
        # This helper contains only the echo host above: it cannot contact CAD.
        # Bound a transport deadlock independently of the production CAD timeout.
        guard=threading.Timer(20,process.kill);guard.start()
        try:result=_exchange(process,payload,startup_timeout=8)
        finally:guard.cancel()
    assert process.returncode==0
    assert result['success'] and json.loads(result['received'])==payload
    assert result['apartment']=='STA'
