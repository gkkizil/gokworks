"""Optional, cancellable ODA export; validate DWG by converting back to real DXF.

No converter is downloaded or bundled. This module has no dependency on GUI or
SolidWorks. No extension renaming, opaque-header-only success or source edits.
"""
import math
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import time

from .shapes.common import check_cancel


def converter_path():
    explicit=os.environ.get('GOKWORKS_ODA_FILE_CONVERTER')
    if explicit:
        if Path(explicit).is_file():return str(Path(explicit).resolve())
        raise ValueError('GOKWORKS_ODA_FILE_CONVERTER dosyası bulunamadı.')
    found=shutil.which('ODAFileConverter')
    if found:return found
    from ezdxf.addons import odafc
    path=odafc.get_win_exec_path() if os.name=='nt' else odafc.get_unix_exec_path()
    if path and Path(path).is_file():return str(path)
    raise ValueError('DWG için kurulu yerel ODA File Converter gerekli.')


def available():
    try:converter_path();return True
    except (ValueError,ImportError,OSError):return False


def _convert(source,directory,kind,token=None,timeout=120):
    check_cancel(token);directory.mkdir(parents=True,exist_ok=True)
    environment=os.environ.copy()
    for key in ('QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH','QT_QPA_PLATFORM','QML2_IMPORT_PATH','QML_IMPORT_PATH'):
        environment.pop(key,None)
    if 'LD_LIBRARY_PATH_ORIG' in environment:environment['LD_LIBRARY_PATH']=environment['LD_LIBRARY_PATH_ORIG']
    command=[converter_path(),str(source.parent),str(directory),'ACAD2018',kind,'0','0',source.name]
    process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                             env=environment,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    try:
        deadline=time.monotonic()+timeout
        while process.poll() is None:
            check_cancel(token)
            if time.monotonic()>=deadline:raise ValueError('ODA dönüştürme süresi doldu.')
            try:process.wait(timeout=.08)
            except subprocess.TimeoutExpired:pass
        check_cancel(token)
        if process.returncode:raise ValueError(f'ODA dönüştürme hatası: {process.returncode}.')
        candidates=[p for p in directory.iterdir() if p.name.lower()==source.stem.lower()+'.'+kind.lower()]
        if len(candidates)!=1 or not candidates[0].is_file():raise ValueError('ODA beklenen çıktı dosyasını oluşturmadı.')
        return candidates[0]
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=10)


def _signature(path):
    import ezdxf
    from ezdxf.path import make_path
    from shapely.geometry import Polygon
    try:doc=ezdxf.readfile(path)
    except ezdxf.DXFError as exc:raise ValueError('DWG geri okumada geçersiz DXF verisi.') from exc
    if doc.units!=4 or doc.audit().errors:raise ValueError('DWG geri okuma birim/yapı doğrulaması başarısız.')
    cuts={};bends={}
    for entity in doc.modelspace():
        layer=entity.dxf.layer
        if layer in ('BEND','BEND_UP','BEND_DOWN','NOMINAL_BEND'):
            bends[layer]=bends.get(layer,0)+1
        if layer not in ('CUT_OUTER','CUT_INNER','NOMINAL_OUTER','NOMINAL_INNER','COMPENSATED_OUTER','COMPENSATED_INNER'):continue
        if entity.dxftype()=='LWPOLYLINE' and not entity.closed:raise ValueError('DWG geri okumada açık kesim konturu.')
        if entity.dxftype() not in ('LWPOLYLINE','CIRCLE'):raise ValueError('DWG geri okumada beklenmeyen kesim varlığı.')
        points=[]
        for point in make_path(entity).flattening(.001):
            if len(points)>100000:raise ValueError('DWG geri okuma geometri bütçesi aşıldı.')
            points.append((point.x,point.y))
        poly=Polygon(points)
        if not poly.is_valid or poly.area<=0:raise ValueError('DWG geri okumada geçersiz kontur.')
        cuts.setdefault(layer,[]).append((poly.area,*poly.bounds))
    if not cuts:raise ValueError('DWG geri okumada kesim konturu bulunamadı.')
    return {k:sorted(v) for k,v in cuts.items()},bends


def write_dwg(part,path,result,token=None):
    from .dxf import write_dxf
    with TemporaryDirectory(prefix='gokworks-unfold-dwg-') as folder:
        folder=Path(folder);incoming=folder/'input';incoming.mkdir()
        dxf=incoming/'development.dxf';write_dxf(part,dxf,result)
        original,bends=_signature(dxf)
        dwg=_convert(dxf,folder/'dwg','DWG',token)
        with dwg.open('rb') as f:header=f.read(6)
        if not header.startswith(b'AC10'):raise ValueError('DWG başlığı geçersiz.')
        back=_convert(dwg,folder/'readback','DXF',token);converted,other_bends=_signature(back)
        if original.keys()!=converted.keys() or bends!=other_bends:raise ValueError('DWG geri okumada katman/büküm bilgisi değişti.')
        for key,rows in original.items():
            if len(rows)!=len(converted[key]):raise ValueError('DWG geri okumada kontur sayısı değişti.')
            if any(not math.isclose(a,b,rel_tol=1e-7,abs_tol=1e-5) for row,other in zip(rows,converted[key]) for a,b in zip(row,other)):
                raise ValueError('DWG geri okumada alan veya ana boyutlar değişti.')
        check_cancel(token);shutil.copyfile(dwg,path)
