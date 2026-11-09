"""DWG → geçici DXF → mevcut sıkı kontur/birim okuyucusu; iptal edilebilir ve süre sınırlı.

Dönüştürücü sırası:
1. Kullanıcının bilgisayarında kuruluysa ODA File Converter (ayrıca kurulur; paketlenmez,
   lisansı yeniden dağıtıma izin vermez).
2. Uygulama paketindeki LibreDWG ``dwg2dxf`` (GNU LibreDWG 0.13.3, GPL-3.0-or-later).
   Ayrı bir program olarak çağrılır; GOKWORKS koduna bağlanmaz. Lisans ve kaynak
   bildirimi ``licenses/LibreDWG-NOTICE.txt`` içindedir. Kullanıcı hiçbir şey indirmez.

Kaynak dosya hiçbir zaman değiştirilmez: dönüştürücü yalnız geçici kopyayı görür.
"""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from .dxf_import import read_dxf,check_cancel

LIBREDWG_VERSION='0.13.3'
LABELS={'oda':'yerel ODA File Converter','libredwg':f'paketteki LibreDWG {LIBREDWG_VERSION}'}


def converter_path():
    """Installed ODA File Converter, or ValueError when it is not installed."""
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
    raise ValueError('ODA File Converter kurulu değil.')


def libredwg_path():
    """Bundled LibreDWG dwg2dxf: frozen package, build cache next to the source, or PATH."""
    explicit=os.environ.get('GOKWORKS_LIBREDWG_DWG2DXF')
    if explicit:
        if Path(explicit).is_file():return str(Path(explicit).resolve())
        raise ValueError('GOKWORKS_LIBREDWG_DWG2DXF yolu bulunamadı.')
    name='dwg2dxf.exe' if os.name=='nt' else 'dwg2dxf'
    roots=[]
    if getattr(sys,'frozen',False):roots.append(Path(sys._MEIPASS)/'tools'/'libredwg')
    roots.append(Path(__file__).resolve().parents[2]/'packaging'/'vendor'/'libredwg')
    for root in roots:
        if (root/name).is_file():return str(root/name)
    found=shutil.which('dwg2dxf')
    if found:return found
    raise ValueError('Paketteki DWG okuyucu (LibreDWG) bulunamadı; uygulamayı yeniden indirin veya dosyayı DXF olarak ekleyin.')


def converters():
    """Available converters in order of preference: [(kind, executable), …]."""
    found=[]
    for kind,locate in (('oda',converter_path),('libredwg',libredwg_path)):
        try:found.append((kind,locate()))
        except (ValueError,ImportError,OSError):pass
    if not found:
        raise ValueError('DWG okunamıyor: paketteki DWG okuyucu (LibreDWG) eksik. Uygulamayı yeniden indirin veya dosyayı DXF olarak ekleyin.')
    return found


def _environment():
    # External converters own their runtime. Never send GOKWORKS/PyInstaller Qt plugin
    # overrides to them and never mutate the parent's environment.
    environment=os.environ.copy()
    for name in ('QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH','QT_QPA_PLATFORM','QML2_IMPORT_PATH','QML_IMPORT_PATH'):
        environment.pop(name,None)
    if 'LD_LIBRARY_PATH_ORIG' in environment:
        environment['LD_LIBRARY_PATH']=environment['LD_LIBRARY_PATH_ORIG']
    return environment


def _run(command, stop, timeout, cwd=None):
    process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                             env=_environment(),cwd=cwd,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    try:
        deadline=time.monotonic()+timeout
        while process.poll() is None:
            check_cancel(stop)
            if time.monotonic()>=deadline:raise TimeoutError('DWG dönüştürme süresi doldu.')
            try:process.wait(timeout=.08)
            except subprocess.TimeoutExpired:pass
        check_cancel(stop)
        return process.returncode
    finally:
        if process.poll() is None:
            process.kill();process.wait(timeout=10)


