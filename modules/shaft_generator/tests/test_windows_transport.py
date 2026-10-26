"""Exercise the shipping loader against real Windows PowerShell, without CAD."""

import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest
from modules.shaft_generator.bridge import HOST_SOURCE, LOADER, _exchange


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


@pytest.mark.skipif(sys.platform!='win32' or not os.environ.get('GOKWORKS_SHAFT_TEST_INTEROP'),
                   reason='Windows and explicitly staged interop compile references required.')
def test_real_host_uses_registered_class_for_running_object_lookup():
    library=Path(os.environ['GOKWORKS_SHAFT_TEST_INTEROP']).resolve()
    assert library.is_file()
    # Compile the shipping C# host, then exercise its COM lookup against a
    # temporary test-only ProgID/ROT object. No SOLIDWORKS activation or CAD.
    probe=r'''
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace Gokworks.ShaftTest {
 [ComVisible(true), ClassInterface(ClassInterfaceType.AutoDispatch)]
 public class Marker {}
 public static class Rot {
  [DllImport("oleaut32.dll", PreserveSig=false)]
  public static extern void RegisterActiveObject([MarshalAs(UnmanagedType.IUnknown)] object value,
   ref Guid clsid, uint flags, out uint cookie);
  [DllImport("oleaut32.dll", PreserveSig=false)]
  public static extern void RevokeActiveObject(uint cookie, IntPtr reserved);
  public static bool SameIdentity(object left, object right) {
   IntPtr a=Marshal.GetIUnknownForObject(left), b=Marshal.GetIUnknownForObject(right);
   try { return a==b; } finally { Marshal.Release(a); Marshal.Release(b); }
  }
 }
}
'@
$progId='Gokworks.ShaftProbe.'+[Guid]::NewGuid().ToString('N')
$clsid=[Guid]::NewGuid()
$progKey='Software\Classes\'+$progId
$classKey='Software\Classes\CLSID\'+$clsid.ToString('B')
$cookie=[uint32]0
try {
 $key=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($progKey+'\CLSID')
 $key.SetValue('', $clsid.ToString('B')); $key.Close()
 $key=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($classKey+'\ProgID')
 $key.SetValue('', $progId); $key.Close()
 $marker=New-Object Gokworks.ShaftTest.Marker
 [Gokworks.ShaftTest.Rot]::RegisterActiveObject($marker,[ref]$clsid,0,[ref]$cookie)
 $active=[Gokworks.ShaftInterop.Host]::ConnectRunningApplication($progId)
 if (-not [Gokworks.ShaftTest.Rot]::SameIdentity($marker,$active)) { throw 'Wrong running COM object' }
 [Console]::WriteLine('GOKWORKS_SHAFT_REGISTERED_CLASS_OK')
} finally {
 if ($cookie -ne 0) { [Gokworks.ShaftTest.Rot]::RevokeActiveObject($cookie,[IntPtr]::Zero) }
 [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($progKey,$false)
 [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($classKey,$false)
}
'''
    marker='[Gokworks.ShaftInterop.Host]::Run()'
    assert LOADER.count(marker)==1
    powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    result=subprocess.run([str(powershell),'-NoLogo','-NoProfile','-NonInteractive','-STA',
                           '-Command',LOADER.replace(marker,probe)],
        input='',encoding='utf-8',capture_output=True,timeout=40,
        creationflags=subprocess.CREATE_NO_WINDOW,
        env={**os.environ,'GOKWORKS_SHAFT_INTEROP':str(library),'GOKWORKS_SHAFT_HOST':str(HOST_SOURCE)})
    assert result.returncode==0,result.stdout+result.stderr
    assert 'GOKWORKS_SHAFT_REGISTERED_CLASS_OK' in result.stdout,result.stdout+result.stderr
