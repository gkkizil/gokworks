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
$select=$type.GetMethod('SelectGroove',$flags)
$valid=New-Object Gokworks.ShaftChannelTest.Probe
$accepted=$valid.Select($select)
$refused=New-Object Gokworks.ShaftChannelTest.Probe
$refused.RefuseAxis=$true
$refusedResult=$refused.Select($select)
$extra=New-Object Gokworks.ShaftChannelTest.Probe
$extra.ExtraSelection=$true
$extraResult=$extra.Select($select)
$floor=$type.GetMethod('KeywayFloorMetres',$flags)
$floors=@()
foreach($sample in @(@(30,3),@(30,4),@(10,1),@(100,5),@(35,4))) {
 $value=$floor.Invoke($null,[object[]]@([double]$sample[0],[double]$sample[1]))
 $floors+=@{ diameter=$sample[0]; depth=$sample[1]; metres=$value }
}
$keep=New-Object Gokworks.ShaftChannelTest.Probe
$preserve=[Gokworks.ShaftInterop.Host].GetMethod('PreserveFailedPart',$flags)
$title=$preserve.Invoke($null,[object[]]@($keep.Model))
$empty=$preserve.Invoke($null,[object[]]@($null))
[Console]::WriteLine((@{
 event='channel_selection'; accepted=$accepted; events=$valid.Events;
 refused=$refusedResult; extra=$extraResult; floors=$floors;
 retained_title=$title; retained_events=$keep.Events; no_document=$empty
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
        'contours:False', 'clear:True', 'sketch:False:0', 'axis:True:16']
    assert not data['refused'] and not data['extra']
    for sample in data['floors']:
        # Independent millimetre-to-metre reference, especially the reported Ø30 case.
        assert sample['metres'] * 1000 == pytest.approx(sample['diameter']/2 - sample['depth'])
    assert data['retained_title'] == 'Mil_inceleme'
    assert data['retained_events'] == ['add-to-db:False'] and data['no_document'] == ''
