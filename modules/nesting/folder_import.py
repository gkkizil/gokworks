"""Cancellable local folder discovery; no geometry work on the Qt thread."""
import os
from pathlib import Path


def discover_sources(directory, *, recursive=True, prefer_dxf=True, stop=None):
    root=Path(directory).resolve()
    if not root.is_dir():raise ValueError('Okunacak klasör bulunamadı: '+str(root))
    paths=[]
    def checkpoint():
        if stop is not None and stop.is_set():raise InterruptedError('Klasör taraması durduruldu.')
    def failed(error):raise OSError('Klasör okunamadı: '+str(error))
    for current,folders,files in os.walk(root,followlinks=False,onerror=failed):
        checkpoint();folders.sort(key=str.casefold)
        if not recursive:folders.clear()
        for name in sorted(files,key=str.casefold):
            checkpoint();path=Path(current)/name
            if path.suffix.lower() not in ('.dxf','.dwg') or path.is_symlink():continue
            paths.append(path)
            if len(paths)>10000:raise ValueError('Bir taramada en fazla 10000 DXF/DWG dosyası desteklenir.')
    dxf={str(p.with_suffix('')).lower() for p in paths if p.suffix.lower()=='.dxf'}
    paired=[p for p in paths if prefer_dxf and p.suffix.lower()=='.dwg' and str(p.with_suffix('')).lower() in dxf]
    skipped=set(paired)
    checkpoint()
    return [str(p) for p in paths if p not in skipped],[str(p) for p in paired]
