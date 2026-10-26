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


@pytest.mark.skipif(sys.platform!='win32' or not os.environ.get('GOKWORKS_SHAFT_TEST_INTEROP'),
                   reason='Windows and explicitly staged interop compile references required.')
def test_shipping_cut_api_arguments_and_real_volume_checks():
    """Intercept API arguments, without pretending to run a CAD geometry kernel."""
    library=Path(os.environ['GOKWORKS_SHAFT_TEST_INTEROP']).resolve()
    probe=r'''
Add-Type -ReferencedAssemblies $references -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.Remoting.Messaging;
using System.Runtime.Remoting.Proxies;
using SolidWorks.Interop.sldworks;
namespace Gokworks.ShaftCutTest {
 public class Manager : RealProxy {
  public string Method;
  public Dictionary<string,object> Arguments;
  private readonly Type contract;
  public Manager(Type type) : base(type) { contract=type; }
  public override IMessage Invoke(IMessage message) {
   IMethodCallMessage call=(IMethodCallMessage)message;
   Method=call.MethodName; Arguments=new Dictionary<string,object>();
   MethodBase method=call.MethodBase ?? contract.GetMethod(call.MethodName);
   if(method==null) throw new MissingMethodException("Unexpected proxy call: "+call.MethodName);
   ParameterInfo[] parameters=method.GetParameters();
   for(int i=0;i<parameters.Length;i++) Arguments.Add(parameters[i].Name,call.Args[i]);
   // Deliberately return no feature: this is not a simulated CAD success.
   return new ReturnMessage(null,null,0,call.LogicalCallContext,call);
  }
  public static Manager Capture(MethodInfo method, double depth, bool keyway, bool reverse) {
   Manager capture=new Manager(typeof(IFeatureManager));
   object proxy=capture.GetTransparentProxy();
   method.Invoke(null,keyway ? new object[]{proxy,depth,reverse} : new object[]{proxy});
   return capture;
  }
  public static Manager CaptureSlot(MethodInfo method, double sign) {
   Manager capture=new Manager(typeof(ISketchManager));
   method.Invoke(null,new object[]{capture.GetTransparentProxy(),0.005,0.020,0.008,sign});
   return capture;
  }
  public static bool CheckRemoval(MethodInfo method, double after, double expected) {
   try { method.Invoke(null,new object[]{"TEST_CUT",0.0001,after,expected}); return true; }
   catch(TargetInvocationException error) {
    if(!(error.InnerException is InvalidOperationException)) throw;
    return false;
   }
  }
  public static double Expected(MethodInfo method, bool keyway, double diameter, double length, double width, double depth) {
   Type stageType=method.GetParameters()[0].ParameterType;
   Type operationType=method.GetParameters()[1].ParameterType;
   object stage=Activator.CreateInstance(stageType), operation=Activator.CreateInstance(operationType);
   stageType.GetField("diameter").SetValue(stage,diameter);
   operationType.GetField("kind").SetValue(operation,keyway ? "keyway" : "groove");
   operationType.GetField("width").SetValue(operation,width);
   operationType.GetField("depth").SetValue(operation,depth);
   operationType.GetField("length").SetValue(operation,length);
   return (double)method.Invoke(null,new object[]{stage,operation});
  }
 }
}
'@
$type=[Gokworks.ShaftInterop.Host].Assembly.GetType('Gokworks.ShaftInterop.ChannelCuts',$true)
$flags=[Reflection.BindingFlags]::Static -bor [Reflection.BindingFlags]::NonPublic
$groove=[Gokworks.ShaftCutTest.Manager]::Capture($type.GetMethod('Groove',$flags),0,$false,$false)
$keyway=[Gokworks.ShaftCutTest.Manager]::Capture($type.GetMethod('Keyway',$flags),0.004,$true,$true)
$opposite=[Gokworks.ShaftCutTest.Manager]::Capture($type.GetMethod('Keyway',$flags),0.004,$true,$false)
$slot=[Gokworks.ShaftCutTest.Manager]::CaptureSlot($type.GetMethod('KeywaySlot',$flags),1)
$mirrored=[Gokworks.ShaftCutTest.Manager]::CaptureSlot($type.GetMethod('KeywaySlot',$flags),-1)
$volumeMethod=$type.GetMethod('ExpectedVolume',$flags)
$expected=[Gokworks.ShaftCutTest.Manager]::Expected($volumeMethod,$false,30,20,2,1)
$volumes=@()
foreach($sample in @(@(30,20,8,3),@(35,25,10,4),@(30,8.1,8,3),@(100,50,2,1),@(30,20.1,20,14))) {
 $volumes+=@{ parameters=$sample; volume=[Gokworks.ShaftCutTest.Manager]::Expected($volumeMethod,$true,$sample[0],$sample[1],$sample[2],$sample[3]) }
}
$verify=$type.GetMethod('VerifyRemoval',$flags)
function Check-Removal([double]$after) {
 return [Gokworks.ShaftCutTest.Manager]::CheckRemoval($verify,$after,$expected)
}
[Console]::WriteLine((@{
 event='cut_contract'; groove_method=$groove.Method; groove=$groove.Arguments;
 keyway_method=$keyway.Method; keyway=$keyway.Arguments;
 groove_volume=$expected; keyway_volumes=$volumes;
 opposite=$opposite.Arguments; slot_method=$slot.Method; slot=$slot.Arguments; mirrored=$mirrored.Arguments;
 valid=(Check-Removal (0.0001-$expected)); unchanged=(Check-Removal 0.0001);
 added=(Check-Removal (0.0001+$expected)); overcut=(Check-Removal (0.0001-5*$expected))
} | ConvertTo-Json -Depth 5 -Compress))
'''
    powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    result=subprocess.run([str(powershell),'-NoLogo','-NoProfile','-NonInteractive','-STA',
                           '-Command',LOADER.replace('[Gokworks.ShaftInterop.Host]::Run()',probe)],
        input='',encoding='utf-8',capture_output=True,timeout=40,
        creationflags=subprocess.CREATE_NO_WINDOW,
        env={**os.environ,'GOKWORKS_SHAFT_INTEROP':str(library),'GOKWORKS_SHAFT_HOST':str(HOST_SOURCE)})
    assert result.returncode==0,result.stdout+result.stderr
    data=next(json.loads(line) for line in result.stdout.splitlines() if 'cut_contract' in line)
    import math
    assert data['groove_method']=='FeatureRevolve2'
    groove=data['groove']
    assert groove['IsCut'] and groove['IsSolid'] and not groove['IsThin']
    assert groove['Dir1Angle']==pytest.approx(math.tau)
    assert not groove['Merge'] and not groove['UseFeatScope'] and groove['UseAutoSelect']
    assert data['keyway_method']=='FeatureCut4'
    keyway=data['keyway']
    assert keyway['T1']==0 and keyway['D1']==pytest.approx(.004)  # Blind radial cut, depth + clearance.
    assert keyway['Sd'] and keyway['Dir'] and not data['opposite']['Dir']
    assert keyway['T0']==0 and keyway['StartOffset']==0
    assert not keyway['Flip'] and not keyway['NormalCut'] and not keyway['OptimizeGeometry']
    assert not keyway['UseFeatScope'] and keyway['UseAutoSelect']
    assert data['groove_volume']==pytest.approx(2*math.pi*(2*15*1-1)*1e-9)
    assert data['slot_method']=='CreateSketchSlot'
    slot=data['slot']
    assert slot['SlotCreationType']==0 and slot['SlotLengthType']==0
    assert slot['Width']==pytest.approx(.008) and not slot['AddDimension']
    # Arc centres produce overall [5,25] mm, with 4 mm end radii.
    assert slot['X1']==pytest.approx(.009) and slot['X2']==pytest.approx(.021)
    assert slot['Y1']==slot['Y2']==slot['Z1']==slot['Z2']==slot['Z3']==0
    assert slot['Y3']==pytest.approx(.004)
    assert data['mirrored']['X1']==pytest.approx(-.009)
    assert data['mirrored']['X2']==pytest.approx(-.021)
    from modules.shaft_generator.tests.volume_reference import rounded_keyway_volume
    for sample in data['keyway_volumes']:
        expected=rounded_keyway_volume(*sample['parameters'])*1e-9
        assert sample['volume']==pytest.approx(expected,rel=1e-7)
    assert data['valid'] and not any(data[k] for k in ('unchanged','added','overcut'))
