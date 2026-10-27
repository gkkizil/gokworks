"""Bounded local CAD subprocess; cancel/timeout cannot freeze the Qt GUI thread."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from .serialization import to_dict

ROOT=Path(__file__).resolve().parents[2]


class OperationCancelled(RuntimeError):
    pass


def execute(spec,mode,*,target='pair',path=None,construction=True,overwrite=False,stop=None,timeout=120.):
    if mode not in ('check','mesh','dxf','step') or target not in ('pinion','wheel','pair'):
        raise ValueError('Geçersiz dişli işlemi/hedefi.')
    if timeout<=0 or timeout>300:
        raise ValueError('İşlem süresi 0–300 saniye aralığında olmalı.')
    data=to_dict(spec)
    destination=None
    if mode in ('dxf','step'):
        if path is None:
            raise ValueError('CAD aktarım dosyası gerekli.')
        destination=Path(path).absolute()
        if not destination.parent.is_dir() or destination.suffix.lower() not in (('.dxf',) if mode=='dxf' else ('.step','.stp')):
            raise ValueError('CAD dosyası klasörü/uzantısı geçersiz.')
        if destination.exists() and not overwrite:
            raise FileExistsError(str(destination))
    if stop is not None and stop.is_set():
        raise OperationCancelled('İşlem durduruldu.')
    with TemporaryDirectory(prefix='gokworks-gear-') as folder_name:
        folder=Path(folder_name);request=folder/'request.json'
        request.write_text(json.dumps(dict(specification=data,mode=mode,target=target,construction=bool(construction)),
                                      allow_nan=False),encoding='utf-8')
        command=[sys.executable]
        if not getattr(sys,'frozen',False):
            command.append(str(ROOT/'main.py'))
        command.extend(['--gear-worker',str(request)])
        with (folder/'worker.log').open('wb') as log:
            process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,env={**os.environ,'PYTHONUTF8':'1'},
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            deadline=time.monotonic()+timeout
            try:
                while process.poll() is None:
                    if stop is not None and stop.is_set():
                        raise OperationCancelled('Dişli işlemi durduruldu; dosya yayınlanmadı.')
                    if time.monotonic()>deadline:
                        raise TimeoutError('Dişli CAD işlemi süre sınırını aştı; diş sayısını azaltın.')
                    try:
                        process.wait(timeout=.08)
                    except subprocess.TimeoutExpired:
                        pass
            finally:
                if process.poll() is None:
                    process.kill();process.wait(timeout=10)
        if stop is not None and stop.is_set():
            raise OperationCancelled('İşlem durduruldu; dosya yayınlanmadı.')
        response=folder/'result.json'
        if not response.is_file():
            raise RuntimeError('Yerel CAD motoru sonuç vermeden kapandı. '+(folder/'worker.log').read_text(encoding='utf-8',errors='replace')[-1000:])
        result=json.loads(response.read_text(encoding='utf-8'))
        if process.returncode or not result.get('ok'):
            raise RuntimeError(result.get('error','Dişli işlemi başarısız.'))
        info=result['result']
        if mode=='check':
            return info
        if mode=='mesh':
            import numpy as np
            from modules.dxf_dwg.preview.geometry import make_mesh
            points=np.load(folder/'mesh.npy',allow_pickle=False)
            if points.ndim!=1 or points.size>120000*9:
                raise ValueError('CAD üçgen verisi sınır dışında.')
            return dict(mesh=make_mesh(points*.001,stop),**info)
        source=folder/('model.'+mode)
        with TemporaryDirectory(prefix='.gokworks-gear-',dir=destination.parent) as stage_name:
            staged=Path(stage_name)/destination.name
            shutil.copyfile(source,staged)
            if stop is not None and stop.is_set():
                raise OperationCancelled('İşlem durduruldu; dosya yayınlanmadı.')
            if overwrite:
                os.replace(staged,destination)
            else:
                os.link(staged,destination)
        return dict(info,path=str(destination))
