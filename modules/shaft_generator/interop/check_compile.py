"""Compile against caller-supplied interop/Framework references, without CAD.

No DLL is downloaded or copied into the repository. Windows runtime compilation
still uses PowerShell Add-Type and the installed SOLIDWORKS DLLs.
"""

import argparse
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dotnet',type=Path,required=True)
    parser.add_argument('--framework-references',type=Path,required=True)
    parser.add_argument('--interop-dir',type=Path,required=True)
    parser.add_argument('--constants-dir',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    sdk=sorted((args.dotnet.parent/'sdk').glob('*/Roslyn/bincore/csc.dll'))
    if not sdk:parser.error('Roslyn csc.dll bulunamadı.')
    refs=[args.framework_references/n for n in ('mscorlib.dll','System.dll','System.Core.dll','System.Web.Extensions.dll')]
    facade=args.framework_references/'Facades/netstandard.dll'
    if facade.is_file():refs.append(facade)
    refs.extend((args.interop_dir/'SolidWorks.Interop.sldworks.dll',
                 (args.constants_dir or args.interop_dir)/'SolidWorks.Interop.swconst.dll'))
    for ref in refs:
        if not ref.is_file():parser.error('Referans bulunamadı: '+str(ref))
    command=[str(args.dotnet),str(sdk[-1]),'-nologo','-noconfig','-nostdlib+',
             '-langversion:5','-warnaserror+','-target:library','-out:'+str(args.output)]
    command.extend('-r:'+str(ref) for ref in refs)
    command.append(str(Path(__file__).with_name('ShaftHost.cs')))
    subprocess.run(command,check=True)
    print('C# compile passed (C# 5, warnings as errors). This is NOT a live SOLIDWORKS test.')


if __name__=='__main__':main()
