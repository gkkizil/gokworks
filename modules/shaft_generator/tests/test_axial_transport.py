"""Actual Windows compiler/API contract tests, without a CAD geometry kernel."""

import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from modules.shaft_generator.bridge import HOST_SOURCE,LOADER


@pytest.mark.skipif(sys.platform!='win32' or not os.environ.get('GOKWORKS_SHAFT_TEST_INTEROP'),
                   reason='Windows PowerShell and temporary interop references required; no live CAD.')
def test_shipping_cosmetic_call_metadata_checks_and_bore_volume():
    library=Path(os.environ['GOKWORKS_SHAFT_TEST_INTEROP']).resolve()
    probe=r'''
Add-Type -ReferencedAssemblies $references -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.Remoting.Proxies;
using System.Runtime.Remoting.Messaging;
using SolidWorks.Interop.sldworks;
namespace Gokworks.AxialTest {
 public class Capture : RealProxy {
  public Dictionary<string,object> Arguments=new Dictionary<string,object>();
  public Capture() : base(typeof(IFeatureManager)) {}
  public override IMessage Invoke(IMessage msg) {
   IMethodCallMessage call=(IMethodCallMessage)msg;
   if(call.MethodName!="InsertCosmeticThread3") throw new InvalidOperationException(call.MethodName);
   ParameterInfo[] parameters=typeof(IFeatureManager).GetMethod(call.MethodName).GetParameters();
   for(int i=0;i<parameters.Length;i++) Arguments[parameters[i].Name]=call.Args[i];
   // A null feature is intentional: no simulated native CAD success.
   return new ReturnMessage(null,null,0,call.LogicalCallContext,call);
  }
  public static Capture Run(MethodInfo method) {
   Capture c=new Capture();method.Invoke(null,new object[]{c.GetTransparentProxy(),30.0,3.5,20.0});return c;
  }
 }
 public class Metadata : RealProxy {
  public string Mode;
  public Metadata(string mode) : base(typeof(ICosmeticThreadFeatureData)) { Mode=mode; }
  public override IMessage Invoke(IMessage msg) {
   IMethodCallMessage call=(IMethodCallMessage)msg;object value;
   switch(call.MethodName) {
    case "get_Size": value=Mode=="size" ? "M30x1.5" : "M30x3.500";break;
    case "get_Standard": value=Mode=="standard" ? -2 : 8;break;
    case "get_EndCondition": value=Mode=="end" ? 2 : 0;break;
    case "get_BlindDepth": value=Mode=="depth" ? 0.002 : 0.02;break;
    case "get_Diameter": value=Mode=="diameter" ? 0.04 : 0.0257;break;
    default: throw new InvalidOperationException(call.MethodName);
   }
   return new ReturnMessage(value,null,0,call.LogicalCallContext,call);
  }
  public static bool Check(MethodInfo method,string mode) {
   Metadata data=new Metadata(mode);
   try { method.Invoke(null,new object[]{data.GetTransparentProxy(),30.0,3.5,20.0});return true; }
   catch(TargetInvocationException e) { if(!(e.InnerException is InvalidOperationException))throw;return false; }
  }
 }
 public static class Checks {
  public static bool Volume(MethodInfo method,double after) {
   try { method.Invoke(null,new object[]{0.0001,after});return true; }
   catch(TargetInvocationException e) { if(!(e.InnerException is InvalidOperationException))throw;return false; }
  }
 }
}
'@
$flags=[Reflection.BindingFlags]::Static -bor [Reflection.BindingFlags]::NonPublic
$t=[Gokworks.ShaftInterop.Host].Assembly.GetType('Gokworks.ShaftInterop.AxialFeatures',$true)
$capture=[Gokworks.AxialTest.Capture]::Run($t.GetMethod('Cosmetic',$flags))
$m=$t.GetMethod('VerifyCosmetic',$flags)
$checks=@{}
foreach($mode in @('valid','size','standard','end','depth','diameter')) {
 $checks[$mode]=[Gokworks.AxialTest.Metadata]::Check($m,$mode)
}
$v=$t.GetMethod('VerifyUnchanged',$flags)
$hole=$t.GetMethod('BoreVolume',$flags).Invoke($null,[object[]]@([double]10,[double]180))
[Console]::WriteLine((@{ event='axial_contract'; arguments=$capture.Arguments; metadata=$checks; bore=$hole;
 unchanged=[Gokworks.AxialTest.Checks]::Volume($v,0.0001); changed=[Gokworks.AxialTest.Checks]::Volume($v,0.00009);
 nan=[Gokworks.AxialTest.Checks]::Volume($v,[double]::NaN) } | ConvertTo-Json -Depth 5 -Compress))
'''
    powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    result=subprocess.run([str(powershell),'-NoLogo','-NoProfile','-NonInteractive','-STA',
        '-Command',LOADER.replace('[Gokworks.ShaftInterop.Host]::Run()',probe)],
        input='',encoding='utf-8',capture_output=True,timeout=40,creationflags=subprocess.CREATE_NO_WINDOW,
        env={**os.environ,'GOKWORKS_SHAFT_INTEROP':str(library),'GOKWORKS_SHAFT_HOST':str(HOST_SOURCE)})
    assert result.returncode==0,result.stdout+result.stderr
    data=next(json.loads(line) for line in result.stdout.splitlines() if 'axial_contract' in line)
    args=data['arguments']
    assert args['Standard']==8 and args['StandardType']=='Machine Threads'
    assert args['Size']=='M30x3.5' and args['EndType']==0 and args['Depth']==pytest.approx(.02)
    assert args['Diameter']==pytest.approx((30-1.226869*3.5)*.001)
    assert data['metadata']['valid'] and not any(data['metadata'][k] for k in ('size','standard','end','depth','diameter'))
    assert data['unchanged'] and not data['changed'] and not data['nan']
    import math
    assert data['bore']==pytest.approx(math.pi*25*180*1e-9)