def _output(destination):
    candidates=[p for p in destination.parent.iterdir() if p.name.lower()==destination.name.lower()]
    if len(candidates)!=1 or not candidates[0].is_file() or not candidates[0].stat().st_size:return False
    if candidates[0]!=destination:candidates[0].rename(destination)
    return True


def convert_dwg(source, destination, stop=None, *, timeout=120):
    """Convert with the first converter that produces a DXF; returns its kind ('oda' or 'libredwg')."""
    check_cancel(stop)
    source,destination=Path(source),Path(destination)
    problems=[]
    for kind,executable in converters():
        if destination.exists():destination.unlink()
        if kind=='oda':
            code=_run([executable,str(source.parent),str(destination.parent),'ACAD2018','DXF','0','0',source.name],stop,timeout)
        else:
            # LibreDWG skips a few advanced R2010+ objects and may then exit non-zero while still
            # writing a usable DXF; the strict reader below decides whether the geometry is valid.
            code=_run([executable,'-y','-o',str(destination),str(source)],stop,timeout,cwd=str(Path(executable).parent))
        if _output(destination):
            return kind
        problems.append(f'{LABELS[kind]} dönüştüremedi (kod {code})')
    raise ValueError('DWG için DXF çıktısı oluşmadı: '+'; '.join(problems)+'. Dosyayı CAD programında DXF olarak kaydedip ekleyin.')


def _drop_invalid_handles(dxf):
    """Copy of a converter DXF without records whose handle is 0, or None when there are none.

    Handle 0 is never valid in DXF; LibreDWG writes it for objects it cannot convert
    (e.g. MLEADERSTYLE). ezdxf rejects the whole file for one such record, even in
    recover mode, although the geometry is intact. Only these placeholder records go.
    """
    lines=dxf.read_bytes().splitlines(keepends=True)
    pairs=[lines[i:i+2] for i in range(0,len(lines)-1,2)]
    records=[]
    for pair in pairs:
        if pair[0].strip()==b'0' or not records:records.append([])
        records[-1].append(pair)
    # Section and table frames are never dropped: losing one would break the whole file.
    frame={b'SECTION',b'ENDSEC',b'TABLE',b'ENDTAB',b'EOF'}
    invalid=lambda record:(record[0][1].strip() not in frame and
                           any(code.strip() in (b'5',b'105') and value.strip()==b'0' for code,value in record))
    kept=[record for record in records if not invalid(record)]
    if len(kept)==len(records):return None
    cleaned=dxf.with_name(dxf.stem+'-temiz.dxf')
    cleaned.write_bytes(b''.join(line for record in kept for pair in record for line in pair))
    return cleaned


def _read_converted(dxf, stop, options):
    try:
        return read_dxf(dxf,stop=stop,**options)
    except ValueError as error:
        first=error
    # A converter's DXF may carry small structural flaws: drop placeholder records with the
    # invalid handle 0, then repair a copy with ezdxf's recover mode and read strictly again.
    source=_drop_invalid_handles(dxf) or dxf
    if source is not dxf:
        try:
            return read_dxf(source,stop=stop,**options)
        except ValueError:
            pass
    try:
        from ezdxf import recover
        document,auditor=recover.readfile(str(source))
    except Exception:
        raise first from None
    if auditor.has_errors:raise first from None
    repaired=dxf.with_name(dxf.stem+'-onarildi.dxf');document.saveas(str(repaired))
    return read_dxf(repaired,stop=stop,**options)


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
        kind=convert_dwg(copy,dxf,stop) or 'oda'
        parts=_read_converted(dxf,stop,options)
        check_cancel(stop)
        if source.read_bytes()!=before:raise ValueError('DWG okunurken değişti; yeniden yükleyin.')
        digest=hashlib.sha256(before).hexdigest()
        note=f'DWG {LABELS.get(kind,kind)} ile geçici DXF üzerinden okundu.'
        return [replace(p,source=str(source),source_sha256=digest,notes=[*p.notes,note]) for p in parts]
