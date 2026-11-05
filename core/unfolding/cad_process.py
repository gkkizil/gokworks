"""Bounded OCCT worker, using the existing application's frozen/source host pattern."""
import json
import hashlib
import math
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from .models import to_data
from .shapes.common import check_cancel

ROOT=Path(__file__).resolve().parents[2]


def execute(parts,path,*,cancel_token=None,timeout=120.):
    if type(timeout) not in (int,float) or not 0<timeout<=300:raise ValueError('CAD süre sınırı 0–300 saniye olmalı.')
    check_cancel(cancel_token)
    payload={'parts':[dict(id=p.id,surface_patches=to_data(p.surface_patches)) for p in parts]}
    with TemporaryDirectory(prefix='gokworks-unfold-cad-') as folder:
        folder=Path(folder);request=folder/'request.json'
        request.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        command=[sys.executable]
        if not getattr(sys,'frozen',False):command.append(str(ROOT/'main.py'))
        command.extend(['--unfold-worker',str(request)])
        with (folder/'worker.log').open('wb') as log:
            process=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                env={**os.environ,'PYTHONUTF8':'1'},creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            deadline=time.monotonic()+timeout
            try:
                while process.poll() is None:
                    check_cancel(cancel_token)
                    if time.monotonic()>deadline:raise TimeoutError('STEP yerel CAD süre sınırını aştı.')
                    try:process.wait(timeout=.05)
                    except subprocess.TimeoutExpired:pass
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=10)
        check_cancel(cancel_token)
        response=folder/'result.json';source=folder/'surface.step'
        if not response.is_file():raise RuntimeError('STEP worker sonuç vermeden kapandı.')
        data=json.loads(response.read_text(encoding='utf-8'))
        if process.returncode or not data.get('ok') or not source.is_file():raise RuntimeError(data.get('error','STEP doğrulanamadı.'))
        stats=data.get('stats',{});content=source.read_bytes()
        if (data.get('verified') is not True or data.get('sha256')!=hashlib.sha256(content).hexdigest()
                or not content.startswith(b'ISO-10303-21;') or stats.get('solids')!=0 or stats.get('faces',0)<1
                or not isinstance(stats.get('area_mm2'),(int,float)) or not math.isfinite(stats['area_mm2']) or stats['area_mm2']<=0):
            raise ValueError('STEP worker doğrulama kanıtı eksik veya dosyayla uyuşmuyor.')
        # The caller owns an unpublished same-volume temporary file.
        import shutil
        shutil.copyfile(source,path)
        check_cancel(cancel_token)


def run_worker(request_path):
    from dataclasses import dataclass
    from .models import SurfacePatch,FrozenMap
    from .storage import read_json
    request=Path(request_path);folder=request.parent
    @dataclass(frozen=True)
    class CadPart:
        id: str
        surface_patches: tuple
    try:
        data=read_json(request)
        if not isinstance(data,dict) or set(data)!={'parts'} or not isinstance(data['parts'],list) or not 1<=len(data['parts'])<=256:
            raise ValueError('CAD worker parça sözleşmesi geçersiz.')
        parts=[]
        for p in data['parts']:
            if not isinstance(p,dict) or set(p)!={'id','surface_patches'} or not 1<=len(p['surface_patches'])<=16384:
                raise ValueError('CAD worker yüzey sözleşmesi geçersiz.')
            patches=[]
            for s in p['surface_patches']:
                if not isinstance(s,dict) or set(s)!={'kind','data'}:raise ValueError('CAD yüzey alanları geçersiz.')
                patches.append(SurfacePatch(s['kind'],FrozenMap(s['data'])))
            parts.append(CadPart(p['id'],tuple(patches)))
        from .cad import write_step
        target=folder/'surface.step';stats=write_step(tuple(parts),target)
        result=dict(ok=True,verified=True,stats=stats,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    except Exception as exc:result=dict(ok=False,error=str(exc))
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    return 0 if result['ok'] else 1
