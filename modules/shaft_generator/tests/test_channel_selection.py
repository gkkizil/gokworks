"""Shipping C# selection/unit/failure-policy probes; never simulate CAD success."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from modules.shaft_generator.bridge import HOST_SOURCE, LOADER


@pytest.mark.skipif(sys.platform != 'win32' or not os.environ.get('GOKWORKS_SHAFT_TEST_INTEROP'),
                   reason='Windows PowerShell and staged interop references required; no live CAD.')
def test_shipping_channel_selection_units_and_failed_part_preservation():
    library = Path(os.environ['GOKWORKS_SHAFT_TEST_INTEROP']).resolve()
    probe = r'''
Add-Type -ReferencedAssemblies $references -TypeDefinition ([IO.File]::ReadAllText($env:GOKWORKS_SHAFT_CHANNEL_PROBE))
$assembly=[Gokworks.ShaftInterop.Host].Assembly
$flags=[Reflection.BindingFlags]::Static -bor [Reflection.BindingFlags]::NonPublic
$type=$assembly.GetType('Gokworks.ShaftInterop.ChannelCuts',$true)
$order=$type.GetField('OperationOrder',$flags).GetValue($null)
$fillet=[Gokworks.ShaftChannelTest.FilletProbe]::Capture($type.GetMethod('Fillet',$flags),$false)
$badFillet=[Gokworks.ShaftChannelTest.FilletProbe]::Capture($type.GetMethod('Fillet',$flags),$true)
$select=$type.GetMethod('SelectGroove',$flags)
$valid=New-Object Gokworks.ShaftChannelTest.Probe
$accepted=$valid.Select($select)
$refused=New-Object Gokworks.ShaftChannelTest.Probe
$refused.RefuseAxis=$true
$refusedResult=$refused.Select($select)
$extra=New-Object Gokworks.ShaftChannelTest.Probe
$extra.ExtraSelection=$true
$extraResult=$extra.Select($select)
$start=$type.GetMethod('KeywayStartMetres',$flags)
$reverse=$type.GetMethod('KeywayReverseDirection',$flags)
$paths=@()
foreach($sample in @(@(30,3),@(30,4),@(10,1),@(100,5),@(35,4),@(45,5.5))) {
 foreach($normal in @(-1.0,1.0)) {
  $value=$start.Invoke($null,[object[]]@([double]$sample[0]))
  $direction=$reverse.Invoke($null,[object[]]@([double]$normal))
  $paths+=@{ diameter=$sample[0]; depth=$sample[1]; start=$value; normal=$normal; reverse=$direction }
 }
}
$selectKeyway=$type.GetMethod('SelectKeyway',$flags)
$keyway=New-Object Gokworks.ShaftChannelTest.Probe
$keywayAccepted=$keyway.SelectKeyway($selectKeyway)
$keywayInvalid=@()
foreach($mode in @('status','open','multiple','none','selection','extra')) {
 $bad=New-Object Gokworks.ShaftChannelTest.Probe
 switch($mode) {
  'status' { $bad.ProfileStatus=1 }
  'open' { $bad.OpenContours=1 }
  'multiple' { $bad.ClosedContours=2 }
  'none' { $bad.ClosedContours=0 }
  'selection' { $bad.RefuseSketch=$true }
  'extra' { $bad.ExtraSelection=$true }
 }
 $keywayInvalid+=@{ mode=$mode; accepted=$bad.SelectKeyway($selectKeyway); events=$bad.Events }
}
$keep=New-Object Gokworks.ShaftChannelTest.Probe
$preserve=[Gokworks.ShaftInterop.Host].GetMethod('PreserveFailedPart',$flags)
$title=$keep.Preserve($preserve)
$empty=$keep.PreserveEmpty($preserve)
[Console]::WriteLine((@{
 event='channel_selection'; accepted=$accepted; events=$valid.Events; order=$order;
 refused=$refusedResult; extra=$extraResult; paths=$paths;
 keyway_accepted=$keywayAccepted; keyway_events=$keyway.Events; keyway_invalid=$keywayInvalid;
 retained_title=$title; retained_events=$keep.Events; no_document=$empty
 fillet=$fillet.Values; fillet_create_called=$fillet.CreateCalled;
 fillet_definition=$fillet.CorrectDefinition; fillet_edges=$fillet.EdgeCount;
 fillet_bad_init_rejected=$badFillet.Rejected; fillet_bad_create_called=$badFillet.CreateCalled
} | ConvertTo-Json -Depth 5 -Compress))
'''
    powershell = Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    result = subprocess.run(
        [str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-STA', '-Command',
         LOADER.replace('[Gokworks.ShaftInterop.Host]::Run()', probe)],
        input='', encoding='utf-8', capture_output=True, timeout=45,
        creationflags=subprocess.CREATE_NO_WINDOW,
        env={**os.environ, 'GOKWORKS_SHAFT_INTEROP': str(library),
             'GOKWORKS_SHAFT_HOST': str(HOST_SOURCE),
             'GOKWORKS_SHAFT_CHANNEL_PROBE': str(Path(__file__).with_name('native')/'ChannelProbe.cs')})
    assert result.returncode == 0, result.stdout + result.stderr
    data = next(json.loads(line) for line in result.stdout.splitlines() if 'channel_selection' in line)
    assert data['accepted'] and data['events'] == [
        'contours:False', 'clear:True', 'sketch:False:0', 'axis:True:4']
    assert not data['refused'] and not data['extra']
    assert data['order'] == ['chamfer', 'fillet', 'groove', 'keyway']
    fillet=data['fillet']
    assert fillet['Definition']==1 and fillet['Initialize']==0  # native constant-radius definition
    assert fillet['DefaultRadius']==pytest.approx(.001) and fillet['ConicTypeForCrossSectionProfile']==0
    assert not any(fillet[k] for k in ('CurvatureContinuous','IsMultipleRadius','AsymmetricFillet','PropagateToTangentFaces'))
    assert data['fillet_create_called'] and data['fillet_definition'] and data['fillet_edges']==1
    assert data['fillet_bad_init_rejected'] and not data['fillet_bad_create_called']
    assert data['keyway_accepted'] and data['keyway_events']==[
        'profile:11','contours:False','clear:True','sketch:False:0']
    for invalid in data['keyway_invalid']:
        assert not invalid['accepted'], invalid
        assert any(event.startswith('rejected:') for event in invalid['events'])
        if invalid['mode'] in ('status','open','multiple','none'):
            assert not any(event.startswith('sketch:') for event in invalid['events'])
    for sample in data['paths']:
        # Independent cut-direction contract: default cut is -sketch normal.
        # Both reference-plane orientations must end on the same pocket floor.
        assert sample['start']*1000==pytest.approx(sample['diameter']/2+1)
        direction=sample['normal']*(1 if sample['reverse'] else -1)
        end=sample['start']*1000+direction*(sample['depth']+1)
        assert direction==-1
        assert end==pytest.approx(sample['diameter']/2-sample['depth'])
    assert data['retained_title'] == 'Mil_inceleme'
    assert data['retained_events'] == ['add-to-db:False'] and data['no_document'] == ''
