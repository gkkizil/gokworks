"""Optional local DWG conversion, isolated from sources and bounded/cancellable.

ODA File Converter is installed separately; it is never downloaded or bundled.
The converted DXF passes the existing strict contour/unit reader unchanged.
"""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import time

from .dxf_import import read_dxf,check_cancel


def converter_path():
    explicit=os.environ.get('GOKWORKS_ODA_FILE_CONVERTER')
    if explicit:
        if Path(explicit).is_file():return str(Path(explicit).resolve())
        raise ValueError('GOKWORKS_ODA_FILE_CONVERTER yolu bulunamadı.')
    found=shutil.which('ODAFileConverter')
    if found:return found
    from ezdxf.addons import odafc
    candidate=odafc.get_win_exec_path() if os.name=='nt' else odafc.get_unix_exec_path()
    if candidate and Path(candidate).is_file():return str(candidate)
    if os.name=='nt':
        for base in ('ProgramFiles','ProgramFiles(x86)'):
            root=Path(os.environ.get(base,'C:/Program Files'))
            for directory in ('ODA','Open Design Alliance'):
                matches=sorted((root/directory).glob('*FileConverter*/ODAFileConverter.exe'),reverse=True)
                if matches:return str(matches[0])
    raise ValueError('DWG okumak için yerel ODA File Converter gerekli. Aracı kurun veya dosyayı DXF olarak ekleyin.')


def convert_dwg(source, destination, stop=None, *, timeout=120):
    check_cancel(stop)
    source,destination=Path(source),Path(destination)
    command=[converter_path(),str(source.parent),str(destination.parent),'ACAD2018','DXF','0','0',source.name]
    # External ODA owns a separate Qt runtime. Do not send GOKWORKS/PyInstaller
    # plugin overrides to that application or mutate the parent's environment.
    environment=os.environ.copy()
    for name in ('QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH','QT_QPA_PLATFORM','QML2_IMPORT_PATH','QML_IMPORT_PATH'):
        environment.pop(name,None)
    if 'LD_LIBRARY_PATH_ORIG' in environment:
        environment['LD_LIBRARY_PATH']=environment['LD_LIBRARY_PATH_ORIG']
    process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                             env=environment,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    try:
        deadline=time.monotonic()+timeout
        while process.poll() is None:
            check_cancel(stop)
            if time.monotonic()>=deadline:raise TimeoutError('DWG dönüştürme süresi doldu.')
            try:process.wait(timeout=.08)
            except subprocess.TimeoutExpired:pass
        check_cancel(stop)
        if process.returncode:raise ValueError(f'ODA File Converter dosyayı dönüştüremedi (kod {process.returncode}).')
        candidates=[p for p in destination.parent.iterdir() if p.name.lower()==destination.name.lower()]
        if len(candidates)!=1 or not candidates[0].is_file():raise ValueError('DWG için DXF çıktısı oluşmadı.')
        if candidates[0]!=destination:candidates[0].rename(destination)
    finally:
        if process.poll() is None:
            process.kill();process.wait(timeout=10)


def read_dwg(filename, *, stop=None, **options):
    source=Path(filename).resolve();check_cancel(stop)
    if source.stat().st_size>100*1024*1024:raise ValueError('DWG dosyası 100 MB sınırını aşıyor.')
    before=source.read_bytes()
    if not before.startswith(b'AC10'):raise ValueError('Geçersiz DWG dosya başlığı.')
    with TemporaryDirectory(prefix='gokworks-dwg-') as folder:
        folder=Path(folder);incoming=folder/'input';outgoing=folder/'output'
        incoming.mkdir();outgoing.mkdir()
        copy=incoming/source.name;copy.write_bytes(before)
        dxf=outgoing/(source.stem+'.dxf')
        convert_dwg(copy,dxf,stop)
        parts=read_dxf(dxf,stop=stop,**options)
        check_cancel(stop)
        if source.read_bytes()!=before:raise ValueError('DWG okunurken değişti; yeniden yükleyin.')
        digest=hashlib.sha256(before).hexdigest()
        return [replace(p,source=str(source),source_sha256=digest,
                        notes=[*p.notes,'DWG yerel ODA File Converter ile geçici DXF üzerinden okundu.']) for p in parts]
