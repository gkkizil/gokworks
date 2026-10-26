"""Stage pinned interop references for Windows compile tests, outside the app.

These DLLs are test inputs only. The packaged host resolves the user's installed
SOLIDWORKS DLLs and never ships these temporary NuGet references.
"""

import argparse
import io
from pathlib import Path
import urllib.request
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    args.directory.mkdir(parents=True,exist_ok=True)
    for package in ('solidworks.interop.sldworks','solidworks.interop.swconst'):
        url=f'https://api.nuget.org/v3-flatcontainer/{package}/32.1.0/{package}.32.1.0.nupkg'
        with urllib.request.urlopen(url,timeout=30) as response:
            data=response.read()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names=[name for name in archive.namelist()
                   if name.lower().startswith('lib/netstandard2.0/') and name.lower().endswith('.dll')]
            if len(names)!=1:raise RuntimeError('Unexpected interop reference package: '+package)
            target=args.directory/Path(names[0]).name
            target.write_bytes(archive.read(names[0]))
            print(target)


if __name__=='__main__':main()
